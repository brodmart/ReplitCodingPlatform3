"""
Compiler service for code execution and testing.
Advanced memory management and resource monitoring.
"""
import subprocess
import tempfile
import os
import logging
import signal
import resource
import errno
from pathlib import Path
import re
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager
import queue
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import psutil

logger = logging.getLogger(__name__)

@dataclass
class CompilerMetrics:
    """Detailed metrics for compiler performance"""
    language: str
    compilation_time: float
    execution_time: float
    memory_used: float
    peak_memory: float
    error_type: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    client_info: Optional[Dict[str, str]] = None
    timestamp: datetime = datetime.now()

class MonitoringSystem:
    """Enhanced monitoring system for compiler performance and resource usage"""
    def __init__(self):
        self.metrics_window = 3600  # 1 hour window for metrics
        self.metrics: List[CompilerMetrics] = []
        self.error_patterns = defaultdict(list)
        self._lock = threading.Lock()

    def add_metric(self, metric: CompilerMetrics):
        """Add new compilation metric with enhanced tracking"""
        with self._lock:
            current_time = datetime.now()
            # Clean old metrics
            self.metrics = [m for m in self.metrics 
                          if (current_time - m.timestamp).total_seconds() < self.metrics_window]
            self.metrics.append(metric)

class CompilerError(Exception):
    """Custom exception for compiler-related errors"""
    pass

class ExecutionError(Exception):
    """Custom exception for execution-related errors"""
    pass

class MemoryLimitExceeded(ExecutionError):
    """Custom exception for memory limit violations"""
    pass

class TimeoutError(ExecutionError):
    """Custom exception for execution timeout"""
    pass

def set_resource_limits():
    """Set process resource limits"""
    try:
        # Set memory limit (100MB)
        resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, -1))
        # Set CPU time limit (5 seconds)
        resource.setrlimit(resource.RLIMIT_CPU, (5, -1))
        # Set process priority
        os.nice(10)
    except Exception as e:
        logger.warning(f"Failed to set resource limits: {e}")

