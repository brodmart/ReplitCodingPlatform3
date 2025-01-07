import logging
import traceback
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, g, current_app, has_request_context
import json
from datetime import datetime
import uuid
import platform
import psutil
import os
import threading

# Configure base logger
logger = logging.getLogger(__name__)

class JsonFormatter(logging.Formatter):
    """Formateur personnalisé pour la sortie JSON des logs"""
    def format(self, record):
        # Récupérer les attributs standard du record
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
            'thread': record.threadName,
            'process': record.process
        }

        # Ajouter les attributs supplémentaires s'ils existent
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)

        # Si le message est déjà du JSON, le parser
        try:
            if isinstance(record.msg, str):
                message_data = json.loads(record.msg)
                if isinstance(message_data, dict):
                    log_data.update(message_data)
        except (json.JSONDecodeError, TypeError):
            pass

        return json.dumps(log_data)

def generate_error_id() -> str:
    """Génère un identifiant unique pour chaque erreur"""
    return str(uuid.uuid4())

def get_system_info() -> Dict[str, Any]:
    """Collecte les informations système pertinentes"""
    return {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024,  # MB
        "cpu_percent": psutil.Process().cpu_percent()
    }

def log_error(error: Exception, error_type: str = "ERROR", include_trace: bool = True, **additional_data) -> Dict[str, Any]:
    """
    Log une erreur de manière structurée avec des informations contextuelles enrichies
    """
    error_id = generate_error_id()
    error_data = {
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat(),
        "type": error_type,
        "message": str(error),
        "error_class": error.__class__.__name__,
        "system_info": get_system_info()
    }

    # Only add request context information if we're in a request context
    if has_request_context():
        request_data = {
            "endpoint": request.endpoint,
            "method": request.method,
            "path": request.path,
            "ip": request.remote_addr,
            "user_agent": str(request.user_agent) if request.user_agent else None,
            "request_duration": (datetime.utcnow() - g.request_start_time).total_seconds() if hasattr(g, 'request_start_time') else None,
            "headers": dict(request.headers),
            "query_string": request.query_string.decode('utf-8'),
            "is_xhr": request.is_xhr,
            "is_secure": request.is_secure
        }
        error_data.update({"request_info": request_data})

    if include_trace:
        error_data["traceback"] = traceback.format_exc()

    if additional_data:
        error_data.update({"additional_info": additional_data})

    logger.error(json.dumps(error_data))
    return error_data

def log_exception(error_type: str = "EXCEPTION"):
    """
    Décorateur pour logger automatiquement les exceptions avec contexte enrichi
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_data = log_error(e, error_type=error_type, function=f.__name__, args=str(args), kwargs=str(kwargs))
                logger.error(f"Exception in {f.__name__}",
                           extra={
                               'error_id': error_data.get('id'),
                               'function': f.__name__
                           })
                raise
        return wrapped
    return decorator

class StructuredLogger:
    """
    Logger personnalisé pour un format structuré avec contexte enrichi
    """
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

        # Ensure at least one handler exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)

    def _format_message(self, message: str, level: str, **kwargs) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "logger": self.name,
            "process_id": os.getpid(),
            "thread_id": threading.get_ident()
        }

        # Only add request context information if we're in a request context
        if has_request_context():
            context_data = {
                "request_id": getattr(g, 'request_id', None),
                "user_id": getattr(g, 'user_id', None),
                "session_id": request.cookies.get('session', None)
            }
            log_data.update({"request_context": context_data})

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
    """
    Factory pour créer un nouveau logger structuré
    """
    return StructuredLogger(name)