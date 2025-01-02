import time
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_migrate import Migrate
from datetime import timedelta

logger = logging.getLogger(__name__)

# Initialize extensions without app context
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
login_manager = LoginManager()
migrate = Migrate()

# Configure rate limiter with proper configuration
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    storage_options={},
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True,
    strategy="fixed-window",
    retry_after="http-date"
)

def init_extensions(app, db): # Added db parameter here
    """Initialize all Flask extensions with proper error handling"""
    try:
        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'
        login_manager.session_protection = 'strong'

        # Configure session handling
        app.config.update(
            SESSION_COOKIE_SECURE=False,  # Set to True in production
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(minutes=60),
            SESSION_PROTECTION='strong'
        )

        # Initialize caching
        cache_config = {
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 300,
            'CACHE_THRESHOLD': 1000
        }
        cache.init_app(app, config=cache_config)

        # Initialize other extensions
        compress.init_app(app)
        csrf.init_app(app)
        limiter.init_app(app)
        migrate.init_app(app, db) # Added db parameter here

        @login_manager.user_loader
        def load_user(user_id):
            try:
                from models import Student
                return Student.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user: {str(e)}")
                return None

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise