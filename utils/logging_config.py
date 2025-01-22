import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path

def setup_logging(name='app', log_level=logging.DEBUG):
    """Configure comprehensive logging for the application"""
    
    # Ensure logs directory exists
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Generate datestamped log file name
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Detailed log format with module name and line number
    detailed_formatter = {
        'format': '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    }
    
    # Basic format for console output
    basic_formatter = {
        'format': '%(levelname)s - %(message)s'
    }
    
    # Logging configuration dictionary
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': detailed_formatter,
            'basic': basic_formatter
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'basic',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': str(log_file),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'filename': str(log_dir / f'error_{name}.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            }
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': True
            },
            'socketio': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            },
            'compiler': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            },
            'database': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    return logging.getLogger(name)
