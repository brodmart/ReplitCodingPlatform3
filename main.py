import os
import logging
from app import app, logger

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    port = 5000  # Changed from 8080 to 5000
    logger.info(f"Starting Flask server on port {port}")
    app.run(
        host='0.0.0.0',  # Bind to all interfaces
        port=port,
        debug=True,
        threaded=True    # Enable threading for better request handling
    )