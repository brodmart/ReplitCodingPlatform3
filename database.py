import os
import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from contextlib import contextmanager

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

        # Configure SQLAlchemy with minimal settings
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'pool_recycle': 1800
        }

        # Initialize the db with the Flask app
        db.init_app(app)

        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

@contextmanager
def transaction_context():
    """Simple context manager for database transactions"""
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction error: {str(e)}")
        raise