class RequestQueue:
    """Manages code execution requests with enhanced memory management"""
    def __init__(self, max_workers: int = 2):
        self.queue = queue.Queue()
        self.max_workers = max_workers
        self._shutdown = threading.Event()
        self.monitor = MonitoringSystem()
        self.workers = []
        self.start_workers()

    def execute_code(self, code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Execute code with strict resource limits"""
        start_time = time.time()
        try:
            if language == 'cpp':
                result = self._compile_and_run_cpp(code, input_data)
            else:
                result = self._compile_and_run_csharp(code, input_data)

            # Get memory statistics
            process = psutil.Process()
            memory_info = process.memory_info()
            result.update({
                'memory_usage': memory_info.rss / (1024 * 1024),  # MB
                'peak_memory': memory_info.vms / (1024 * 1024)    # MB
            })

            return result

        except Exception as e:
            logger.error(f"Error executing {language} code: {e}", exc_info=True)
            return {
                'success': False,
                'output': '',
                'error': f"Erreur d'exécution: {str(e)}",
                'memory_usage': 0.0,
                'peak_memory': 0.0
            }
        finally:
            logger.info(f"Code execution took {time.time() - start_time:.2f} seconds")

    def _worker_loop(self):
        """Worker thread main loop"""
        while not self._shutdown.is_set():
            try:
                # Get request with timeout
                try:
                    code, language, input_data, result_queue, client_info = self.queue.get(timeout=1)
                except queue.Empty:
                    continue

                start_time = time.time()
                try:
                    # Execute code with timeout
                    result = self.execute_code(code, language, input_data)

                    # Update metrics
                    self.monitor.add_metric(CompilerMetrics(
                        language=language,
                        compilation_time=time.time() - start_time,
                        execution_time=0.0,  # Placeholder
                        memory_used=result.get('memory_usage', 0.0),
                        peak_memory=result.get('peak_memory', 0.0),
                        client_info=client_info
                    ))

                    # Send result back
                    try:
                        result_queue.put(result, timeout=2)
                    except queue.Full:
                        logger.error("Result queue is full")
                        result_queue.put({
                            'success': False,
                            'output': '',
                            'error': "Erreur système: délai d'attente dépassé"
                        }, block=False)

                except Exception as e:
                    logger.error(f"Worker error: {e}", exc_info=True)
                    result_queue.put({
                        'success': False,
                        'output': '',
                        'error': f"Erreur d'exécution: {str(e)}"
                    }, block=False)

                finally:
                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Critical worker error: {e}", exc_info=True)
                time.sleep(1)

    def start_workers(self):
        """Start worker threads"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"CompilerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker thread {worker.name}")

    def submit(self, code: str, language: str, input_data: Optional[str] = None, 
              client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit code for execution"""
        if self._shutdown.is_set():
            return {
                'success': False,
                'output': '',
                'error': "Le service est en cours d'arrêt"
            }

        result_queue = queue.Queue()
        try:
            # Try to submit with timeout
            try:
                self.queue.put((code, language, input_data, result_queue, client_info), timeout=5)
            except queue.Full:
                return {
                    'success': False,
                    'output': '',
                    'error': "Le serveur est occupé"
                }

            # Wait for result with timeout
            try:
                result = result_queue.get(timeout=10)
                result['client_info'] = client_info
                return result
            except queue.Empty:
                return {
                    'success': False,
                    'output': '',
                    'error': "Le délai d'exécution a été dépassé"
                }

        except Exception as e:
            logger.error(f"Submit error: {e}", exc_info=True)
            return {
                'success': False,
                'output': '',
                'error': f"Erreur système: {str(e)}"
            }

    def shutdown(self):
        """Graceful shutdown"""
        self._shutdown.set()
        for worker in self.workers:
            worker.join(timeout=2)

    def _compile_and_run_cpp(self, code: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Compile and run C++ code"""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "program.cpp"
            executable = Path(temp_dir) / "program"

            try:
                # Write source code
                with open(source_file, 'w') as f:
                    f.write(code)

                # Compile
                compile_process = subprocess.run(
                    ['g++', str(source_file), '-o', str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'output': '',
                        'error': compile_process.stderr
                    }

                # Run
                run_process = subprocess.run(
                    [str(executable)],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    preexec_fn=set_resource_limits
                )

                return {
                    'success': True,
                    'output': run_process.stdout,
                    'error': run_process.stderr if run_process.stderr else None
                }

            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'output': '',
                    'error': "Le délai d'exécution a été dépassé"
                }
            except Exception as e:
                return {
                    'success': False,
                    'output': '',
                    'error': f"Erreur: {str(e)}"
                }

    def _compile_and_run_csharp(self, code: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Compile and run C# code"""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "program.cs"
            executable = Path(temp_dir) / "program.exe"

            try:
                # Write source code
                with open(source_file, 'w') as f:
                    f.write(code)

                # Compile
                compile_process = subprocess.run(
                    ['mcs', str(source_file), '-out:' + str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'output': '',
                        'error': compile_process.stderr
                    }

                # Run
                run_process = subprocess.run(
                    ['mono', str(executable)],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    preexec_fn=set_resource_limits
                )

                return {
                    'success': True,
                    'output': run_process.stdout,
                    'error': run_process.stderr if run_process.stderr else None
                }

            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'output': '',
                    'error': "Le délai d'exécution a été dépassé"
                }
            except Exception as e:
                return {
                    'success': False,
                    'output': '',
                    'error': f"Erreur: {str(e)}"
                }

# Initialize global queue
request_queue = RequestQueue(max_workers=2)

def compile_and_run(code: str, language: str, input_data: Optional[str] = None,
                   client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Submit code to the request queue"""
    if language not in ['cpp', 'csharp']:
        return {
            'success': False,
            'output': '',
            'error': f"Langage non supporté: {language}"
        }

    return request_queue.submit(code, language, input_data, client_info)

def check_memory_availability(required_mb: int = 20) -> bool:
    """
    Check if enough memory is available before attempting allocation
    """
    try:
        # Get memory info
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                key, value = line.split(':')
                meminfo[key.strip()] = int(value.split()[0])  # Values are in KB

        available_mb = (meminfo.get('MemAvailable', 0)) / 1024  # Convert to MB
        logger.debug(f"Available memory: {available_mb:.2f}MB, Required: {required_mb}MB")

        return available_mb >= required_mb
    except Exception as e:
        logger.error(f"Error checking memory availability: {e}")
        return False

@contextmanager
def create_temp_directory():
    """Create and clean up temporary directory with proper context management"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        try:
            subprocess.run(['rm', '-rf', temp_dir], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")

def format_compiler_error(error_text: str, lang: str = 'cpp') -> Dict[str, Any]:
    """Format compiler error messages to be more user-friendly"""
    if not error_text:
        return {
            'error_details': None,
            'full_error': '',
            'formatted_message': "Une erreur inconnue est survenue"
        }

    # Extract the main error message
    error_lines = error_text.split('\n')
    main_error = None

    if lang == 'cpp':
        for line in error_lines:
            if 'error:' in line:
                match = re.search(r'program\.cpp:(\d+):(\d+):\s*error:\s*(.+)', line)
                if match:
                    line_num, col_num, message = match.groups()
                    main_error = {
                        'line': int(line_num),
                        'column': int(col_num),
                        'message': message.strip(),
                        'type': 'error'
                    }
                    break
    else:  # C#
        for line in error_lines:
            if '(CS' in line:
                match = re.search(r'program\.cs\((\d+),(\d+)\):\s*error\s*(CS\d+):\s*(.+)', line)
                if match:
                    line_num, col_num, error_code, message = match.groups()
                    main_error = {
                        'line': int(line_num),
                        'column': int(col_num),
                        'code': error_code,
                        'message': message.strip(),
                        'type': 'error'
                    }
                    break

    if main_error:
        formatted_msg = (
            f"Erreur ligne {main_error['line']}: {main_error['message']}"
            if 'code' not in main_error else
            f"Erreur {main_error['code']} ligne {main_error['line']}: {main_error['message']}"
        )
        return {
            'error_details': main_error,
            'full_error': error_text,
            'formatted_message': formatted_msg
        }
    return {
        'error_details': None,
        'full_error': error_text,
        'formatted_message': error_text.split('\n')[0] if error_text else "Erreur de compilation"
    }