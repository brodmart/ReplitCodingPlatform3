import logging
import traceback
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, g, current_app, has_request_context
import json
from datetime import datetime
import uuid
import os
from logging import LogRecord

logger = logging.getLogger(__name__)

class SimpleFormatter(logging.Formatter):
    """Formateur simplifié pour les logs avec informations essentielles"""
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }

        # Ajouter le context de requête si disponible
        if has_request_context():
            try:
                log_data['request'] = {
                    'url': request.url,
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'ip': request.remote_addr
                }
            except Exception:
                pass

        # Ajouter la stack trace si disponible
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)

        # Ajouter les attributs supplémentaires du record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)

def generate_error_id() -> str:
    """Génère un identifiant unique pour chaque erreur"""
    return str(uuid.uuid4())

def log_error(error: Exception, error_type: str = "ERROR", include_trace: bool = True, **additional_data) -> Dict[str, Any]:
    """Log une erreur de manière structurée"""
    error_id = generate_error_id()
    error_data = {
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat(),
        "type": error_type,
        "message": str(error),
        "error_class": error.__class__.__name__
    }

    if include_trace:
        error_data["traceback"] = traceback.format_exc()

    # Ajouter le context de requête si disponible
    if has_request_context():
        try:
            error_data["request_info"] = {
                "endpoint": request.endpoint,
                "method": request.method,
                "path": request.path,
                "ip": request.remote_addr,
                "user_agent": str(request.user_agent)
            }
        except Exception:
            pass

    if additional_data:
        error_data.update({"additional_info": additional_data})

    logger.error(json.dumps(error_data))
    return error_data

def log_exception(error_type: str = "EXCEPTION"):
    """Décorateur pour logger automatiquement les exceptions"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_data = log_error(
                    e,
                    error_type=error_type,
                    function=f.__name__,
                    include_trace=True
                )
                logger.error(
                    f"Exception in {f.__name__}",
                    extra={
                        'error_id': error_data.get('error_id'),
                        'function': f.__name__,
                        'error_type': error_type
                    }
                )
                raise
        return wrapped
    return decorator

class StructuredLogger:
    """Logger personnalisé pour un format structuré"""
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(SimpleFormatter())
            self.logger.addHandler(handler)

    def _format_message(self, message: str, level: str, **kwargs) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "logger": self.name
        }

        if has_request_context():
            try:
                log_data["request"] = {
                    "url": request.url,
                    "method": request.method,
                    "endpoint": request.endpoint,
                    "ip": request.remote_addr
                }
            except Exception:
                pass

        if kwargs:
            log_data.update({"additional_info": kwargs})

        return json.dumps(log_data)

    def debug(self, message: str, **kwargs):
        self.logger.debug(self._format_message(message, "DEBUG", **kwargs))

    def info(self, message: str, **kwargs):
        self.logger.info(self._format_message(message, "INFO", **kwargs))

    def warning(self, message: str, **kwargs):
        self.logger.warning(self._format_message(message, "WARNING", **kwargs))

    def error(self, message: str, **kwargs):
        error_id = kwargs.pop('error_id', generate_error_id())
        self.logger.error(self._format_message(message, "ERROR", error_id=error_id, **kwargs))

    def critical(self, message: str, **kwargs):
        error_id = kwargs.pop('error_id', generate_error_id())
        self.logger.critical(self._format_message(message, "CRITICAL", error_id=error_id, **kwargs))

def get_logger(name: str) -> StructuredLogger:
    """Factory pour créer un nouveau logger structuré"""
    return StructuredLogger(name)