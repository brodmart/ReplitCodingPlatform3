import os
import logging
import time
from flask import Flask, render_template, session, request, jsonify
from flask_login import LoginManager, AnonymousUserMixin, current_user
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_app as init_db
from utils.validation_utils import validate_app_configuration
from compiler import get_template
from utils.socketio_logger import log_socket_event, track_connection, track_session, get_current_metrics

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Socket.IO
socketio = SocketIO()

# Define anonymous user class
class Anonymous(AnonymousUserMixin):
    def __init__(self):
        self.username = 'Guest'

def register_blueprints(app):
    """Register Flask blueprints lazily"""
    with app.app_context():
        # Import blueprints here to avoid circular dependencies
        from routes.auth_routes import auth
        from routes.activity_routes import activities
        from routes.tutorial import tutorial_bp
        from routes.static_routes import static_pages
        from routes.curriculum_routes import curriculum_bp

        app.register_blueprint(auth)
        app.register_blueprint(activities)
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        app.register_blueprint(static_pages)
        app.register_blueprint(curriculum_bp, url_prefix='/curriculum')

def setup_error_handlers(app):
    """Setup Flask error handlers lazily"""
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {error}")
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {error}")
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        logger.warning(f"413 error: {error}")
        return render_template('errors/413.html'), 413

def setup_template_routes(app, csrf):
    """Setup template-related routes with proper CSRF protection"""
    @app.route('/activities/get_template', methods=['POST'])
    def get_code_template():
        """Get code template for a specific programming language."""
        try:
            # Verify CSRF token manually since we're handling JSON
            csrf.protect()

            data = request.get_json()
            if not data:
                logger.warning("Template request had no JSON data")
                return jsonify({
                    'success': False,
                    'error': 'Invalid request format'
                }), 400

            language = data.get('language')
            if not language:
                logger.warning("Template request missing language parameter")
                return jsonify({
                    'success': False,
                    'error': 'Language parameter is required'
                }), 400

            language = language.lower()
            if language not in ['cpp', 'csharp']:
                logger.warning(f"Unsupported language requested: {language}")
                return jsonify({
                    'success': False,
                    'error': f'Unsupported language: {language}'
                }), 400

            template = get_template(language)
            if not template:
                logger.warning(f"No template found for language: {language}")
                return jsonify({
                    'success': False,
                    'error': 'Template not found'
                }), 404

            logger.info(f"Successfully retrieved template for {language}")
            return jsonify({
                'success': True,
                'template': template
            })

        except Exception as e:
            logger.error(f"Error getting template: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal server error'
            }), 500

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, 
                static_url_path='',
                static_folder='static',
                template_folder='templates')

    # Basic configuration
    app.config.update({
        'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
        'SESSION_TYPE': 'filesystem',
        'SESSION_FILE_DIR': os.path.join(os.getcwd(), 'flask_session'),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 60,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        },
        'DEFAULT_LANGUAGE': 'fr',
        'SESSION_PERMANENT': True,
        'PERMANENT_SESSION_LIFETIME': 31536000,
        'WTF_CSRF_ENABLED': True,
        'WTF_CSRF_TIME_LIMIT': None,
        'SERVER_NAME': None
    })

    try:
        # Initialize database first
        init_db(app)
        migrate = Migrate(app, db)

        # Initialize Socket.IO with proper configuration
        socketio.init_app(
            app,
            cors_allowed_origins="*",
            async_mode='eventlet',
            logger=True,
            engineio_logger=True,
            ping_timeout=60,
            ping_interval=25
        )

        # Initialize other extensions
        CORS(app)
        csrf = CSRFProtect()
        csrf.init_app(app)
        Session(app)

        # Setup Login Manager
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.anonymous_user = Anonymous
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'warning'

        @login_manager.user_loader
        def load_user(user_id):
            try:
                from models import Student
                return Student.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user: {str(e)}")
                return None

        # Setup template routes with CSRF protection
        setup_template_routes(app, csrf)
        setup_websocket_handlers()

        # Register blueprints after database is initialized
        register_blueprints(app)
        setup_error_handlers(app)

        # Initialize session with default language if not set
        @app.before_request
        def before_request():
            if 'lang' not in session:
                session['lang'] = app.config['DEFAULT_LANGUAGE']
                session.modified = True
                logger.debug(f"Set default language: {session['lang']}")

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

def setup_websocket_handlers():
    """Setup WebSocket event handlers for console I/O with comprehensive logging"""
    from compiler_service import start_interactive_session, send_input, get_output

    @socketio.on('connect')
    @log_socket_event
    def handle_connect():
        """Handle client connection with metrics tracking"""
        logger.info(f"Client connected to Socket.IO: {request.sid}")
        track_connection(connected=True)
        emit('metrics', get_current_metrics())

    @socketio.on('disconnect')
    @log_socket_event
    def handle_disconnect():
        """Handle client disconnection with cleanup"""
        logger.info(f"Client disconnected from Socket.IO: {request.sid}")
        track_connection(connected=False)

        if 'console_session_id' in session:
            session_id = session['console_session_id']
            logger.info(f"Cleaning up session: {session_id}")
            track_session(session_id, active=False)
            session.pop('console_session_id', None)

    @socketio.on_error()
    @log_socket_event
    def handle_error(e):
        """Handle Socket.IO errors with detailed logging"""
        error_msg = str(e)
        logger.error(f"Socket.IO error: {error_msg}", exc_info=True)
        emit('error', {
            'message': 'Internal server error',
            'error_id': str(time.time()),
            'type': e.__class__.__name__
        })

    @socketio.on('session_start')
    @log_socket_event
    def handle_session_start(data):
        """Handle new interactive session start with metrics"""
        try:
            session_id = data.get('session_id')
            if not session_id:
                logger.error("No session ID provided")
                emit('error', {'message': 'Session ID required'})
                return

            logger.info(f"Registering Socket.IO for session: {session_id}")
            session['console_session_id'] = session_id
            track_session(session_id, active=True)

            # Send initial metrics
            emit('connected', {
                'status': 'success',
                'metrics': get_current_metrics()
            })

        except Exception as e:
            logger.error(f"Error in session_start: {str(e)}", exc_info=True)
            emit('error', {'message': 'Failed to start session'})

    @socketio.on('input')
    @log_socket_event
    def handle_input(data):
        """Handle console input from client with performance tracking"""
        try:
            session_id = data.get('session_id')
            input_text = data.get('input')

            if not session_id or not input_text:
                logger.error("Missing session_id or input")
                emit('error', {'message': 'Invalid input data'})
                return

            logger.debug(f"Sending input to session {session_id}: {input_text}")
            result = send_input(session_id, input_text)

            if result and result.get('success'):
                # Get immediate output after input
                output = get_output(session_id)
                if output and output.get('success'):
                    emit('output', {
                        'type': 'output',
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False),
                        'metrics': get_current_metrics()
                    })
                else:
                    emit('error', {'message': 'Failed to get output'})
            else:
                emit('error', {'message': 'Failed to send input'})

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {'message': 'Failed to process input'})

    @socketio.on('get_metrics')
    @log_socket_event
    def handle_get_metrics():
        """Handle metrics request"""
        emit('metrics', get_current_metrics())

# Create the application instance
app = create_app()

# Add ProxyFix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)