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
import psutil
import platform

# Configure logging
logger = get_logger('extensions')

# Initialize extensions
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()
cors = CORS()

# Configure rate limiter with proper storage
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

def init_extensions(app, db=None):
    """Initialize Flask extensions"""
    try:
        logger.info("Starting extension initialization...", 
                   python_version=platform.python_version(),
                   platform=platform.platform(),
                   memory_usage=psutil.Process().memory_info().rss / 1024 / 1024)

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

        # Initialize extensions with proper error handling and performance monitoring
        try:
            cache.init_app(app)
            logger.debug("Cache initialized", 
                        cache_type=app.config['CACHE_TYPE'],
                        cache_timeout=app.config['CACHE_DEFAULT_TIMEOUT'])
        except Exception as e:
            logger.error(f"Failed to initialize cache: {str(e)}", 
                        cache_config=app.config.get('CACHE_TYPE'))
            raise

        try:
            compress.init_app(app)
            logger.debug("Compress initialized", 
                        compression_enabled=True)
        except Exception as e:
            logger.error(f"Failed to initialize compress: {str(e)}")
            raise

        try:
            csrf.init_app(app)
            logger.debug("CSRF protection initialized",
                        csrf_enabled=app.config['WTF_CSRF_ENABLED'])
        except Exception as e:
            logger.error(f"Failed to initialize CSRF: {str(e)}",
                        csrf_config=app.config.get('WTF_CSRF_ENABLED'))
            raise

        try:
            limiter.init_app(app)
            logger.debug("Rate limiter initialized",
                        rate_limit_default=app.config['RATELIMIT_DEFAULT'],
                        rate_limit_strategy=app.config['RATELIMIT_STRATEGY'])
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {str(e)}",
                        rate_limit_config=app.config.get('RATELIMIT_DEFAULT'))
            raise

        if db is not None:
            try:
                migrate.init_app(app, db)
                logger.debug("Database migrations initialized",
                           db_uri=app.config['SQLALCHEMY_DATABASE_URI'],
                           db_pool_size=app.config['SQLALCHEMY_ENGINE_OPTIONS'].get('pool_size'),
                           db_pool_recycle=app.config['SQLALCHEMY_ENGINE_OPTIONS'].get('pool_recycle'))
            except Exception as e:
                logger.error(f"Failed to initialize migrations: {str(e)}",
                           db_config=app.config.get('SQLALCHEMY_DATABASE_URI'))
                raise

        try:
            cors.init_app(app)
            logger.debug("CORS initialized",
                        cors_origins=app.config.get('CORS_ORIGINS', '*'),
                        cors_methods=app.config.get('CORS_METHODS'),
                        cors_allow_headers=app.config.get('CORS_ALLOW_HEADERS'))
        except Exception as e:
            logger.error(f"Failed to initialize CORS: {str(e)}",
                        cors_config=app.config.get('CORS_ORIGINS'))
            raise

        # Log final initialization status with system metrics
        process = psutil.Process()
        logger.info("All extensions initialized successfully",
                   memory_usage_mb=process.memory_info().rss / 1024 / 1024,
                   cpu_percent=process.cpu_percent(),
                   thread_count=len(process.threads()),
                   open_files=len(process.open_files()),
                   connections=len(process.connections()))
        return True

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}",
                    error_type=type(e).__name__,
                    error_details=str(e))
        raise