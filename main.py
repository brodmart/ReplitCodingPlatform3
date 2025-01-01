import os
import logging
from app import app, logger
from flask import Flask
from database import init_db
from extensions import init_extensions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def init_app():
    """Initialize the application"""
    try:
        # Initialize database
        init_db(app)

        # Initialize extensions
        init_extensions(app)

        # Import and register blueprints
        from routes.auth import auth_blueprint
        from routes.activities import activities_blueprint

        app.register_blueprint(auth_blueprint)
        app.register_blueprint(activities_blueprint)

        # Import models and create tables
        with app.app_context():
            from models import db
            db.create_all()

        return app

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

if __name__ == '__main__':
    app = init_app()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)