
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
