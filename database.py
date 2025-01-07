import os
import logging
from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from typing import Optional
from sqlalchemy import text, event
from datetime import datetime
from utils.logger import log_error, get_logger

# Configure logging
logger = get_logger('database')

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the custom base class
db = SQLAlchemy(model_class=Base)

def init_db(app):
    """Initialize database with application context"""
    try:
        # Configure database
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800
        }

        # Initialize the db with the Flask app
        db.init_app(app)

        with app.app_context():
            # Setup event listeners for connection handling
            @event.listens_for(db.engine, 'connect')
            def receive_connect(dbapi_connection, connection_record):
                try:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("SET timezone='UTC'")
                    cursor.close()
                    logger.info("Database connection configured successfully")
                except Exception as e:
                    logger.error(f"Failed to configure database connection: {str(e)}")
                    raise

            @event.listens_for(db.engine, 'checkout')
            def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                try:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    logger.debug("Connection health check passed")
                except Exception as e:
                    logger.error(f"Connection health check failed: {str(e)}")
                    raise OperationalError(statement="Connection lost", 
                                        params=None,
                                        orig=e)

            # Verify connection
            db.engine.connect()
            logger.info("Database connection successful")

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
            logger.info("Session info retrieved", **info)
            return info
        except Exception as e:
            log_error(e, error_type="DB_SESSION_INFO_ERROR")
            raise