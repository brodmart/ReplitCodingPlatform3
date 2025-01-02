"""
Compiler service for code execution and testing.
"""
import subprocess
import tempfile
import os
import logging
from typing import Dict, Optional, Any
from compiler_service import compile_and_run as service_compile_and_run

logger = logging.getLogger(__name__)

class CompilerError(Exception):
    """Raised when compilation fails"""
    pass

class ExecutionError(Exception):
    """Raised when execution fails"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code for testing purposes.
    This is a wrapper around the more detailed compiler_service implementation.
    """
    try:
        return service_compile_and_run(code, language, input_data)
    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': f"Une erreur s'est produite lors de l'exécution: {str(e)}"
        }