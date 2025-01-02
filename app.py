import os
import logging
import secrets
import time
from flask import Flask, render_template, request, jsonify, session, g, flash, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_compress import Compress
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
csrf = CSRFProtect()
compress = Compress()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")
        app = Flask(__name__)

        # Configure security and session settings
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
            SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
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
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_pre_ping": True,
                "pool_recycle": 300,
            },
            JSON_AS_ASCII=False,
            JSONIFY_PRETTYPRINT_REGULAR=False,
            JSONIFY_MIMETYPE='application/json'
        )
        logger.info("Application configuration completed")

        # Initialize extensions
        db.init_app(app)
        csrf.init_app(app)
        compress.init_app(app)
        migrate.init_app(app, db)
        limiter.init_app(app)
        logger.info("Extensions initialized")

        # Add CSRF error handler
        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            logger.error(f"CSRF error: {str(e)}")
            response = jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 400

        # Enable CORS with specific origins
        CORS(app, resources={
            r"/activities/*": {
                "origins": "*",
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "X-CSRF-Token"],
                "methods": ["GET", "POST", "OPTIONS"]
            }
        })
        logger.info("CORS configured")

        # Register blueprints
        from routes.activity_routes import activities
        from routes.tutorial import tutorial_bp

        app.register_blueprint(activities, url_prefix='/activities')
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        logger.info("Blueprints registered")

        @app.before_request
        def before_request():
            """Log request information and set up request context"""
            g.start_time = time.time()
            if 'lang' not in session:
                session['lang'] = 'fr'
            logger.debug(f"Processing request: {request.endpoint}")

        @app.after_request
        def after_request(response):
            """Add response headers and log response time"""
            if hasattr(g, 'start_time'):
                elapsed = time.time() - g.start_time
                response.headers['X-Response-Time'] = str(elapsed)
                logger.debug(f"Request processed in {elapsed:.3f}s")

            # Ensure JSON responses have correct content type
            if response.mimetype == 'application/json':
                response.headers['Content-Type'] = 'application/json; charset=utf-8'

            # Add CORS headers for JSON responses
            if request.method == 'OPTIONS':
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRF-Token'

            return response

        logger.info("Application creation completed successfully")
        return app

    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}", exc_info=True)
        raise

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting development server...")
    app.run(host='0.0.0.0', port=5000, debug=True)