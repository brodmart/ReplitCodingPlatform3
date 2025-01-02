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

# Configure rate limiter with more permissive defaults
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    storage_options={},
    default_limits=["500 per day", "100 per hour"],  # Increased limits
    headers_enabled=True,
    strategy="moving-window",  # Changed to moving-window for better handling
    retry_after="http-date",
    default_limits_deduct_when=lambda response: response.status_code != 429
)

def init_extensions(app, db):
    """Initialize all Flask extensions with proper error handling"""
    try:
        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
        login_manager.login_message_category = 'info'
        login_manager.session_protection = 'strong'
        login_manager.refresh_view = 'auth.login'
        login_manager.needs_refresh_message = 'Session expirée, veuillez vous reconnecter.'
        login_manager.needs_refresh_message_category = 'info'

        # Configure session handling with longer duration
        app.config.update(
            SESSION_COOKIE_SECURE=False,  # Set to True in production
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # Increased to 24 hours
            SESSION_PROTECTION='strong'
        )

        # Initialize caching with longer timeout
        cache_config = {
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 3600,  # Increased to 1 hour
            'CACHE_THRESHOLD': 1000
        }
        cache.init_app(app, config=cache_config)

        # Initialize other extensions
        compress.init_app(app)
        csrf.init_app(app)
        limiter.init_app(app)
        migrate.init_app(app, db)

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