"""Flask extensions initialization"""
import logging
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS

# Configure logging
logger = logging.getLogger('extensions')

# Initialize extensions
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()
cors = CORS()

# Configure rate limiter with safe defaults
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"],
    strategy="fixed-window"
)

def init_extensions(app, db=None):
    """Initialize Flask extensions with proper error handling"""
    try:
        # Configure basic security settings
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            SESSION_COOKIE_SECURE=False,  # Set to True in production
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
            # Cache configuration
            CACHE_TYPE='SimpleCache',
            CACHE_DEFAULT_TIMEOUT=3600,
            # Rate limiting
            RATELIMIT_ENABLED=True,
            RATELIMIT_HEADERS_ENABLED=True,
            RATELIMIT_STORAGE_URL="memory://",
            # CSRF Protection
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_TIME_LIMIT=3600,
            # CORS settings
            CORS_SUPPORTS_CREDENTIALS=True
        )

        # Initialize extensions with error handling
        try:
            cache.init_app(app)
            logger.info("Cache initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache: {str(e)}")
            raise

        try:
            compress.init_app(app)
            logger.info("Compression initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize compression: {str(e)}")
            raise

        try:
            csrf.init_app(app)
            logger.info("CSRF protection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CSRF protection: {str(e)}")
            raise

        try:
            limiter.init_app(app)
            logger.info("Rate limiter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {str(e)}")
            raise

        try:
            if db is not None:
                migrate.init_app(app, db)
                logger.info("Database migrations initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database migrations: {str(e)}")
            raise

        try:
            cors.init_app(app)
            logger.info("CORS initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CORS: {str(e)}")
            raise

        logger.info("All extensions initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise