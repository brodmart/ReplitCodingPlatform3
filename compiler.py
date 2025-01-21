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
    start_time = time.time()
    logger.debug("Starting compile_and_run")

    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        logger.debug(f"Processing {language} code, length: {len(code)}")

        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'csharp':
                source_file = os.path.join(temp_dir, "program.cs")
                executable = os.path.join(temp_dir, "program.exe")

                logger.debug(f"Writing code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile with strict timeout using subprocess.run
                compile_cmd = [
                    'mcs',
                    '-optimize+',
                    '-debug-',
                    source_file,
                    '-out:' + executable
                ]

                logger.debug("Starting compilation")
                compile_start = time.time()

                try:
                    # Use subprocess.run with timeout
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10  # 10 second timeout
                    )

                    compile_time = time.time() - compile_start
                    logger.debug(f"Compilation completed in {compile_time:.2f}s")

                    if compile_process.returncode != 0:
                        logger.error(f"Compilation failed: {compile_process.stderr}")
                        return {
                            'success': False,
                            'error': compile_process.stderr,
                            'metrics': {
                                'compilation_time': compile_time
                            }
                        }

                    logger.debug("Compilation successful, preparing execution")
                    os.chmod(executable, 0o755)

                    # Run with timeout
                    run_cmd = ['mono', executable]
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=5  # 5 second timeout
                    )

                    run_time = time.time() - run_start
                    total_time = time.time() - start_time

                    logger.debug(f"Execution completed in {run_time:.2f}s")
                    logger.debug(f"Total processing time: {total_time:.2f}s")

                    return {
                        'success': run_process.returncode == 0,
                        'output': run_process.stdout,
                        'error': run_process.stderr if run_process.returncode != 0 else None,
                        'metrics': {
                            'compilation_time': compile_time,
                            'execution_time': run_time,
                            'total_time': total_time
                        }
                    }

                except subprocess.TimeoutExpired as e:
                    elapsed_time = time.time() - start_time
                    logger.error(f"Process timed out after {elapsed_time:.2f}s")
                    return {
                        'success': False,
                        'error': "Compilation or execution timed out. Check for infinite loops.",
                        'metrics': {
                            'time_elapsed': elapsed_time
                        }
                    }

                except Exception as e:
                    logger.error(f"Error during compilation/execution: {str(e)}", exc_info=True)
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