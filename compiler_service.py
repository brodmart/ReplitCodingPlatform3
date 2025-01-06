"""
Compiler service for code execution and testing.
Focused on memory management and resource limits.
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
from typing import Dict, Any, Optional
from contextlib import contextmanager
import queue
import threading
import time
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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

class RequestQueue:
    """Manages code execution requests with strict memory limits"""
    def __init__(self, max_workers=2):
        self.queue = queue.Queue(maxsize=5)  # Limit concurrent requests
        self.workers = []
        self.max_workers = max_workers
        self._shutdown = threading.Event()
        self.start_workers()

    def start_workers(self):
        """Start worker threads with resource limits"""
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        """Worker thread main loop with enhanced error handling"""
        while not self._shutdown.is_set():
            try:
                request = self.queue.get(timeout=1)
                if request is None:
                    break

                code, language, input_data, result_queue = request
                try:
                    # Set process-specific memory limits
                    if not set_memory_limit():
                        raise MemoryLimitExceeded("Failed to set memory limits")

                    result = self._execute_code(code, language, input_data)
                    result_queue.put(result)
                except MemoryLimitExceeded as e:
                    logger.error(f"Memory limit exceeded: {str(e)}")
                    result_queue.put({
                        'success': False,
                        'output': '',
                        'error': 'Limite de mémoire dépassée. Réduisez l\'utilisation de la mémoire.'
                    })
                except Exception as e:
                    logger.error(f"Worker error: {str(e)}")
                    result_queue.put({
                        'success': False,
                        'output': '',
                        'error': str(e)
                    })
                finally:
                    self.queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {str(e)}")
                time.sleep(1)

    def _execute_code(self, code: str, language: str, input_data: Optional[str]) -> Dict[str, Any]:
        """Execute code with strict memory limits"""
        if language == 'cpp':
            return _compile_and_run_cpp(code, input_data)
        else:
            return _compile_and_run_csharp(code, input_data)

    def submit(self, code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Submit code for execution with timeout"""
        result_queue = queue.Queue()
        try:
            self.queue.put((code, language, input_data, result_queue), timeout=5)
            return result_queue.get(timeout=10)
        except queue.Full:
            return {
                'success': False,
                'output': '',
                'error': "Le serveur est occupé. Veuillez réessayer dans quelques instants."
            }
        except queue.Empty:
            return {
                'success': False,
                'output': '',
                'error': "Le délai d'exécution a été dépassé."
            }

    def shutdown(self):
        """Graceful shutdown with cleanup"""
        self._shutdown.set()
        for _ in range(self.max_workers):
            try:
                self.queue.put(None, timeout=1)
            except queue.Full:
                break
        for worker in self.workers:
            worker.join(timeout=2)

