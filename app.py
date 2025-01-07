import os
import logging
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from flask_wtf.csrf import CSRFError
import traceback

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Add file handler for error logging
error_handler = logging.FileHandler('error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
))
logger.addHandler(error_handler)

def log_request_info():
    """Log detailed request information"""
    logger.debug(f"""
Request Details:
    Path: {request.path}
    Method: {request.method}
    Headers: {dict(request.headers)}
    Args: {dict(request.args)}
    Form: {dict(request.form)}
    Session: {dict(session)}
    """.strip())

def create_app():
    """Create and configure the Flask application"""
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
            logger.warning(f"404 error: {request.url}")
            return render_template('errors/404.html'), 404

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            logger.error(f"CSRF error on {request.url}: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception on {request.url}: {str(e)}", exc_info=True)
            logger.error(f"Stack trace: {''.join(traceback.format_tb(e.__traceback__))}")
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
        logger.error(f"Failed to create application: {str(e)}", exc_info=True)
        logger.error(f"Stack trace: {''.join(traceback.format_tb(e.__traceback__))}")
        raise

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting development server...")
    app.run(host='0.0.0.0', port=5000)