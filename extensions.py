from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# Import db from database
from database import db

# Initialize extensions
cache = Cache()
compress = Compress()
csrf = CSRFProtect()
migrate = Migrate()

# Configure rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day"]
)

def init_extensions(app):
    """Initialize Flask extensions"""
    # Configure basic settings
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        CACHE_TYPE='simple',
        CACHE_DEFAULT_TIMEOUT=3600
    )

    # Initialize the app with the extension, flask-sqlalchemy >= 3.0.x
    cache.init_app(app)
    compress.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    return True