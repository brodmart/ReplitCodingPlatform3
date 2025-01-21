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

# Performance tuning constants
MAX_COMPILATION_TIME = 30  # Increased from 10 to 30 seconds for large files
MAX_EXECUTION_TIME = 15    # Execution timeout remains at 15 seconds
MEMORY_LIMIT = 512        # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"

class CompilationTimeout(Exception):
    """Raised when compilation exceeds time limit"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with enhanced timeout handling for large files.
    """
    start_time = time.time()
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        # Create compiler cache directory if it doesn't exist
        os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'csharp':
                source_file = os.path.join(temp_dir, "program.cs")
                executable = os.path.join(temp_dir, "program.exe")

                logger.debug(f"Writing code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Enhanced compilation command with optimization flags
                compile_cmd = [
                    'mcs',
                    '-optimize+',
                    '-debug-',
                    '-unsafe+',
                    '-langversion:latest',
                    '-parallel+',
                    '-warnaserror-',
                    '-nowarn:219,414',
                    str(source_file),
                    '-out:' + str(executable)
                ]

                logger.debug("Starting C# compilation with enhanced settings")
                compile_start = time.time()

                try:
                    logger.debug("Executing compilation command")
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_COMPILATION_TIME,
                        env={
                            'MONO_GC_PARAMS': 'max-heap-size=512M',
                            'MONO_THREADS_PER_CPU': '2',
                            'PATH': os.environ['PATH']
                        }
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

                    # Execute with optimized Mono runtime settings
                    run_cmd = ['mono', executable]
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        env={
                            'MONO_GC_PARAMS': 'major=marksweep-par,nursery-size=64m',
                            'MONO_THREADS_PER_CPU': '2',
                            'MONO_MIN_HEAP_SIZE': '128M',
                            'MONO_MAX_HEAP_SIZE': f'{MEMORY_LIMIT}M'
                        }
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
                    phase = "compilation" if elapsed_time < MAX_COMPILATION_TIME else "execution"
                    logger.error(f"{phase.capitalize()} timed out after {elapsed_time:.2f}s")
                    return {
                        'success': False,
                        'error': f"{phase.capitalize()} timed out after {elapsed_time:.2f} seconds. For large files, try breaking down the code into smaller functions.",
                        'metrics': {
                            'time_elapsed': elapsed_time
                        }
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