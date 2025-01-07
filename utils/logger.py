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
from logging import LogRecord

logger = logging.getLogger(__name__)

class DetailedFormatter(logging.Formatter):
    """Formateur amélioré pour les logs avec informations détaillées"""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process
        }

        # Ajouter le context de requête si disponible
        if has_request_context():
            try:
                log_data['request'] = {
                    'url': request.url,
                    'method': request.method,
                    'endpoint': request.endpoint,
                    'ip': request.remote_addr,
                    'user_agent': str(request.user_agent),
                    'referrer': request.referrer,
                    'path': request.path,
                    'query_string': request.query_string.decode('utf-8') if request.query_string else '',
                    'host': request.host
                }
            except Exception as e:
                log_data['request_error'] = str(e)

        # Ajouter la stack trace si disponible
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)

        # Ajouter les attributs supplémentaires du record
        extra_attrs = getattr(record, 'extra_data', {})
        if extra_attrs:
            log_data['extra'] = extra_attrs

        try:
            return json.dumps(log_data)
        except Exception as e:
            return json.dumps({
                'timestamp': self.formatTime(record),
                'name': record.name,
                'level': record.levelname,
                'message': record.getMessage(),
                'error': f'Error formatting log: {str(e)}'
            })

def setup_logging(app):
    """Configure le logging pour l'application"""
    try:
        # Créer le dossier logs s'il n'existe pas
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Configurer le formateur
        formatter = DetailedFormatter()

        # Configurer le handler de console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

        # Configurer les handlers de fichier
        handlers = {
            'error': RotatingFileHandler(
                os.path.join(log_dir, 'error.log'),
                maxBytes=10485760,
                backupCount=5,
                encoding='utf-8'
            ),
            'access': RotatingFileHandler(
                os.path.join(log_dir, 'access.log'),
                maxBytes=10485760,
                backupCount=5,
                encoding='utf-8'
            )
        }

        # Configurer les niveaux
        handlers['error'].setLevel(logging.ERROR)
        handlers['access'].setLevel(logging.INFO)

        # Appliquer le formateur
        for handler in handlers.values():
            handler.setFormatter(formatter)

        # Configurer le logger principal
        app.logger.handlers = []
        app.logger.addHandler(console_handler)
        for handler in handlers.values():
            app.logger.addHandler(handler)

        app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
        return True

    except Exception as e:
        print(f"Erreur lors de la configuration du logging: {str(e)}")
        logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)
        return False

class StructuredLogger:
    """Logger personnalisé pour un format structuré avec support amélioré des erreurs"""
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Méthode interne pour la journalisation"""
        log_data = {
            'message': message,
            'logger': self.name,
            'level': level,
            'timestamp': datetime.utcnow().isoformat()
        }

        if kwargs:
            log_data['context'] = kwargs

        self.logger.log(
            getattr(logging, level),
            json.dumps(log_data)
        )

    def debug(self, message: str, **kwargs):
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        error_id = kwargs.pop('error_id', generate_error_id())
        self._log('ERROR', message, error_id=error_id, **kwargs)

    def critical(self, message: str, **kwargs):
        error_id = kwargs.pop('error_id', generate_error_id())
        self._log('CRITICAL', message, error_id=error_id, **kwargs)

def get_logger(name: str) -> StructuredLogger:
    """Factory pour créer un nouveau logger structuré"""
    return StructuredLogger(name)

def generate_error_id() -> str:
    """Génère un identifiant unique pour chaque erreur"""
    return str(uuid.uuid4())

def log_error(error: Exception, error_type: str = "ERROR", include_trace: bool = True, **additional_data) -> Dict[str, Any]:
    """Log une erreur de manière structurée avec plus de contexte"""
    error_id = generate_error_id()
    error_data = {
        'error_id': error_id,
        'timestamp': datetime.utcnow().isoformat(),
        'type': error_type,
        'message': str(error),
        'error_class': error.__class__.__name__,
        'module': error.__class__.__module__
    }

    if include_trace:
        error_data['traceback'] = traceback.format_exc()

    if additional_data:
        error_data['additional_info'] = additional_data

    logger.error(json.dumps(error_data))
    return error_data