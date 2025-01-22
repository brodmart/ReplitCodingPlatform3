import os
import logging
import time
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Socket.IO with minimal configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

Base = DeclarativeBase()
db = SQLAlchemy(model_class=Base)

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
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': True,
        'WTF_CSRF_TIME_LIMIT': None,
    })

    try:
        # Initialize extensions
        db.init_app(app)
        socketio.init_app(app)
        CORS(app)
        Session(app)

        with app.app_context():
            db.create_all()

        # Initialize session with default language if not set
        @app.before_request
        def before_request():
            if 'lang' not in session:
                session['lang'] = 'fr'
                session.modified = True

        # Register Socket.IO event handlers
        setup_websocket_handlers()

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

def setup_websocket_handlers():
    """Setup WebSocket event handlers for console I/O"""
    from compiler_service import start_interactive_session, send_input, get_output, compile_and_run

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info(f"Client connected: {request.sid}")
        session['sid'] = request.sid

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        logger.info(f"Client disconnected: {request.sid}")
        if 'console_session_id' in session:
            session.pop('console_session_id', None)
        session.pop('sid', None)

    @socketio.on('compile_and_run')
    def handle_compile_and_run(data):
        """Handle code compilation and execution"""
        try:
            code = data.get('code')
            language = data.get('language', 'cpp')

            if not code:
                emit('error', {'message': 'No code provided'})
                return

            result = compile_and_run(code, language)

            if result['success']:
                session_id = result.get('session_id')
                if session_id:
                    session['console_session_id'] = session_id

                    if result.get('interactive'):
                        # For interactive programs, wait briefly for initial prompt
                        time.sleep(0.1)
                        output = get_output(session_id)
                        if output and output.get('success'):
                            emit('output', {
                                'output': output.get('output', ''),
                                'waiting_for_input': output.get('waiting_for_input', False)
                            })

                emit('compilation_result', {
                    'success': True,
                    'session_id': session_id,
                    'interactive': result.get('interactive', False)
                })
            else:
                emit('compilation_result', {
                    'success': False,
                    'error': result.get('error', 'Compilation failed')
                })

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {'message': 'Internal server error'})

    @socketio.on('input')
    def handle_input(data):
        """Handle console input from client"""
        try:
            session_id = data.get('session_id')
            input_text = data.get('input')

            if not session_id or not input_text:
                emit('error', {'message': 'Invalid input data'})
                return

            result = send_input(session_id, input_text)

            if result and result.get('success'):
                # Get immediate output after input
                time.sleep(0.1)
                output = get_output(session_id)
                if output and output.get('success'):
                    emit('output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {'message': 'Failed to process input'})

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)