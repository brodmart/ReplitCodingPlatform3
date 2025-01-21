"""
Compiler service for code execution and testing.
"""
import subprocess
import tempfile
import os
import logging
import traceback
from typing import Dict, Optional, Any
from compiler_service import compile_and_run as service_compile_and_run

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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
    if not code or not language:
        logger.error("Invalid input parameters: code or language is missing")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        logger.debug(f"Attempting to compile and run {language} code")
        logger.debug(f"Code length: {len(code)} characters")
        logger.debug(f"Code content:\n{code}")

        result = service_compile_and_run(code, language, input_data)

        logger.debug(f"Compilation result: {result}")

        if not result.get('success', False):
            logger.error(f"Compilation/execution failed: {result.get('error', 'Unknown error')}")
            logger.error(f"Full result: {result}")

        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"Execution timeout: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': "Code execution timed out. Check for infinite loops."
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Process error: {str(e)}, Output: {e.output}")
        return {
            'success': False,
            'output': '',
            'error': f"Process error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error in compile_and_run: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'output': '',
            'error': "Code execution service encountered an error. Please try again."
        }