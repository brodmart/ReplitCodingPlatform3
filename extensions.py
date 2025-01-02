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

# Configure rate limiter with proper error handling
try:
    limiter = Limiter(
        get_remote_address,
        storage_uri="memory://",
        storage_options={},
        default_limits=["200 per day", "50 per hour"],
        headers_enabled=True,
        strategy="fixed-window"  # Added explicit strategy
    )
except Exception as e:
    logger.error(f"Failed to initialize rate limiter: {str(e)}")
    raise

def init_extensions(app):
    """Initialize all Flask extensions with proper error handling"""
    try:
        # Configure session handling with strict security settings
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(minutes=60),
            SESSION_PROTECTION='strong',
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,
            REMEMBER_COOKIE_DURATION=timedelta(days=14),
            REMEMBER_COOKIE_REFRESH_EACH_REQUEST=False
        )

        # Initialize caching with optimized settings
        cache_config = {
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 300,
            'CACHE_THRESHOLD': 1000
        }
        cache.init_app(app, config=cache_config)

        # Initialize compression
        compress.init_app(app)

        # Initialize CSRF protection
        csrf.init_app(app)

        # Initialize rate limiting
        limiter.init_app(app)

        # Configure login manager with strict session protection
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.session_protection = 'strong'
        login_manager.refresh_view = 'auth.login'
        login_manager.needs_refresh_message = 'Please log in again to confirm your identity'
        login_manager.needs_refresh_message_category = 'info'

        # Initialize database migrations
        migrate.init_app(app)

        @login_manager.user_loader
        def load_user(id):
            try:
                from models import Student
                return Student.query.get(int(id))
            except Exception as e:
                logger.error(f"Error loading user: {str(e)}")
                return None

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise