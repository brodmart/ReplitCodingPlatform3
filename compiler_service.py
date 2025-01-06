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
        self.hourly_stats = defaultdict(lambda: defaultdict(int))
        self.language_stats = defaultdict(lambda: {
            'total_requests': 0,
            'success_count': 0,
            'avg_compile_time': 0.0,
            'avg_execution_time': 0.0,
            'avg_memory_used': 0.0,
            'peak_memory': 0.0,
            'error_count': 0
        })
        self._lock = threading.Lock()

    def add_metric(self, metric: CompilerMetrics):
        """Add new compilation metric with enhanced tracking"""
        with self._lock:
            current_time = datetime.now()
            # Clean old metrics
            self.metrics = [m for m in self.metrics 
                          if (current_time - m.timestamp).total_seconds() < self.metrics_window]

            # Add new metric
            self.metrics.append(metric)

            # Update language statistics
            lang_stats = self.language_stats[metric.language]
            lang_stats['total_requests'] += 1
            if metric.error_type is None:
                lang_stats['success_count'] += 1
            else:
                lang_stats['error_count'] += 1

            # Update averages
            n = lang_stats['total_requests']
            lang_stats['avg_compile_time'] = (lang_stats['avg_compile_time'] * (n-1) + metric.compilation_time) / n if n > 0 else metric.compilation_time
            lang_stats['avg_execution_time'] = (lang_stats['avg_execution_time'] * (n-1) + metric.execution_time) / n if n > 0 else metric.execution_time
            lang_stats['avg_memory_used'] = (lang_stats['avg_memory_used'] * (n-1) + metric.memory_used) / n if n > 0 else metric.memory_used
            lang_stats['peak_memory'] = max(lang_stats['peak_memory'], metric.peak_memory)

            # Track error patterns
            if metric.error_type:
                hour_key = metric.timestamp.strftime('%Y-%m-%d %H:00')
                self.error_patterns[metric.error_type].append({
                    'timestamp': metric.timestamp,
                    'language': metric.language,
                    'client_info': metric.client_info,
                    'memory_used': metric.memory_used,
                    'details': metric.error_details
                })

                # Special handling for libstdc++.so.6 errors
                if 'libstdc++.so.6' in str(metric.error_details):
                    concurrent_users = len([m for m in self.metrics 
                                             if abs((m.timestamp - metric.timestamp).total_seconds()) < 60])
                    logger.warning(
                        f"libstdc++.so.6 error detected:\n"
                        f"Time: {metric.timestamp}\n"
                        f"Concurrent Users: {concurrent_users}\n"
                        f"Memory Used: {metric.memory_used}MB\n"
                        f"Client Info: {metric.client_info}"
                    )

    def get_current_load(self) -> Dict[str, Any]:
        """Get current system load metrics"""
        try:
            memory = psutil.virtual_memory()
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': memory.percent,
                'memory_available': memory.available / (1024 * 1024),  # MB
                'concurrent_compilations': len([m for m in self.metrics 
                    if (datetime.now() - m.timestamp).total_seconds() < 60])
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        with self._lock:
            current_time = datetime.now()
            recent_window = 300  # 5 minutes
            recent_metrics = [m for m in self.metrics 
                            if (current_time - m.timestamp).total_seconds() < recent_window]

            if not recent_metrics:
                return {'status': 'No recent metrics available'}

            total_requests = len(recent_metrics)
            error_count = sum(1 for m in recent_metrics if m.error_type is not None)

            report = {
                'current_load': self.get_current_load(),
                'recent_metrics': {
                    'window_seconds': recent_window,
                    'total_requests': total_requests,
                    'error_rate': error_count / total_requests if total_requests > 0 else 0,
                    'avg_compilation_time': sum(m.compilation_time for m in recent_metrics) / total_requests if total_requests > 0 else 0,
                    'avg_execution_time': sum(m.execution_time for m in recent_metrics) / total_requests if total_requests > 0 else 0,
                    'avg_memory_used': sum(m.memory_used for m in recent_metrics) / total_requests if total_requests > 0 else 0,
                    'peak_memory': max(m.peak_memory for m in recent_metrics) if recent_metrics else 0
                },
                'language_stats': dict(self.language_stats),
                'error_patterns': {
                    error_type: len(errors) 
                    for error_type, errors in self.error_patterns.items()
                }
            }

            # Add performance alerts
            alerts = []
            if report['recent_metrics']['error_rate'] > 0.1:  # More than 10% errors
                alerts.append({
                    'level': 'warning',
                    'message': f"High error rate: {report['recent_metrics']['error_rate']*100:.1f}%"
                })
            if report['current_load'].get('memory_available', float('inf')) < 1000:  # Less than 1GB available
                alerts.append({
                    'level': 'critical',
                    'message': "Low memory availability"
                })
            report['alerts'] = alerts

            return report

# Initialize the monitoring system
monitoring_system = MonitoringSystem()

