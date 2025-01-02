import time
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from datetime import timedelta

logger = logging.getLogger(__name__)

# Initialize extensions without app context
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()

# Configure rate limiter with reasonable defaults
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    storage_options={},
    default_limits=["200 per day"],  # More permissive default limit
    headers_enabled=True,
    strategy="fixed-window",  # Simpler strategy
    retry_after="delta-seconds"
)

def init_extensions(app, db):
    """Initialize all Flask extensions"""
    try:
        # Basic session configuration
        app.config.update(
            SESSION_COOKIE_SECURE=False,  # Set to True in production
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),  # Longer session lifetime
            SESSION_PROTECTION='basic'  # Less strict protection
        )

        # Initialize caching with simple configuration
        cache_config = {
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 3600
        }
        cache.init_app(app, config=cache_config)

        # Initialize other extensions
        compress.init_app(app)
        csrf.init_app(app)
        limiter.init_app(app)
        migrate.init_app(app, db)

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise