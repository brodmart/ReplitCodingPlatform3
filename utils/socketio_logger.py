import logging
import time
from functools import wraps
from flask import current_app
from datetime import datetime
from .logging_config import setup_logging

# Initialize logger with our new configuration
logger = setup_logging('socketio')

class SocketIOMetrics:
    def __init__(self):
        self.connections = 0
        self.active_sessions = set()
        self.events_processed = 0
        self.errors = 0
        self.start_time = time.time()
        self.event_timings = {}
        self.error_details = []  # Track detailed error information

    def track_event(self, event_name, duration, context=None):
        """Track event with enhanced context"""
        if event_name not in self.event_timings:
            self.event_timings[event_name] = []
        self.event_timings[event_name].append({
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        })
        self.events_processed += 1
        logger.debug(f"Event tracked: {event_name}, Duration: {duration:.3f}s, Context: {context}")

    def track_error(self, event_name, error, context=None):
        """Track detailed error information"""
        error_detail = {
            'event': event_name,
            'error': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        self.error_details.append(error_detail)
        self.errors += 1
        logger.error(f"Socket.IO error in {event_name}: {error}", exc_info=True)

    def get_stats(self):
        """Get enhanced statistics including error details"""
        uptime = time.time() - self.start_time
        avg_timings = {
            event: {
                'avg_duration': sum(t['duration'] for t in times)/len(times),
                'count': len(times),
                'last_event': times[-1] if times else None
            }
            for event, times in self.event_timings.items()
        }

        return {
            'uptime': uptime,
            'total_connections': self.connections,
            'active_sessions': len(self.active_sessions),
            'events_processed': self.events_processed,
            'errors': {
                'count': self.errors,
                'recent': self.error_details[-5:] if self.error_details else []
            },
            'average_event_timings': avg_timings
        }

# Global metrics instance
metrics = SocketIOMetrics()

def log_socket_event(func):
    """Enhanced decorator to log Socket.IO events with detailed context"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        event_name = func.__name__
        start_time = time.time()
        context = {
            'args': str(args),
            'kwargs': str(kwargs)
        }

        try:
            logger.debug(f"Socket.IO event {event_name} started at {datetime.now()}")
            logger.debug(f"Event context: {context}")

            result = func(*args, **kwargs)

            duration = time.time() - start_time
            metrics.track_event(event_name, duration, context)

            logger.debug(f"Socket.IO event {event_name} completed in {duration:.3f}s")
            logger.debug(f"Event result: {result}")
            return result

        except Exception as e:
            duration = time.time() - start_time
            metrics.track_error(event_name, e, context)
            logger.exception(f"Error in Socket.IO event {event_name} after {duration:.3f}s: {str(e)}")
            raise

    return wrapper

def track_connection(connected=True, client_info=None):
    """Enhanced connection tracking with client information"""
    if connected:
        metrics.connections += 1
        logger.info(f"New connection established. Total connections: {metrics.connections}")
        if client_info:
            logger.debug(f"Client info: {client_info}")
    else:
        metrics.connections = max(0, metrics.connections - 1)
        logger.info(f"Connection closed. Remaining connections: {metrics.connections}")

def track_session(session_id, active=True, context=None):
    """Enhanced session tracking with context"""
    if active:
        metrics.active_sessions.add(session_id)
        logger.info(f"Session {session_id} activated. Total active sessions: {len(metrics.active_sessions)}")
        if context:
            logger.debug(f"Session context: {context}")
    else:
        metrics.active_sessions.discard(session_id)
        logger.info(f"Session {session_id} deactivated. Remaining active sessions: {len(metrics.active_sessions)}")

def get_current_metrics():
    """Get current Socket.IO metrics with enhanced error reporting"""
    stats = metrics.get_stats()
    logger.debug(f"Current metrics: {stats}")
    return stats

def log_error(error_type, message, context=None):
    """Utility function to log errors with context"""
    logger.error(f"{error_type}: {message}", extra={'context': context}, exc_info=True)
    metrics.track_error(error_type, message, context)