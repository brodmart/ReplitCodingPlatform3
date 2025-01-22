import os
import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from contextlib import contextmanager
from sqlalchemy import text
from utils.logger import log_error, get_logger


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the custom base class
db = SQLAlchemy(model_class=Base)

def init_app(app):
    """Initialize database with application context"""
    try:
        # Configure database URL
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

        if not app.config['SQLALCHEMY_DATABASE_URI']:
            raise ValueError("DATABASE_URL environment variable is not set")

        # Configure SQLAlchemy
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        }

        # Initialize the db with the Flask app
        db.init_app(app)

        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Test connection using text()
            db.session.execute(text("SELECT 1"))
            db.session.commit()
            logger.info("Database connection test successful")

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

@contextmanager
def transaction_context():
    """Context manager for database transactions"""
    try:
        yield
        db.session.commit()
        logger.info("Transaction completed successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction error: {str(e)}")
        raise

def check_db_connection():
    """Verify database connection is working"""
    try:
        db.session.execute(text("SELECT 1"))
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False

class DatabaseHealthCheck:
    """Database health monitoring"""

    @staticmethod
    def check_connection():
        """Check database connection health"""
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True, None
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False, str(e)

    @staticmethod
    def get_connection_stats():
        """Get database connection pool statistics"""
        try:
            return {
                'pool_size': db.engine.pool.size(),
                'checkedin': db.engine.pool.checkedin(),
                'checkedout': db.engine.pool.checkedout(),
                'overflow': db.engine.pool.overflow()
            }
        except Exception as e:
            logger.error(f"Failed to get connection stats: {str(e)}")
            raise

    @staticmethod
    def get_session_info() -> dict:
        """Get current session statistics"""
        try:
            info = {
                'open_transactions': db.session.is_active,
                'autocommit': db.session.autocommit,
                'autoflush': db.session.autoflush,
                'expired_all': db.session._is_clean()
            }
            logger.info("Session info retrieved", extra=info)
            return info
        except Exception as e:
            log_error(e, error_type="DB_SESSION_INFO_ERROR")
            raise