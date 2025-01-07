import logging
import traceback
from functools import wraps
from flask import request, g, current_app, has_app_context
import json
from datetime import datetime

# Configure base logger
logger = logging.getLogger(__name__)

def log_error(error, error_type="ERROR", include_trace=True, **additional_data):
    """
    Log une erreur de manière structurée avec des informations contextuelles
    """
    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": error_type,
        "message": str(error)
    }

    # Only add request context information if we're in a request context
    if has_app_context():
        error_data.update({
            "endpoint": request.endpoint if request else None,
            "method": request.method if request else None,
            "path": request.path if request else None,
            "ip": request.remote_addr if request else None,
            "user_agent": str(request.user_agent) if request and request.user_agent else None,
            "request_duration": (datetime.utcnow() - g.request_start_time).total_seconds() if hasattr(g, 'request_start_time') else None
        })

    if include_trace:
        error_data["traceback"] = traceback.format_exc()

    if additional_data:
        error_data.update(additional_data)

    logger.error(json.dumps(error_data))
    return error_data

def log_exception(error_type="EXCEPTION"):
    """
    Décorateur pour logger automatiquement les exceptions
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                log_error(e, error_type=error_type)
                raise
        return wrapped
    return decorator

class StructuredLogger:
    """
    Logger personnalisé pour un format structuré
    """
    def __init__(self, name):
        self.logger = logging.getLogger(name)

    def _format_message(self, message, level, **kwargs):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "logger": self.logger.name
        }

        # Only add request context information if we're in a request context
        if has_app_context():
            log_data.update({
                "request_id": getattr(g, 'request_id', None),
                "user_id": getattr(g, 'user_id', None)
            })

        if kwargs:
            log_data.update(kwargs)
        return json.dumps(log_data)

    def debug(self, message, **kwargs):
        self.logger.debug(self._format_message(message, "DEBUG", **kwargs))

    def info(self, message, **kwargs):
        self.logger.info(self._format_message(message, "INFO", **kwargs))

    def warning(self, message, **kwargs):
        self.logger.warning(self._format_message(message, "WARNING", **kwargs))

    def error(self, message, **kwargs):
        self.logger.error(self._format_message(message, "ERROR", **kwargs))

    def critical(self, message, **kwargs):
        self.logger.critical(self._format_message(message, "CRITICAL", **kwargs))

def get_logger(name):
    """
    Factory pour créer un nouveau logger structuré
    """
    return StructuredLogger(name)