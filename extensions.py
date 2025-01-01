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

limiter = Limiter(
    get_remote_address,
    storage_uri="memory://",
    storage_options={},
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True
)

class PerformanceMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        start_time = time.time()
        response = None

        try:
            response = self.app(environ, start_response)
            return response
        finally:
            process_time = time.time() - start_time
            if process_time > 1.0:  # Log slow requests
                logger.warning(f"Slow request ({process_time:.2f}s): {environ.get('PATH_INFO')}")

def init_extensions(app):
    """Initialize all Flask extensions"""
    cache.init_app(app, config={'CACHE_TYPE': 'simple'})
    compress.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(id):
        from models import Student
        try:
            return Student.query.get(int(id))
        except Exception as e:
            logger.error(f"Error loading user: {str(e)}")
            return None