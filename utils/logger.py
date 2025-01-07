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
    """Formateur personnalisé pour la sortie JSON des logs avec contexte enrichi"""
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
            'thread': record.threadName,
            'process': record.process,
            'process_name': record.processName,
            'hostname': platform.node(),
            'environment': os.getenv('FLASK_ENV', 'development')
        }

        # Ajouter le context d'exécution
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'error_id'):
            log_data['error_id'] = record.error_id

        # Ajouter les informations de performance
        try:
            process = psutil.Process()
            log_data.update({
                'memory_usage': process.memory_info().rss / 1024 / 1024,  # MB
                'cpu_percent': process.cpu_percent(),
                'thread_count': len(process.threads()),
                'open_files': len(process.open_files()),
                'connections': len(process.connections())
            })
        except Exception:
            pass

        # Ajouter la stack trace si disponible
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)
            log_data['exc_type'] = record.exc_info[0].__name__
            log_data['exc_message'] = str(record.exc_info[1])
            log_data['stack_trace'] = ''.join(traceback.format_exception(*record.exc_info))

        # Ajouter le contexte de requête si disponible
        if has_request_context():
            try:
                log_data['request'] = {
                    'url': request.url,
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'ip': request.remote_addr,
                    'user_agent': str(request.user_agent),
                    'referrer': request.referrer,
                    'accept_languages': request.accept_languages.to_header(),
                    'content_length': request.content_length,
                    'content_type': request.content_type,
                    'is_secure': request.is_secure,
                    'host': request.host,
                    'request_id': getattr(g, 'request_id', str(uuid.uuid4())),
                }
                if 'user_id' in g:
                    log_data['request']['user_id'] = g.user_id
                if 'request_id' in g:
                    log_data['request']['request_id'] = g.request_id
            except Exception as e:
                log_data['request_context_error'] = str(e)

        # Ajouter les attributs supplémentaires du record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)

def generate_error_id() -> str:
    """Génère un identifiant unique pour chaque erreur"""
    return str(uuid.uuid4())

def get_system_info() -> Dict[str, Any]:
    """Collecte les informations système pertinentes"""
    try:
        process = psutil.Process()
        return {
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "memory_usage": process.memory_info().rss / 1024 / 1024,  # MB
            "cpu_percent": process.cpu_percent(),
            "thread_count": len(process.threads()),
            "open_files": len(process.open_files()),
            "connections": len(process.connections()),
            "uptime": datetime.now().timestamp() - process.create_time()
        }
    except Exception as e:
        return {"error_collecting_system_info": str(e)}

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
        "system_info": get_system_info(),
        "environment": os.getenv('FLASK_ENV', 'development'),
        "hostname": platform.node()
    }

    if include_trace:
        error_data["traceback"] = traceback.format_exc()
        error_data["stack_trace"] = ''.join(traceback.format_tb(error.__traceback__))

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
            "is_secure": request.is_secure,
            "accept_languages": request.accept_languages.to_header(),
            "content_length": request.content_length,
            "content_type": request.content_type,
            "host": request.host,
            "url": request.url,
            "base_url": request.base_url,
            "request_id": getattr(g, 'request_id', str(uuid.uuid4())),
            "referrer": request.referrer
        }
        error_data.update({"request_info": request_data})

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
                error_data = log_error(
                    e,
                    error_type=error_type,
                    function=f.__name__,
                    args=str(args),
                    kwargs=str(kwargs),
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
            "thread_id": threading.get_ident(),
            "hostname": platform.node(),
            "environment": os.getenv('FLASK_ENV', 'development')
        }

        # Add performance metrics
        try:
            process = psutil.Process()
            log_data.update({
                "memory_usage": process.memory_info().rss / 1024 / 1024,  # MB
                "cpu_percent": process.cpu_percent(),
                "thread_count": len(process.threads())
            })
        except Exception:
            pass

        # Only add request context information if we're in a request context
        if has_request_context():
            context_data = {
                "request_id": getattr(g, 'request_id', str(uuid.uuid4())),
                "user_id": getattr(g, 'user_id', None),
                "session_id": request.cookies.get('session', None),
                "url": request.url,
                "method": request.method,
                "endpoint": request.endpoint,
                "ip": request.remote_addr
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