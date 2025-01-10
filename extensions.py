"""Flask extensions initialization"""
import logging
import os
from datetime import timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS
from flask_mail import Mail, Message
from smtplib import SMTPException, SMTPAuthenticationError

# Configure logging
logger = logging.getLogger('extensions')

# Initialize extensions
mail = Mail()
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

def test_mail_connection(app):
    """Test mail server connection with provided credentials"""
    try:
        with app.app_context():
            # Create a test message
            msg = Message(
                subject="Mail Server Test",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[app.config['MAIL_USERNAME']]
            )
            msg.body = "This is a test email to verify SMTP configuration."
            mail.send(msg)
            return True, "Mail server connection test successful"
    except SMTPAuthenticationError as e:
        logger.warning(f"SMTP Authentication Error: {str(e)}")
        return False, "Invalid SMTP credentials. Please check your username and password."
    except SMTPException as e:
        logger.warning(f"SMTP Error: {str(e)}")
        return False, f"SMTP Error: {str(e)}"
    except Exception as e:
        logger.warning(f"Unexpected error testing mail connection: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

def init_extensions(app, db=None):
    """Initialize Flask extensions with proper error handling"""
    try:
        # Configure basic security settings
        app.config.update({
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'SESSION_COOKIE_SECURE': False,  # Set to True in production
            'PERMANENT_SESSION_LIFETIME': timedelta(days=7),
            # Mail settings
            'MAIL_SERVER': 'smtp.gmail.com',
            'MAIL_PORT': 587,
            'MAIL_USE_TLS': True,
            'MAIL_USE_SSL': False,
            'MAIL_USERNAME': os.environ.get('MAIL_USERNAME'),
            'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD'),
            'MAIL_DEFAULT_SENDER': os.environ.get('MAIL_USERNAME'),
            'MAIL_MAX_EMAILS': 5,  # Limit emails per connection
            'MAIL_SUPPRESS_SEND': False,  # Enable email sending
            'MAIL_ASCII_ATTACHMENTS': False,
            # Cache configuration
            'CACHE_TYPE': 'SimpleCache',
            'CACHE_DEFAULT_TIMEOUT': 3600,
            # Rate limiting
            'RATELIMIT_ENABLED': True,
            'RATELIMIT_HEADERS_ENABLED': True,
            'RATELIMIT_STORAGE_URL': "memory://",
            # CSRF Protection
            'WTF_CSRF_ENABLED': True,
            'WTF_CSRF_TIME_LIMIT': 3600,
            # CORS settings
            'CORS_SUPPORTS_CREDENTIALS': True,
        })

        # Initialize Mail with proper error handling
        try:
            mail.init_app(app)
            # Test mail configuration only if credentials are provided
            with app.app_context():
                mail_username = app.config.get('MAIL_USERNAME')
                mail_password = app.config.get('MAIL_PASSWORD')

                if not mail_username or not mail_password:
                    logger.warning("Mail credentials not configured - email functionality will be disabled")
                else:
                    # Test the mail connection but don't fail if it doesn't work
                    success, message = test_mail_connection(app)
                    if not success:
                        logger.warning(f"Mail configuration test failed: {message} - email functionality will be disabled")
                    else:
                        logger.info(f"Mail initialized successfully with username: {mail_username}")
        except Exception as e:
            logger.warning(f"Failed to initialize mail: {str(e)} - email functionality will be disabled")

        # Initialize other extensions with error handling
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
            cors.init_app(app, resources={r"/*": {"origins": "*"}})
            logger.info("CORS initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CORS: {str(e)}")
            raise

        logger.info("All extensions initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize extensions: {str(e)}")
        raise