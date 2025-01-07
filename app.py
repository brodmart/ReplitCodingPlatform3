import os
import logging
import secrets
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from flask_wtf.csrf import CSRFError
import traceback

# Enhanced logging configuration with rotation
log_formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]:\n%(message)s'
)

def setup_logging():
    """Configure logging with rotation and proper handlers"""
    logger = logging.getLogger('codecrafthub')
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()

    # Console handler for all logs
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    # Rotating file handler for errors
    error_handler = RotatingFileHandler(
        'error.log', 
        maxBytes=10485760,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_formatter)
    logger.addHandler(error_handler)

    # Access log handler
    access_handler = RotatingFileHandler(
        'access.log',
        maxBytes=10485760,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(log_formatter)
    logger.addHandler(access_handler)

    return logger

# Initialize logger
logger = setup_logging()

def log_request_info():
    """Log detailed request information with enhanced formatting"""
    try:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'method': request.method,
            'path': request.path,
            'query_string': request.query_string.decode('utf-8'),
            'headers': dict(request.headers),
            'source_ip': request.remote_addr,
            'user_agent': request.user_agent.string
        }

        # Add form/json data if present
        if request.form:
            log_data['form_data'] = dict(request.form)
        if request.is_json:
            log_data['json_data'] = request.get_json()

        # Add session info if available
        if session:
            log_data['session_id'] = session.get('_id')

        logger.info(f"Request Details:\n" + "\n".join(f"{k}: {v}" for k, v in log_data.items()))
    except Exception as e:
        logger.error(f"Error logging request info: {str(e)}", exc_info=True)

def create_app():
    """Create and configure the Flask application with enhanced error handling"""
    try:
        logger.info("Starting application creation...")
        app = Flask(__name__)

        # Configure security and session settings
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
            TEMPLATES_AUTO_RELOAD=True,
            SEND_FILE_MAX_AGE_DEFAULT=0,
            DEBUG=True,
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_TIME_LIMIT=3600,
            WTF_CSRF_SSL_STRICT=False,
            RATELIMIT_DEFAULT="200 per day",
            RATELIMIT_STORAGE_URL="memory://",
            RATELIMIT_HEADERS_ENABLED=True,
            JSON_AS_ASCII=False,
            JSONIFY_PRETTYPRINT_REGULAR=False,
            JSONIFY_MIMETYPE='application/json',
            SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        )

        # Initialize database first
        from database import init_db, db
        init_db(app)

        # Initialize all extensions
        from extensions import init_extensions
        init_extensions(app)

        # Enable CORS with specific origins
        CORS(app, resources={
            r"/activities/*": {
                "origins": "*",
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "X-CSRF-Token"],
                "methods": ["GET", "POST", "OPTIONS"]
            }
        })

        # Register blueprints
        from routes.activity_routes import activities
        from routes.tutorial import tutorial_bp
        from routes.auth_routes import auth

        app.register_blueprint(activities, url_prefix='/activities')
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        app.register_blueprint(auth, url_prefix='/auth')

        @app.before_request
        def before_request():
            """Log request information before processing"""
            g.request_start_time = datetime.utcnow()
            log_request_info()

        @app.after_request
        def after_request(response):
            """Log response information after processing"""
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                logger.info(f"Request completed in {duration.total_seconds():.3f}s with status {response.status_code}")
            return response

        @app.route('/')
        def index():
            """Root route handler"""
            try:
                logger.debug("Rendering index template...")
                language = request.args.get('language', 'cpp')
                logger.debug(f"Selected language: {language}")

                # Log template details
                logger.debug("Setting up template data...")
                templates = {
                    'cpp': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
                    'csharp': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}'
                }
                logger.debug("Template data prepared successfully")

                # Ensure session has required values
                if 'lang' not in session:
                    logger.debug("Setting default language in session to 'fr'")
                    session['lang'] = 'fr'

                logger.debug(f"Rendering index with params - lang: {session.get('lang', 'fr')}, language: {language}")
                return render_template('index.html', 
                                   lang=session.get('lang', 'fr'),
                                   language=language,
                                   templates=templates)
            except Exception as e:
                logger.error(f"Error rendering index template: {str(e)}", exc_info=True)
                logger.error(f"Stack trace: {''.join(traceback.format_tb(e.__traceback__))}")
                return render_template('errors/500.html'), 500

        # Enhanced error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            """Enhanced 404 error handler with detailed logging"""
            error_details = {
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'error': str(error)
            }
            logger.warning(f"404 Error Details:\n" + "\n".join(f"{k}: {v}" for k, v in error_details.items()))
            return render_template('errors/404.html'), 404

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            """Enhanced CSRF error handler with security logging"""
            error_details = {
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'error': str(e)
            }
            logger.error(f"CSRF Error Details:\n" + "\n".join(f"{k}: {v}" for k, v in error_details.items()))
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_exception(e):
            """Enhanced exception handler with detailed error logging"""
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'traceback': traceback.format_exc()
            }
            logger.error(f"Unhandled Exception Details:\n" + "\n".join(f"{k}: {v}" for k, v in error_details.items()))
            return jsonify({
                'success': False,
                'error': "Une erreur inattendue s'est produite"
            }), 500

        # Create all database tables
        with app.app_context():
            import models
            db.create_all()
            logger.info("Database tables created successfully")

        logger.info("Application creation completed successfully")
        return app

    except Exception as e:
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'traceback': traceback.format_exc()
        }
        logger.error(f"Application Creation Failed:\n" + "\n".join(f"{k}: {v}" for k, v in error_details.items()))
        raise

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting development server...")
    app.run(host='0.0.0.0', port=5000)