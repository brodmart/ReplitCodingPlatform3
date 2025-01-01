
import os
import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the custom base class
db = SQLAlchemy(model_class=Base)

def init_db(app, max_retries=3):
    """Initialize database with application context and retry logic"""
    logger.info("Configuring database connection...")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set!")
        raise RuntimeError("DATABASE_URL must be set")

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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
        for attempt in range(max_retries):
            try:
                db.engine.connect()
                logger.info("Database connection successful")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying...")
