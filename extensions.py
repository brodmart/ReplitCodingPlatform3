import time
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# Import db from database instead of creating new SQLAlchemy instance
from database import db

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
    default_limits=["200 per day"],
    headers_enabled=True,
    strategy="fixed-window",
    retry_after="delta-seconds"
)

def init_extensions(app):
    """Initialize all Flask extensions with enhanced error handling"""
    try:
        app.logger.info("Starting extension initialization...")

        # Basic session configuration
        app.config.update(
            SESSION_COOKIE_SECURE=False,  # Set to True in production
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
            SESSION_PROTECTION='basic'
        )
        app.logger.debug("Session configuration updated")

        # Initialize caching with simple configuration
        try:
            cache_config = {
                'CACHE_TYPE': 'simple',
                'CACHE_DEFAULT_TIMEOUT': 3600
            }
            app.config.update(cache_config)
            cache.init_app(app)
            app.logger.info("Cache initialization successful")
        except Exception as e:
            app.logger.error(f"Cache initialization failed: {str(e)}", exc_info=True)
            raise

        # Initialize other extensions
        try:
            compress.init_app(app)
            csrf.init_app(app)
            limiter.init_app(app)
            migrate.init_app(app, db)
            app.logger.info("All other extensions initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize extensions: {str(e)}", exc_info=True)
            raise

        app.logger.info("All extensions initialized successfully")
        return True

    except Exception as e:
        app.logger.error(f"Critical error during extension initialization: {str(e)}", exc_info=True)
        raise