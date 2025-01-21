"""
Compiler service for code execution and testing.
"""
import subprocess
import tempfile
import os
import logging
import traceback
import signal
from typing import Dict, Optional, Any
from pathlib import Path
import psutil
import time
from threading import Thread, Event

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CompilationTimeout(Exception):
    """Raised when compilation exceeds time limit"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with strict timeouts and process management.
    """
    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        logger.debug(f"Attempting to compile and run {language} code")
        logger.debug(f"Code length: {len(code)} characters")

        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'csharp':
                source_file = os.path.join(temp_dir, "program.cs")
                executable = os.path.join(temp_dir, "program.exe")

                # Write code to file
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile with strict timeout
                compile_cmd = [
                    'mcs',
                    '-optimize+',
                    '-debug-',
                    source_file,
                    '-out:' + executable
                ]

                try:
                    # Use timeout parameter directly in check_output
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10  # Strict 10 second timeout
                    )

                    if compile_process.returncode != 0:
                        logger.error(f"Compilation failed: {compile_process.stderr}")
                        return {
                            'success': False,
                            'error': compile_process.stderr
                        }

                    # Set execute permission
                    os.chmod(executable, 0o755)

                    # Run with strict timeout
                    run_cmd = ['mono', executable]
                    run_process = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=5  # Strict 5 second timeout
                    )

                    return {
                        'success': run_process.returncode == 0,
                        'output': run_process.stdout,
                        'error': run_process.stderr if run_process.returncode != 0 else None
                    }

                except subprocess.TimeoutExpired as e:
                    logger.error("Process timed out")
                    return {
                        'success': False,
                        'error': "Compilation or execution timed out. Check for infinite loops."
                    }

                except Exception as e:
                    logger.error(f"Compilation/execution error: {str(e)}")
                    return {
                        'success': False,
                        'error': str(e)
                    }

            else:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"An unexpected error occurred: {str(e)}"
        }