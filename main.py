import logging
import os
from app import app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.getcwd(), 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
            os.chmod(temp_dir, 0o755)

        # Ensure the port is set and valid
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting Flask server on port {port}")

        # Start the Flask application with proper host binding
        app.run(
            host='0.0.0.0',  # Bind to all interfaces
            port=port,
            debug=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}", exc_info=True)
        raise