import logging
import os
import socket
from app import app

def find_free_port(start_port=5000, max_port=5100):
    """Find a free port starting from start_port"""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find a free port")

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', find_free_port()))
        logging.info(f"Starting Flask server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=True)
    except Exception as e:
        logging.error(f"Failed to start Flask server: {e}", exc_info=True)
        raise