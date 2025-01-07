import logging
import logging.config
import traceback
from functools import wraps
from typing import Optional, Dict, Any, Mapping
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

        # Set up basic configuration
        logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)

        # Get root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if app.debug else logging.INFO)

        # File handler for detailed logging
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        file_handler.setLevel(logging.DEBUG)

        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

        # Clear any existing handlers
        logger.handlers = []

        # Add our handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        app.logger.handlers = []
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)

        # Test logging
        app.logger.info("Logging configured successfully")
        return True

    except Exception as e:
        print(f"Error configuring logging: {str(e)}")
        return False

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

def generate_error_id() -> str:
    """Generate a unique error ID"""
    return str(uuid.uuid4())

def log_error(error: Exception, error_type: str = "ERROR", include_trace: bool = True, **additional_data) -> Dict[str, Any]:
    """Log an error with context"""
    error_id = generate_error_id()
    error_data: Dict[str, Any] = {
        'id': error_id,
        'timestamp': datetime.utcnow().isoformat(),
        'type': error_type,
        'message': str(error),
        'error_class': error.__class__.__name__
    }

    if include_trace:
        error_data['traceback'] = traceback.format_exc()

    if additional_data:
        error_data.update(additional_data)

    if has_request_context():
        request_data: Dict[str, Any] = {
            'url': str(request.url),
            'method': str(request.method),
            'headers': dict(request.headers),
            'remote_addr': str(request.remote_addr)
        }
        error_data.update(request_data)

    logger = get_logger('app')
    logger.error(
        f"Error occurred: {error_type}",
        extra={'error_data': error_data}
    )

    return error_data