@dataclass
class ExecutionMetrics:
    """Enhanced metrics tracking for monitoring"""
    request_id: str
    timestamp: datetime
    language: str  # Track which language was used
    queue_size: int = 0
    wait_time: float = 0.0
    compilation_time: float = 0.0  # Separate compilation time
    execution_time: float = 0.0    # Separate execution time
    total_time: float = 0.0        # Total processing time
    memory_usage: float = 0.0      # Memory usage in MB
    peak_memory: float = 0.0       # Peak memory usage
    error_type: Optional[str] = None  # Categorize error types
    error_details: Optional[Dict[str, Any]] = None
    success: bool = False
    concurrent_requests: int = 0    # Track concurrent requests
    worker_id: Optional[str] = None # Track which worker handled it
    client_info: Optional[Dict[str, Any]] = None  # Store client details


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

def set_memory_limit(memory_mb: int = 20) -> bool:
    """Set memory limit with pre-check"""
    try:
        if not check_memory_availability(memory_mb):
            logger.error(f"Insufficient memory available for {memory_mb}MB allocation")
            return False

        memory_bytes = memory_mb * 1024 * 1024
        # Set both soft and hard limits
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        # Set data segment limit
        resource.setrlimit(resource.RLIMIT_DATA, (memory_bytes // 2, memory_bytes // 2))
        # Set stack size limit
        resource.setrlimit(resource.RLIMIT_STACK, (2 * 1024 * 1024, 2 * 1024 * 1024))  # 2MB stack

        logger.info(f"Memory limits set successfully: {memory_mb}MB")
        return True
    except Exception as e:
        logger.error(f"Failed to set memory limit: {e}")
        return False

class RequestQueue:
    """Manages code execution requests with enhanced memory management"""
    def __init__(self, max_workers: int = 2):
        self.queue = queue.Queue(maxsize=5)
        self.workers: List[threading.Thread] = []
        self.max_workers = max_workers
        self.active_workers = threading.Semaphore(max_workers)
        self._shutdown = threading.Event()
        self.monitor = monitoring_system # Using the new MonitoringSystem
        self.start_workers()
        logger.info(f"RequestQueue initialized with {max_workers} workers")

    def execute_code(self, code: str, language: str, input_data: Optional[str]) -> Dict[str, Any]:
        """Execute code with strict memory limits and performance monitoring"""
        metric = CompilerMetrics(
            language=language,
            compilation_time=0.0,
            execution_time=0.0,
            memory_used=0.0,
            peak_memory=0.0
        )

        try:
            compile_start = time.time()
            if language == 'cpp':
                result = _compile_and_run_cpp(code, input_data)
            else:
                result = _compile_and_run_csharp(code, input_data)
            compile_end = time.time()

            # Update metrics
            metric.compilation_time = compile_end - compile_start
            metric.execution_time = time.time() - compile_end

            # Get memory statistics
            try:
                with open('/proc/self/status') as f:
                    for line in f:
                        if 'VmPeak:' in line:
                            metric.peak_memory = float(line.split()[1]) / 1024  # KB to MB
                        elif 'VmSize:' in line:
                            metric.memory_used = float(line.split()[1]) / 1024
            except Exception as e:
                logger.error(f"Error reading memory stats: {e}")

            if not result.get('success', False):
                metric.error_type = 'compilation_error' if 'error' in result else 'runtime_error'
                metric.error_details = result.get('error')

            monitoring_system.add_metric(metric)
            return result

        except Exception as e:
            logger.error(f"Error executing {language} code: {str(e)}")
            metric.error_type = 'system_error'
            metric.error_details = {'message': str(e)}
            monitoring_system.add_metric(metric)
            return {
                'success': False,
                'output': '',
                'error': f"Erreur d'exécution: {str(e)}"
            }

    def start_workers(self):
        """Start worker threads with resource monitoring"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"CompilerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker thread {worker.name}")

    def _worker_loop(self):
        """Enhanced worker thread main loop with detailed metrics"""
        while not self._shutdown.is_set():
            try:
                with self.active_workers:
                    request = self.queue.get(timeout=1)
                    if request is None:
                        break

                    code, language, input_data, result_queue, client_info = request
                    start_time = time.time()

                    metrics = ExecutionMetrics(
                        request_id=f"{time.time()}-{threading.current_thread().name}",
                        timestamp=datetime.now(),
                        language=language,
                        queue_size=self.queue.qsize(),
                        concurrent_requests=threading.active_count() - 1,  # Exclude main thread
                        worker_id=threading.current_thread().name,
                        client_info=client_info
                    )

                    try:
                        # Memory pre-check with enhanced monitoring
                        if not check_memory_availability():
                            raise MemoryLimitExceeded("Insufficient memory available")

                        # Track compilation and execution separately
                        compile_start = time.time()
                        result = self.execute_code(code, language, input_data)
                        compile_end = time.time()

                        metrics.compilation_time = compile_end - compile_start
                        metrics.execution_time = time.time() - compile_end
                        metrics.total_time = time.time() - start_time

                        # Get detailed memory stats  (This part needs improvement for accuracy)
                        process = psutil.Process()
                        metrics.memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
                        metrics.peak_memory = process.memory_info().vms / (1024 * 1024)  # MB


                        metrics.success = result.get('success', False)
                        if not result.get('success', False):
                            metrics.error_type = 'compilation_error' if 'error' in result else 'runtime_error'
                            metrics.error_details = result.get('error')

                        result_queue.put(result)

                    except MemoryLimitExceeded as e:
                        logger.error(f"Memory limit exceeded: {str(e)}")
                        metrics.error_type = 'memory_limit_exceeded'
                        metrics.error_details = str(e)
                        result_queue.put({
                            'success': False,
                            'output': '',
                            'error': 'Mémoire insuffisante. Réduisez la taille des variables ou des tableaux.'
                        })
                    except Exception as e:
                        logger.error(f"Worker error: {str(e)}", exc_info=True)
                        metrics.error_type = 'system_error'
                        metrics.error_details = str(e)
                        result_queue.put({
                            'success': False,
                            'output': '',
                            'error': f"Erreur d'exécution: {str(e)}"
                        })
                    finally:
                        self.monitor.add_metric(CompilerMetrics(
                            language=language,
                            compilation_time=metrics.compilation_time,
                            execution_time=metrics.execution_time,
                            memory_used=metrics.memory_usage,
                            peak_memory=metrics.peak_memory,
                            error_type=metrics.error_type,
                            error_details=metrics.error_details,
                            client_info=client_info
                        ))
                        self.queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {str(e)}", exc_info=True)
                time.sleep(1)

    def submit(self, code: str, language: str, input_data: Optional[str] = None, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit code for execution with enhanced error handling"""
        result_queue = queue.Queue()
        try:
            if not check_memory_availability():
                return {
                    'success': False,
                    'output': '',
                    'error': 'Le serveur est actuellement sous charge. Veuillez réessayer dans quelques instants.'
                }

            self.queue.put((code, language, input_data, result_queue, client_info), timeout=5)
            result = result_queue.get(timeout=10)
            result['client_info'] = client_info
            return result
        except queue.Full:
            logger.warning(f"Request queue full (size: {self.queue.qsize()})")
            return {
                'success': False,
                'output': '',
                'error': "Le serveur est occupé. Veuillez réessayer dans quelques instants."
            }
        except queue.Empty:
            logger.error("Execution timeout")
            return {
                'success': False,
                'output': '',
                'error': "Le délai d'exécution a été dépassé."
            }

    def shutdown(self):
        """Graceful shutdown with cleanup"""
        logger.info("Initiating RequestQueue shutdown")
        self._shutdown.set()
        for _ in range(self.max_workers):
            try:
                self.queue.put(None, timeout=1)
            except queue.Full:
                break
        for worker in self.workers:
            worker.join(timeout=2)
            logger.info(f"Worker {worker.name} shutdown complete")

# Global request queue instance
request_queue = RequestQueue()

def compile_and_run(code: str, language: str, input_data: Optional[str] = None, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Submit code to the request queue with enhanced monitoring"""
    if language not in ['cpp', 'csharp']:
        raise ValueError(f"Unsupported language: {language}")

    try:
        result = request_queue.submit(code, language, input_data, client_info)
        # Add performance metrics to the response
        performance_report = monitoring_system.get_performance_report()
        if performance_report.get('alerts'):
            logger.warning(f"Performance alerts: {performance_report['alerts']}")
        return result
    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': f"Une erreur s'est produite lors de l'exécution: {str(e)}"
        }

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
                'error': run_process.stderr if run_process.stderr else None,
                'memory_usage': 0.0,  # Placeholder - needs actual memory usage
                'peak_memory': 0.0    # Placeholder - needs actual peak memory usage
            }

        except OSError as e:
            if e.errno == errno.ENOMEM:
                logger.error("Memory allocation error: %s", str(e))
                return {
                    'success': False,
                    'output': '',
                    'error': 'Mémoire insuffisante. Réduisez la taille des variables ou des tableaux.',
                    'error_type': 'OSError',
                    'error_details': str(e)
                }
            return {
                'success': False,
                'output': '',
                'error': f'Erreur système: {str(e)}',
                'error_type': 'OSError',
                'error_details': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in C++ execution: {str(e)}")
            return {
                'success': False,
                'output': '',
                'error': 'Une erreur inattendue s\'est produite lors de l\'exécution',
                'error_type': type(e).__name__,
                'error_details': str(e)
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
                    'error': error_info['formatted_message'],
                    'error_type': 'CompilerError',
                    'error_details': error_info
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
                    'error': f"Erreur d'exécution: {run_process.stderr}",
                    'error_type': 'ExecutionError',
                    'error_details': run_process.stderr
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
                'error': error_output if error_output else None,
                'memory_usage': 0.0, # Placeholder
                'peak_memory': 0.0   # Placeholder
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"C# execution timeout: {str(e)}")
            os.killpg(os.getpgid(0), signal.SIGKILL)
            return {
                'success': False,
                'output': '',
                'error': 'Le programme a dépassé la limite de temps de 5 secondes',
                'error_type': 'TimeoutExpired',
                'error_details': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in C# execution: {str(e)}", exc_info=True)
            return {
                'success': False,
                'output': '',
                'error': f"Erreur lors de l'exécution: {str(e)}",
                'error_type': type(e).__name__,
                'error_details': str(e)
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