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
        # Use port 80 consistently for both development and production
        port = 80
        logger.info(f"Starting Flask server on port {port}")

        # Configure server for interactive I/O
        app.config['PROPAGATE_EXCEPTIONS'] = True
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
        app.config['TEMPLATES_AUTO_RELOAD'] = True

        # Enable session support for managing interactive sessions
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_PERMANENT'] = False

        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True,
            use_reloader=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}", exc_info=True)
        raise