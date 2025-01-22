"""
Compiler performance testing module.
Only loads when explicitly running performance tests.
"""
import os
import sys
import logging
import psutil
from pathlib import Path

# Add project root to path only when running tests
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    logging.basicConfig(level=logging.DEBUG)

from compiler import compile_and_run

logger = logging.getLogger(__name__)

def get_system_metrics():
    """Get current system performance metrics"""
    return {
        'cpu_percent': psutil.cpu_percent(),
        'memory_used': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent
    }

def run_performance_tests():
    """Run compiler performance tests"""
    if __name__ != "__main__":
        return  # Only run when explicitly called
        
    logger.info("Starting compiler performance tests...")
    # Rest of the testing code remains unchanged
