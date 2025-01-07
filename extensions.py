"""Flask extensions initialization"""
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS
from utils.logger import get_logger

# Configure logging
logger = get_logger('extensions')

# Initialize extensions
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()
cors = CORS()

# Configure rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def init_extensions(app, db=None):
    """Initialize Flask extensions"""
    try:
        # Configure basic settings
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
            CACHE_TYPE='simple',
            CACHE_DEFAULT_TIMEOUT=3600
        )

        # Initialize extensions
        cache.init_app(app)
        compress.init_app(app)
        csrf.init_app(app)
        limiter.init_app(app)

        if db is not None:
            migrate.init_app(app, db)

        cors.init_app(app)

        logger.info("All extensions initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise