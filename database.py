import os
import logging
from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from typing import Optional
from sqlalchemy import text, event

# Configure logging
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the custom base class
db = SQLAlchemy(model_class=Base)

def init_db(app):
    """Initialize database with application context"""
    logger.info("Configuring database connection...")

    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_timeout': 30,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'echo_pool': True
    }

    # Initialize the db with the Flask app
    db.init_app(app)

    # Setup event listeners for monitoring
    _setup_event_listeners()
    _setup_session_handlers()

    # Test database connection
    with app.app_context():
        try:
            # Verify connection
            db.engine.connect()
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise

@contextmanager
def transaction_context():
    """Context manager for database transactions"""
    try:
        yield
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Transaction failed: {str(e)}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error in transaction: {str(e)}")
        raise

def _setup_event_listeners():
    """Setup SQLAlchemy event listeners for monitoring and connection management"""
    @event.listens_for(db.engine, 'connect')
    def receive_connect(dbapi_connection, connection_record):
        """Configure connection on creation"""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET timezone='UTC'")
        cursor.execute("SET client_encoding='UTF8'")
        cursor.execute("SET application_name='codecrafthub'")
        cursor.close()

    @event.listens_for(db.engine, 'checkout')
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Verify connection is valid on checkout"""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            logger.error("Connection invalid, forcing reconnection")
            raise OperationalError("Database connection lost")
        finally:
            cursor.close()

def _setup_session_handlers():
    """Configure session event handlers"""
    @event.listens_for(db.session, 'after_commit')
    def receive_after_commit(session):
        """Log successful commits"""
        logger.debug("Transaction committed successfully")

    @event.listens_for(db.session, 'after_rollback')
    def receive_after_rollback(session):
        """Log rollbacks"""
        logger.warning("Transaction rolled back")

class DatabaseHealthCheck:
    """Database health monitoring with enhanced metrics"""

    @staticmethod
    def check_connection() -> tuple[bool, Optional[str]]:
        """Check database connection health with detailed diagnostics"""
        try:
            with db.engine.connect() as conn:
                # Run more comprehensive health check
                conn.execute(text("SELECT 1"))
                conn.execute(text("SELECT version()"))
                return True, None
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False, str(e)

    @staticmethod
    def get_connection_stats() -> dict:
        """Get detailed database connection pool statistics"""
        return {
            'pool_size': db.engine.pool.size(),
            'checkedin': db.engine.pool.checkedin(),
            'checkedout': db.engine.pool.checkedout(),
            'overflow': db.engine.pool.overflow(),
            'timeout': db.engine.pool._timeout,
            'recycle': db.engine.pool._recycle
        }

    @staticmethod
    def get_session_info() -> dict:
        """Get current session statistics"""
        return {
            'open_transactions': db.session.is_active,
            'autocommit': db.session.autocommit,
            'autoflush': db.session.autoflush,
            'expired_all': db.session._is_clean()
        }