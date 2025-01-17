import os
import logging
from flask import Flask, render_template
from flask_login import LoginManager, AnonymousUserMixin
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, init_db
from extensions import init_extensions
from utils.logger import setup_logging
from models import Student

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
        # Mail settings remain unchanged
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': 587,
        'MAIL_USE_TLS': True,
        'MAIL_USE_SSL': False,
        'MAIL_USERNAME': os.environ.get('MAIL_USERNAME'),
        'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD'),
        'MAIL_DEFAULT_SENDER': os.environ.get('MAIL_USERNAME'),
        # Session security settings remain unchanged
        'SESSION_COOKIE_SECURE': False,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'PERMANENT_SESSION_LIFETIME': 1800,
        # Request settings remain unchanged
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,
        # Registration settings remain unchanged
        'REGISTRATION_ENABLED': True,
        'ALLOWED_EMAIL_DOMAINS': [
            # Government domains
            'ontario.ca',
            'edu.ontario.ca',
            # School board domains remain unchanged
            'tdsb.on.ca',
            'peelschools.org',
            'edu.cepeo.on.ca',
            'yrdsb.ca',
            'ddsb.ca',
            'hdsb.ca',
            'hwdsb.on.ca',
            'dsbn.org',
            'wrdsb.ca',
            'tvdsb.ca',
            'ocdsb.ca',
            'ugdsb.on.ca',
            'scdsb.on.ca',
            'kprschools.ca',
            'lkdsb.net',
            'gogeeco.net',
            'tldsb.on.ca',
            # French boards remain unchanged
            'cepeo.on.ca',
            'csviamonde.ca',
            'ecolecatholique.ca',
            'cscmonavenir.ca',
            'cspne.ca',
            'cscprovidence.ca',
            # English Catholic boards remain unchanged
            'tcdsb.org',
            'dpcdsb.org',
            'ycdsb.ca',
            'dcdsb.ca',
            'hcdsb.org',
            'bhncdsb.ca',
            'alcdsb.on.ca',
            'ocsb.ca',
            # First Nations boards remain unchanged
            'knet.ca',
            'nnec.on.ca',
            # Student subdomains remain unchanged
            'student.tdsb.on.ca',
            'students.peelschools.org',
            'gapps.yrdsb.ca',
            'students.ocdsb.ca'
        ],
    })

    try:
        # Create session directory if it does not exist
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

        # Initialize database
        init_db(app)

        # Initialize Flask-Migrate
        migrate = Migrate(app, db)

        # Initialize extensions
        init_extensions(app, db)

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
                return Student.query.get(int(user_id))
            except:
                return None

        # Register blueprints
        from routes.auth_routes import auth
        from routes.activity_routes import activities
        from routes.tutorial import tutorial_bp
        from routes.static_routes import static_pages

        app.register_blueprint(auth)
        app.register_blueprint(activities, url_prefix='/activities')
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        app.register_blueprint(static_pages)

        # Error handlers remain unchanged
        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('errors/404.html', lang='en'), 404

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            return render_template('errors/500.html', lang='en'), 500

        @app.errorhandler(413)
        def request_entity_too_large(error):
            return render_template('errors/413.html', lang='en'), 413

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

# Create the application instance
app = create_app()

# Add ProxyFix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)