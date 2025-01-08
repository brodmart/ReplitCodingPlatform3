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
        # Use port 5000 for Flask development server
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting Flask server on port {port}")

        app.config['PROPAGATE_EXCEPTIONS'] = True
        app.config['TEMPLATES_AUTO_RELOAD'] = True

        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}", exc_info=True)
        raise