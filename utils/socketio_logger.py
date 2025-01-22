import logging
import time
from functools import wraps
from flask import current_app
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SocketIOMetrics:
    def __init__(self):
        self.connections = 0
        self.active_sessions = set()
        self.events_processed = 0
        self.errors = 0
        self.start_time = time.time()
        self.event_timings = {}
        
    def track_event(self, event_name, duration):
        if event_name not in self.event_timings:
            self.event_timings[event_name] = []
        self.event_timings[event_name].append(duration)
        self.events_processed += 1
        
    def get_stats(self):
        uptime = time.time() - self.start_time
        avg_timings = {
            event: sum(times)/len(times) if times else 0 
            for event, times in self.event_timings.items()
        }
        return {
            'uptime': uptime,
            'total_connections': self.connections,
            'active_sessions': len(self.active_sessions),
            'events_processed': self.events_processed,
            'errors': self.errors,
            'average_event_timings': avg_timings
        }

# Global metrics instance
metrics = SocketIOMetrics()

def log_socket_event(func):
    """Decorator to log Socket.IO events with timing and metrics."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        event_name = func.__name__
        start_time = time.time()

        try:
            logger.debug(f"Socket.IO event {event_name} started at {datetime.now()}")
            logger.debug(f"Event parameters: args={args}, kwargs={kwargs}")

            result = func(*args, **kwargs)

            duration = time.time() - start_time
            metrics.track_event(event_name, duration)

            logger.debug(f"Socket.IO event {event_name} completed in {duration:.3f}s")
            logger.debug(f"Event result: {result}")
            return result

        except Exception as e:
            metrics.errors += 1
            logger.error(f"Error in Socket.IO event {event_name}: {str(e)}", exc_info=True)
            raise

    return wrapper

def track_connection(connected=True):
    """Track Socket.IO connection metrics."""
    if connected:
        metrics.connections += 1
        logger.info(f"New connection established. Total connections: {metrics.connections}")
    else:
        metrics.connections = max(0, metrics.connections - 1)
        logger.info(f"Connection closed. Remaining connections: {metrics.connections}")

def track_session(session_id, active=True):
    """Track active Socket.IO sessions."""
    if active:
        metrics.active_sessions.add(session_id)
        logger.info(f"Session {session_id} activated. Total active sessions: {len(metrics.active_sessions)}")
    else:
        metrics.active_sessions.discard(session_id)
        logger.info(f"Session {session_id} deactivated. Remaining active sessions: {len(metrics.active_sessions)}")

def get_current_metrics():
    """Get current Socket.IO metrics."""
    return metrics.get_stats()