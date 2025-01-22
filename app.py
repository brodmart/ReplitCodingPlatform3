import os
import logging
from flask import Flask, render_template, session
from flask_login import LoginManager, AnonymousUserMixin
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_app as init_db
from utils.validation_utils import validate_app_configuration

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define anonymous user class
class Anonymous(AnonymousUserMixin):
    def __init__(self):
        self.username = 'Guest'

def register_blueprints(app):
    """Register Flask blueprints lazily"""
    with app.app_context():
        # Import blueprints here to avoid circular dependencies and early loading
        from routes.auth_routes import auth
        from routes.activities import activities_bp
        from routes.tutorial import tutorial_bp
        from routes.static_routes import static_pages
        from routes.curriculum_routes import curriculum_bp

        app.register_blueprint(auth)
        app.register_blueprint(activities_bp)
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
    })

    try:
        # Validate application configuration
        if not validate_app_configuration(app):
            raise RuntimeError("Application configuration validation failed")

        # Initialize extensions and create session directory
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

        # Initialize database first
        init_db(app)
        migrate = Migrate(app, db)

        # Initialize other extensions lazily
        CORS(app)
        csrf = CSRFProtect()
        csrf.init_app(app)
        Session(app)

        # Setup Login Manager lazily
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.anonymous_user = Anonymous
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'warning'

        @login_manager.user_loader
        def load_user(user_id):
            try:
                # Import Student model lazily to avoid circular imports
                from models import Student
                return Student.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user: {str(e)}")
                return None

        # Register blueprints after database is initialized
        register_blueprints(app)

        # Setup error handlers
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

# Create the application instance
app = create_app()

# Add ProxyFix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting Flask application on port {port}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask application: {str(e)}")
        raise