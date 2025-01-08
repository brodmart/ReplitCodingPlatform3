import os
import logging
from app import app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        port = 80  # Changed back to 80 for Replit deployment
        logger.info(f"Starting Flask server on port {port}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}", exc_info=True)
        raise