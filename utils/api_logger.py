"""
Centralized logging utilities for the API
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

def log_api_request(start_time: float, client_ip: str, endpoint: str, status_code: int, error: Optional[str] = None):
    """Log API request details"""
    duration = round((time.time() - start_time) * 1000, 2)  # Duration in milliseconds
    logger.info(f"""
    API Request Details:
    - Client IP: {client_ip}
    - Endpoint: {endpoint}
    - Duration: {duration}ms
    - Status: {status_code}
    {f'- Error: {error}' if error else ''}
    """)