# Global request queue instance
request_queue = RequestQueue()

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Submit code to the request queue"""
    if language not in ['cpp', 'csharp']:
        raise ValueError(f"Unsupported language: {language}")

    return request_queue.submit(code, language, input_data)

def _compile_and_run_cpp(code: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C++ code with enhanced memory management"""
    with create_temp_directory() as temp_dir:
        source_file = Path(temp_dir) / "program.cpp"
        executable = Path(temp_dir) / "program"

        try:
            # Write source code to file
            with open(source_file, 'w') as f:
                f.write(code)

            # Compile with memory safety flags
            compile_process = subprocess.run(
                ['g++', '-Wall', '-Wextra', '-Werror',
                 '-fstack-protector',
                 '-fsanitize=address',  # Add ASan for memory error detection
                 '-fno-omit-frame-pointer',  # Better stack traces
                 str(source_file), '-o', str(executable)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if compile_process.returncode != 0:
                error_info = format_compiler_error(compile_process.stderr, 'cpp')
                logger.error(f"Compilation failed: {error_info['formatted_message']}")
                raise CompilerError(error_info['formatted_message'])

            def preexec_fn():
                """Setup process isolation and reduced memory limits"""
                try:
                    # Reduce memory limits
                    resource.setrlimit(resource.RLIMIT_AS, (10 * 1024 * 1024, -1))  # 10MB virtual memory
                    resource.setrlimit(resource.RLIMIT_DATA, (5 * 1024 * 1024, -1))  # 5MB data segment
                    resource.setrlimit(resource.RLIMIT_STACK, (2 * 1024 * 1024, -1))  # 2MB stack
                    resource.setrlimit(resource.RLIMIT_CPU, (2, -1))  # 2 seconds CPU time
                    os.setsid()
                except Exception as e:
                    logger.warning(f"Failed to set resource limits: {e}")

            # Run with memory monitoring
            run_process = subprocess.run(
                [str(executable)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=5,
                preexec_fn=preexec_fn,
                env={'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=0:allocator_may_return_null=1'}
            )

            return {
                'success': True,
                'output': run_process.stdout,
                'error': run_process.stderr if run_process.stderr else None
            }

        except OSError as e:
            if e.errno == errno.ENOMEM:
                logger.error("Memory allocation error: %s", str(e))
                return {
                    'success': False,
                    'output': '',
                    'error': 'Mémoire insuffisante. Réduisez la taille des variables ou des tableaux.'
                }
            return {
                'success': False,
                'output': '',
                'error': f'Erreur système: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error in C++ execution: {str(e)}")
            return {
                'success': False,
                'output': '',
                'error': 'Une erreur inattendue s\'est produite lors de l\'exécution'
            }

def _compile_and_run_csharp(code: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C# code with enhanced monitoring"""
    with create_temp_directory() as temp_dir:
        source_file = Path(temp_dir) / "program.cs"
        executable = Path(temp_dir) / "program.exe"

        try:
            logger.info("Starting C# compilation and execution process")
            logger.debug(f"Working directory: {temp_dir}")

            # Write source code to file
            with open(source_file, 'w') as f:
                f.write(code)
            logger.info(f"Source code written to {source_file}")

            # Compile with detailed output capture
            logger.info("Starting C# compilation")
            compile_cmd = ['mcs', '-debug+', '-checked+', str(source_file), '-out:' + str(executable)]
            logger.debug(f"Compilation command: {' '.join(compile_cmd)}")

            compile_process = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            logger.debug(f"Compilation return code: {compile_process.returncode}")
            logger.debug(f"Compilation stdout: {compile_process.stdout}")
            logger.debug(f"Compilation stderr: {compile_process.stderr}")

            if compile_process.returncode != 0:
                error_info = format_compiler_error(compile_process.stderr, 'csharp')
                logger.error(f"C# compilation failed: {error_info}")
                return {
                    'success': False,
                    'output': '',
                    'error': error_info['formatted_message']
                }

            # Execute with detailed monitoring
            logger.info("Starting C# execution")
            run_cmd = [
                'mono',
                '--debug',
                '--gc=sgen',
                str(executable)
            ]
            logger.debug(f"Execution command: {' '.join(run_cmd)}")

            def monitor_preexec():
                """Monitor process execution"""
                os.setsid()
                # Set lower process priority
                os.nice(10)
                # Set memory limits - adjusted for Mono runtime needs
                resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, -1))  # 100MB virtual memory
                resource.setrlimit(resource.RLIMIT_DATA, (50 * 1024 * 1024, -1))  # 50MB data segment
                logger.debug("Process monitoring and limits set")

            run_process = subprocess.run(
                run_cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=5,
                preexec_fn=monitor_preexec
            )

            logger.debug(f"Execution return code: {run_process.returncode}")
            logger.debug(f"Execution stdout: {run_process.stdout}")
            logger.debug(f"Execution stderr: {run_process.stderr}")

            if run_process.returncode != 0:
                logger.error(f"C# execution failed with return code {run_process.returncode}")
                return {
                    'success': False,
                    'output': '',
                    'error': f"Erreur d'exécution: {run_process.stderr}"
                }

            # Filter out debug messages from stderr
            error_output = run_process.stderr
            if error_output:
                # Only keep actual error messages, filter out debug logs
                error_lines = [line for line in error_output.split('\n')
                               if not any(debug_text in line.lower()
                                          for debug_text in ['debug', 'monitoring', 'process'])]
                error_output = '\n'.join(error_lines).strip()

            return {
                'success': True,
                'output': run_process.stdout,
                'error': error_output if error_output else None
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"C# execution timeout: {str(e)}")
            os.killpg(os.getpgid(0), signal.SIGKILL)
            return {
                'success': False,
                'output': '',
                'error': 'Le programme a dépassé la limite de temps de 5 secondes'
            }
        except Exception as e:
            logger.error(f"Unexpected error in C# execution: {str(e)}", exc_info=True)
            return {
                'success': False,
                'output': '',
                'error': f"Erreur lors de l'exécution: {str(e)}"
            }

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

def set_memory_limit():
    """Set memory limit to 20MB - reduced from 25MB to prevent allocation issues"""
    memory_limit = 20 * 1024 * 1024  # 20MB in bytes
    try:
        # Set both soft and hard limits
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        # Set data segment limit
        resource.setrlimit(resource.RLIMIT_DATA, (memory_limit, memory_limit))
        # Set stack size limit
        resource.setrlimit(resource.RLIMIT_STACK, (2 * 1024 * 1024, 2 * 1024 * 1024))  # 2MB stack
        return True
    except Exception as e:
        logger.error(f"Failed to set memory limit: {e}")
        return False

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

@dataclass
class ExecutionMetrics:
    """Track execution metrics for monitoring"""
    request_id: str
    timestamp: datetime
    queue_size: int = 0
    wait_time: float = 0.0
    execution_time: float = 0.0
    success: bool = False
    error: Optional[str] = None

class QueueMonitor:
    """Monitor queue performance and health"""
    def __init__(self):
        self.metrics = []
        self.max_metrics = 1000  # Keep last 1000 requests
        self._lock = threading.Lock()

    def add_metric(self, metric: ExecutionMetrics):
        with self._lock:
            self.metrics.append(metric)
            if len(self.metrics) > self.max_metrics:
                self.metrics.pop(0)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            if not self.metrics:
                return {}

            total_requests = len(self.metrics)
            successful = sum(1 for m in self.metrics if m.success)
            avg_wait = sum(m.wait_time for m in self.metrics) / total_requests if total_requests > 0 else 0
            avg_exec = sum(m.execution_time for m in self.metrics) / total_requests if total_requests > 0 else 0

            return {
                'total_requests': total_requests,
                'success_rate': successful / total_requests if total_requests > 0 else 0,
                'avg_wait_time': avg_wait,
                'avg_execution_time': avg_exec,
                'current_queue_size': self.metrics[-1].queue_size if self.metrics else 0
            }