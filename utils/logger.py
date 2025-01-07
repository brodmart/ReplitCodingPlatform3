import logging
import traceback
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, g, current_app, has_request_context
import json
from datetime import datetime
import uuid
import os
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """Configure le logging pour l'application"""
    try:
        # Create logs directory if it doesn't exist
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Basic formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

        # File handlers
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # Clear any existing handlers
        app.logger.handlers = []

        # Add handlers
        app.logger.addHandler(console_handler)
        app.logger.addHandler(file_handler)

        # Set level
        app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)

        return True

    except Exception as e:
        print(f"Error configuring logging: {str(e)}")
        logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)
        return False

def get_logger(name: str):
    """Get a logger instance"""
    return logging.getLogger(name)

def generate_error_id() -> str:
    """Generate a unique error ID"""
    return str(uuid.uuid4())

def log_error(error: Exception, error_type: str = "ERROR", include_trace: bool = True, **additional_data) -> Dict[str, Any]:
    """Log an error with context"""
    error_id = generate_error_id()
    error_data = {
        'error_id': error_id,
        'timestamp': datetime.utcnow().isoformat(),
        'type': error_type,
        'message': str(error),
        'error_class': error.__class__.__name__
    }

    if include_trace:
        error_data['traceback'] = traceback.format_exc()

    if additional_data:
        error_data.update(additional_data)

    logging.getLogger('app').error(
        f"Error occurred: {error_type}",
        extra={'error_data': error_data}
    )

    return error_data