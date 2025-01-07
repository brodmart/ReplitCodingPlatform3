from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS
import logging

# Import db from database
from database import db

# Configure logging
logger = logging.getLogger(__name__)

# Initialize extensions
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()
cors = CORS()

# Configure rate limiter with proper storage
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day"],
    storage_uri="memory://"
)

def init_extensions(app):
    """Initialize Flask extensions"""
    try:
        logger.info("Starting extension initialization...")

        # Configure basic settings
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
            CACHE_TYPE='simple',
            CACHE_DEFAULT_TIMEOUT=3600,
            # Rate limiter configuration
            RATELIMIT_STORAGE_URL="memory://",
            RATELIMIT_STRATEGY="fixed-window",
            RATELIMIT_DEFAULT="200 per day",
            # CORS configuration
            CORS_ALLOW_HEADERS=["Content-Type", "X-CSRF-Token"],
            CORS_EXPOSE_HEADERS=["Content-Type"],
            CORS_SUPPORTS_CREDENTIALS=True
        )

        # Initialize extensions with proper error handling
        try:
            cache.init_app(app)
            logger.debug("Cache initialized")
        except Exception as e:
            logger.error(f"Failed to initialize cache: {str(e)}")
            raise

        try:
            compress.init_app(app)
            logger.debug("Compress initialized")
        except Exception as e:
            logger.error(f"Failed to initialize compress: {str(e)}")
            raise

        try:
            csrf.init_app(app)
            logger.debug("CSRF protection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CSRF: {str(e)}")
            raise

        try:
            limiter.init_app(app)
            logger.debug("Rate limiter initialized")
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {str(e)}")
            raise

        try:
            migrate.init_app(app, db)
            logger.debug("Database migrations initialized")
        except Exception as e:
            logger.error(f"Failed to initialize migrations: {str(e)}")
            raise

        try:
            cors.init_app(app)
            logger.debug("CORS initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CORS: {str(e)}")
            raise

        logger.info("All extensions initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise