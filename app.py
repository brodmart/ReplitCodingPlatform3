import os
import logging
from flask import Flask, render_template, session
from flask_login import LoginManager, AnonymousUserMixin
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db

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
        'DEFAULT_LANGUAGE': 'fr',  # Set default language
        'SESSION_PERMANENT': True,  # Make sessions permanent
        'PERMANENT_SESSION_LIFETIME': 31536000,  # Set session lifetime to 1 year
    })

    try:
        # Create session directory if it does not exist
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

        # Initialize database
        db.init_app(app)

        # Initialize Flask-Migrate
        migrate = Migrate(app, db)

        # Initialize extensions
        CORS(app)
        CSRFProtect(app)
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

        # Initialize session with default language if not set
        @app.before_request
        def before_request():
            if 'lang' not in session:
                session['lang'] = app.config['DEFAULT_LANGUAGE']
                session.modified = True

        # Register blueprints
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

        # Error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('errors/404.html'), 404

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            return render_template('errors/500.html'), 500

        @app.errorhandler(413)
        def request_entity_too_large(error):
            return render_template('errors/413.html'), 413

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
    app.run(host='0.0.0.0', port=5000, debug=True)