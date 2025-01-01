import os
import logging
from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from typing import Optional
from sqlalchemy import text

# Configure logging
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the custom base class
db = SQLAlchemy(model_class=Base)

@contextmanager
def transaction_context():
    """
    Context manager for database transactions.
    Handles commit/rollback automatically.
    """
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction failed: {str(e)}")
        raise

def init_db(app, max_retries=3):
    """Initialize database with application context and retry logic"""
    logger.info("Configuring database connection...")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set!")
        raise RuntimeError("DATABASE_URL must be set")

    # Enhanced database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_timeout': 30,
        'pool_recycle': 1200,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10,
            'application_name': 'codecrafthub'
        },
        'echo_pool': True
    }

    # Initialize the db with the Flask app
    db.init_app(app)

    # Test database connection with retry logic
    with app.app_context():
        for attempt in range(max_retries):
            try:
                db.engine.connect()
                logger.info("Database connection successful")
                _setup_event_listeners()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying...")

def _setup_event_listeners():
    """Setup SQLAlchemy event listeners for monitoring"""
    from sqlalchemy import event

    @event.listens_for(db.engine, 'checkout')
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Ping connection on checkout to ensure it's still alive"""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            raise OperationalError("Database connection lost")
        finally:
            cursor.close()

    @event.listens_for(db.engine, 'connect')
    def receive_connect(dbapi_connection, connection_record):
        """Set session parameters on connection"""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET timezone='UTC'")
        cursor.close()

class DatabaseHealthCheck:
    """Database health monitoring"""
    @staticmethod
    def check_connection() -> tuple[bool, Optional[str]]:
        """Check database connection health"""
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, None
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False, str(e)

    @staticmethod
    def get_connection_stats() -> dict:
        """Get database connection pool statistics"""
        return {
            'pool_size': db.engine.pool.size(),
            'checkedin': db.engine.pool.checkedin(),
            'checkedout': db.engine.pool.checkedout(),
            'overflow': db.engine.pool.overflow()
        }