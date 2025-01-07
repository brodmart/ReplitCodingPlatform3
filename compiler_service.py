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
import numpy as np
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

class ResourceAnalyzer:
    """Analyzes and predicts resource usage patterns"""
    def __init__(self, history_window: int = 3600):
        self.history_window = history_window  # 1 hour default
        self.usage_history: List[Dict[str, Any]] = []
        self.last_cleanup = datetime.now()
        self._lock = threading.Lock()

    def add_usage_data(self, data: Dict[str, Any]):
        """Add new resource usage data point"""
        with self._lock:
            current_time = datetime.now()
            self.usage_history.append({
                'timestamp': current_time,
                **data
            })

            # Cleanup old data
            if (current_time - self.last_cleanup).total_seconds() > 300:  # Every 5 minutes
                self._cleanup_old_data()
                self.last_cleanup = current_time

    def _cleanup_old_data(self):
        """Remove data points older than history window"""
        cutoff_time = datetime.now() - timedelta(seconds=self.history_window)
        self.usage_history = [
            data for data in self.usage_history
            if data['timestamp'] > cutoff_time
        ]

    def predict_resource_needs(self, future_minutes: int = 30) -> Dict[str, Any]:
        """Predict future resource needs based on historical patterns"""
        with self._lock:
            if not self.usage_history:
                return {
                    'status': 'insufficient_data',
                    'message': 'Not enough historical data for prediction'
                }

            # Prepare time series data
            current_time = datetime.now()
            timestamps = [(data['timestamp'] - current_time).total_seconds() / 60 
                         for data in self.usage_history]
            memory_usage = [data.get('memory_used', 0) for data in self.usage_history]
            cpu_usage = [data.get('cpu_percent', 0) for data in self.usage_history]

            try:
                # Prepare data for linear regression
                X = np.array(timestamps).reshape(-1, 1)

                # Predict memory usage
                mem_model = LinearRegression()
                mem_model.fit(X, memory_usage)
                future_memory = mem_model.predict([[future_minutes]])[0]

                # Predict CPU usage
                cpu_model = LinearRegression()
                cpu_model.fit(X, cpu_usage)
                future_cpu = cpu_model.predict([[future_minutes]])[0]

                # Calculate confidence intervals
                memory_std = np.std(memory_usage)
                cpu_std = np.std(cpu_usage)

                return {
                    'predictions': {
                        'memory_usage': max(0, future_memory),
                        'memory_confidence_interval': (
                            max(0, future_memory - 2 * memory_std),
                            future_memory + 2 * memory_std
                        ),
                        'cpu_usage': max(0, min(100, future_cpu)),
                        'cpu_confidence_interval': (
                            max(0, future_cpu - 2 * cpu_std),
                            min(100, future_cpu + 2 * cpu_std)
                        )
                    },
                    'current_trends': {
                        'memory_usage_trend': mem_model.coef_[0],
                        'cpu_usage_trend': cpu_model.coef_[0]
                    }
                }
            except Exception as e:
                logger.error(f"Error in resource prediction: {e}")
                return {
                    'status': 'prediction_error',
                    'message': str(e)
                }

    def get_scaling_recommendations(self) -> Dict[str, Any]:
        """Generate scaling recommendations based on predictions"""
        predictions = self.predict_resource_needs()
        if 'status' in predictions:
            return predictions

        current_metrics = self._get_current_metrics()
        pred_metrics = predictions['predictions']
        trends = predictions['current_trends']

        recommendations = []

        # Memory-based recommendations
        if pred_metrics['memory_usage'] > current_metrics['memory_limit'] * 0.8:
            recommendations.append({
                'resource': 'memory',
                'action': 'increase',
                'urgency': 'high',
                'reason': 'Predicted memory usage approaching limit'
            })
        elif pred_metrics['memory_usage'] < current_metrics['memory_limit'] * 0.3:
            recommendations.append({
                'resource': 'memory',
                'action': 'decrease',
                'urgency': 'low',
                'reason': 'Memory consistently underutilized'
            })

        # CPU-based recommendations
        if pred_metrics['cpu_usage'] > 80:
            recommendations.append({
                'resource': 'cpu',
                'action': 'increase',
                'urgency': 'high',
                'reason': 'High CPU utilization predicted'
            })

        # Worker scaling recommendations
        concurrent_requests = current_metrics['concurrent_requests']
        if concurrent_requests > current_metrics['worker_count'] * 0.8:
            recommendations.append({
                'resource': 'workers',
                'action': 'increase',
                'urgency': 'medium',
                'reason': 'High concurrent request load'
            })

        return {
            'current_metrics': current_metrics,
            'predictions': pred_metrics,
            'trends': trends,
            'recommendations': recommendations
        }

    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                'memory_used': memory_info.rss / (1024 * 1024),  # MB
                'memory_limit': resource.getrlimit(resource.RLIMIT_AS)[0] / (1024 * 1024),  # MB
                'cpu_percent': process.cpu_percent(),
                'worker_count': threading.active_count() - 1,  # Exclude main thread
                'concurrent_requests': len([t for t in threading.enumerate() 
                                            if t.name.startswith('CompilerWorker')])
            }
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {}

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
        self.resource_analyzer = ResourceAnalyzer()

    def add_metric(self, metric: CompilerMetrics):
        """Add new compilation metric with enhanced tracking"""
        with self._lock:
            current_time = datetime.now()
            # Clean old metrics
            self.metrics = [m for m in self.metrics 
                              if (current_time - m.timestamp).total_seconds() < self.metrics_window]
            self.metrics.append(metric)
            self.resource_analyzer.add_usage_data({
                'memory_used': metric.memory_used,
                'cpu_percent': psutil.cpu_percent(), #Add CPU usage
            })


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
        self.resource_analyzer = ResourceAnalyzer()
        self.workers = []
        self.start_workers()

    def execute_code(self, code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Execute code with strict resource limits"""
        start_time = time.time()
        try:
            # Get initial resource state
            process = psutil.Process()
            initial_cpu = process.cpu_percent()
            initial_memory = process.memory_info().rss / (1024 * 1024)

            if language == 'cpp':
                result = self._compile_and_run_cpp(code, input_data)
            else:
                result = self._compile_and_run_csharp(code, input_data)

            # Get final resource state
            final_cpu = process.cpu_percent()
            final_memory = process.memory_info().rss / (1024 * 1024)

            # Add resource usage data
            self.resource_analyzer.add_usage_data({
                'memory_used': final_memory,
                'memory_delta': final_memory - initial_memory,
                'cpu_percent': final_cpu,
                'cpu_delta': final_cpu - initial_cpu,
                'execution_time': time.time() - start_time,
                'language': language,
                'success': result.get('success', False)
            })

            # Add resource metrics to result
            result.update({
                'memory_usage': final_memory,
                'peak_memory': process.memory_info().vms / (1024 * 1024)
            })

            # Check if scaling is needed
            recommendations = self.resource_analyzer.get_scaling_recommendations()
            if recommendations.get('recommendations'):
                for rec in recommendations['recommendations']:
                    if rec['urgency'] == 'high':
                        logger.warning(f"Resource scaling recommended: {rec}")

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

# Initialize global queue with resource analysis
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