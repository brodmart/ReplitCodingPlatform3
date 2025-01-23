import os
import logging
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy with a custom base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()

def create_app():
    """Application factory function"""
    app = Flask(__name__)

    # Configure the Flask application
    app.config.update({
        'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_development_only'),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': 5,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        }
    })

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models here to ensure they're registered with SQLAlchemy
    with app.app_context():
        from models.student import Student  # Import other models as needed
        from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    # Basic route for testing
    @app.route('/')
    def index():
        return jsonify({
            'status': 'success',
            'message': 'Ontario Secondary Computer Science Curriculum Educational Platform',
            'version': '1.0'
        })

    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)