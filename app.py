import os
import logging
import secrets
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g, flash
from flask_cors import CORS
from database import init_db, db
from extensions import init_extensions
from flask_wtf.csrf import CSRFProtect
from extensions import cache

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Enable CORS properly
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "X-CSRFToken"]
        }
    })

    # Configure secret key
    app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

    # Security configurations with relaxed settings for development
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Allow non-HTTPS for development
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_TIME_LIMIT=3600,
        WTF_CSRF_SSL_STRICT=False,
        SERVER_NAME=None,
        SEND_FILE_MAX_AGE_DEFAULT=3600,  # Cache static files for 1 hour
        STATIC_FOLDER='static',
        STATIC_URL_PATH='/static'
    )

    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, X-CSRFToken')
        response.headers.add('Access-Control-Allow-Methods', '*')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    try:
        # Initialize database
        init_db(app)

        # Initialize extensions
        init_extensions(app)

        # Register blueprints
        from routes.auth_routes import auth
        from routes.activity_routes import activities

        app.register_blueprint(auth, url_prefix='/auth')
        app.register_blueprint(activities, url_prefix='/activities')

        # Register error handlers
        register_error_handlers(app)

        return app

    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}")
        raise

def register_error_handlers(app):
    """Register error handlers for the application"""

    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json:
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(f"Internal server error: {str(error)}")
        if request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

# Create the application instance
app = create_app()

@app.before_request
def before_request():
    """Set start time for request timing"""
    g.start_time = time.time()

@app.after_request
def after_request(response):
    """Add security headers and timing information"""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = str(elapsed)

    return response

@app.route('/')
def index():
    try:
        lang = session.get('lang', 'en')
        return render_template('index.html', lang=lang)
    except Exception as e:
        logger.error(f"Error rendering index template: {str(e)}")
        return render_template('errors/500.html'), 500

@app.route('/editor')
@cache.cached(timeout=300)  # Cache for 5 minutes
def editor():
    """Render the code editor page"""
    try:
        lang = session.get('lang', 'en')
        return render_template('editor.html', lang=lang)
    except Exception as e:
        logger.error(f"Error rendering editor template: {str(e)}")
        return render_template('errors/500.html'), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Properly remove database session"""
    db.session.remove()