import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from .logging_config import setup_logging

# Initialize logger with our configuration
logger = setup_logging('compiler')

class CompilerLogger:
    """Handles logging for C# compiler service"""

    def __init__(self):
        self.log_dir = Path('logs/compiler')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    def debug(self, message: str, *args, **kwargs):
        """Forward debug messages to logger"""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """Forward info messages to logger"""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """Forward warning messages to logger"""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """Forward error messages to logger"""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """Forward critical messages to logger"""
        self.logger.critical(message, *args, **kwargs)

    def log_compilation_start(self, session_id: str, code: str) -> None:
        """Log compilation start event"""
        self.logger.info(f"Starting compilation for session {session_id}")
        self._log_event(session_id, 'compilation_start', {
            'code_length': len(code),
            'timestamp': datetime.utcnow().isoformat()
        })

    def log_compilation_error(self, session_id: str, error: Exception, context: Dict[str, Any]) -> None:
        """Log compilation error with context"""
        self.logger.error(f"Compilation error in session {session_id}: {str(error)}")
        self._log_event(session_id, 'compilation_error', {
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        })

    def log_runtime_error(self, session_id: str, error: str, context: Dict[str, Any]) -> None:
        """Log runtime errors during program execution"""
        self.logger.error(f"Runtime error in session {session_id}: {error}")
        self._log_event(session_id, 'runtime_error', {
            'error_message': error,
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        })

    def log_execution_state(self, session_id: str, state: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log program execution state changes"""
        self.logger.info(f"Session {session_id} state changed to: {state}")
        self._log_event(session_id, 'execution_state', {
            'state': state,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def _log_event(self, session_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Write structured log entry to session log file"""
        log_file = self.log_dir / f"session_{session_id}.json"

        try:
            existing_logs = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    existing_logs = json.load(f)

            if not isinstance(existing_logs, list):
                existing_logs = []

            log_entry = {
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }

            existing_logs.append(log_entry)

            with open(log_file, 'w') as f:
                json.dump(existing_logs, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error writing to log file: {str(e)}")

    def analyze_session_errors(self, session_id: str) -> Dict[str, Any]:
        """Analyze errors for a specific session"""
        try:
            log_file = self.log_dir / f"session_{session_id}.json"
            if not log_file.exists():
                return {'error_count': 0, 'patterns': []}

            with open(log_file, 'r') as f:
                logs = json.load(f)

            error_events = [
                log for log in logs 
                if log['event_type'] in ('compilation_error', 'runtime_error')
            ]

            error_patterns = {}
            for error in error_events:
                error_type = error['data'].get('error_type', 'unknown')
                if error_type not in error_patterns:
                    error_patterns[error_type] = 0
                error_patterns[error_type] += 1

            return {
                'error_count': len(error_events),
                'patterns': [
                    {'type': k, 'count': v}
                    for k, v in error_patterns.items()
                ],
                'timeline': [
                    {
                        'timestamp': error['timestamp'],
                        'type': error['event_type'],
                        'message': error['data'].get('error_message')
                    }
                    for error in error_events
                ]
            }

        except Exception as e:
            self.logger.error(f"Error analyzing session logs: {str(e)}")
            return {'error': str(e)}

# Global compiler logger instance
compiler_logger = CompilerLogger()