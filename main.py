import os
import logging
from app import app, logger
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
        # Import models to ensure tables are created
        with app.app_context():
            from models import db
            db.create_all()

        return app

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

if __name__ == '__main__':
    app = init_app()
    port = int(os.environ.get('PORT', 8080)) #Changed port here.
    logger.info(f"Starting Flask server on port {port}")
    app.run(
        host='0.0.0.0',  # Bind to all interfaces
        port=8080,
        debug=True,
        threaded=True    # Enable threading for better request handling
    )