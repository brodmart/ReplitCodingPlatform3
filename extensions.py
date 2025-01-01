import time
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_migrate import Migrate

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

class PerformanceMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)

    def __call__(self, environ, start_response):
        try:
            request_start = time.time()

            def custom_start_response(status, headers, exc_info=None):
                # Add performance header
                headers.append(('X-Response-Time', str(time.time() - request_start)))
                return start_response(status, headers, exc_info)

            response = self.app(environ, custom_start_response)
            return response

        except Exception as e:
            self.logger.error(f"Performance middleware error: {str(e)}")
            return self.app(environ, start_response)
        finally:
            process_time = time.time() - request_start
            if process_time > 1.0:  # Log slow requests
                self.logger.warning(
                    f"Slow request ({process_time:.2f}s): {environ.get('PATH_INFO')}"
                )

def init_extensions(app):
    """Initialize all Flask extensions with proper error handling"""
    try:
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

        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.session_protection = 'strong'

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