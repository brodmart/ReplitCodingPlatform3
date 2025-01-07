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
    logger.info("Configuring database connection...")

    try:
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

        with app.app_context():
            try:
                # Setup event listeners for detailed logging
                @event.listens_for(db.engine, 'connect')
                def receive_connect(dbapi_connection, connection_record):
                    """Configure connection on creation"""
                    try:
                        cursor = dbapi_connection.cursor()
                        cursor.execute("SET timezone='UTC'")
                        cursor.execute("SET client_encoding='UTF8'")
                        cursor.execute("SET application_name='codecrafthub'")
                        logger.info("Database connection configured", 
                                  connection_id=id(dbapi_connection),
                                  settings={"timezone": "UTC", "encoding": "UTF8"})
                        cursor.close()
                    except Exception as e:
                        log_error(e, error_type="DB_CONNECTION_CONFIG_ERROR")
                        raise

                @event.listens_for(db.engine, 'checkout')
                def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                    """Verify connection is valid on checkout"""
                    try:
                        cursor = dbapi_connection.cursor()
                        start_time = datetime.utcnow()
                        cursor.execute("SELECT 1")
                        duration = (datetime.utcnow() - start_time).total_seconds()
                        logger.debug("Connection health check", 
                                   connection_id=id(dbapi_connection),
                                   duration=duration)
                        cursor.close()
                    except Exception as e:
                        log_error(e, error_type="DB_CONNECTION_LOST",
                                connection_id=id(dbapi_connection))
                        raise OperationalError("Database connection lost")

                @event.listens_for(db.session, 'after_commit')
                def receive_after_commit(session):
                    """Log successful commits with performance metrics"""
                    logger.info("Transaction committed",
                              session_id=id(session),
                              changes=len(session.dirty) + len(session.new))

                @event.listens_for(db.session, 'after_rollback')
                def receive_after_rollback(session):
                    """Log detailed rollback information"""
                    logger.warning("Transaction rolled back",
                                 session_id=id(session),
                                 pending_changes=len(session.dirty) + len(session.new))

                @event.listens_for(db.engine, 'before_cursor_execute')
                def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    conn.info.setdefault('query_start_time', []).append(datetime.utcnow())

                @event.listens_for(db.engine, 'after_cursor_execute')
                def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                    total_time = datetime.utcnow() - conn.info['query_start_time'].pop()
                    logger.debug("SQL Query executed",
                               duration=total_time.total_seconds(),
                               statement=statement[:200] + '...' if len(statement) > 200 else statement)

                # Verify connection
                db.engine.connect()
                logger.info("Database connection successful")

            except Exception as e:
                log_error(e, error_type="DB_INITIALIZATION_ERROR")
                raise

    except Exception as e:
        log_error(e, error_type="DB_CONFIG_ERROR")
        raise

@contextmanager
def transaction_context():
    """Context manager for database transactions with performance tracking"""
    start_time = datetime.utcnow()
    try:
        yield
        duration = (datetime.utcnow() - start_time).total_seconds()
        db.session.commit()
        logger.info("Transaction completed successfully", duration=duration)
    except SQLAlchemyError as e:
        db.session.rollback()
        duration = (datetime.utcnow() - start_time).total_seconds()
        log_error(e, error_type="DB_TRANSACTION_ERROR", duration=duration)
        raise
    except Exception as e:
        db.session.rollback()
        duration = (datetime.utcnow() - start_time).total_seconds()
        log_error(e, error_type="DB_UNEXPECTED_ERROR", duration=duration)
        raise

class DatabaseHealthCheck:
    """Database health monitoring with enhanced metrics"""

    @staticmethod
    def check_connection() -> tuple[bool, Optional[str]]:
        """Check database connection health with detailed diagnostics"""
        start_time = datetime.utcnow()
        try:
            with db.engine.connect() as conn:
                # Run comprehensive health check
                conn.execute(text("SELECT 1"))
                version = conn.execute(text("SELECT version()")).scalar()
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info("Database health check successful",
                          duration=duration,
                          version=version)
                return True, None
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            log_error(e, error_type="DB_HEALTH_CHECK_ERROR", duration=duration)
            return False, str(e)

    @staticmethod
    def get_connection_stats() -> dict:
        """Get detailed database connection pool statistics"""
        try:
            stats = {
                'pool_size': db.engine.pool.size(),
                'checkedin': db.engine.pool.checkedin(),
                'checkedout': db.engine.pool.checkedout(),
                'overflow': db.engine.pool.overflow(),
                'timeout': db.engine.pool._timeout,
                'recycle': db.engine.pool._recycle
            }
            logger.info("Database connection stats retrieved", **stats)
            return stats
        except Exception as e:
            log_error(e, error_type="DB_STATS_ERROR")
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