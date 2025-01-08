"""
Compiler service for code execution and testing.
"""
import subprocess
import tempfile
import os
import logging
import time
import queue
import threading
import resource
import signal
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
from contextlib import contextmanager
import psutil
import numpy as np
from sklearn.linear_model import LinearRegression
from optimization_analyzer import PerformanceOptimizer

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

def _compile_and_run_cpp(code: str, input_data: Optional[str], temp_dir: str) -> Dict[str, Any]:
    """Compile and run C++ code"""
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

        # Run with input
        input_bytes = input_data.encode() if input_data else None
        run_process = subprocess.run(
            [str(executable)],
            input=input_bytes,
            capture_output=True,
            text=True,
            timeout=5
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

def _compile_and_run_csharp(code: str, input_data: Optional[str], temp_dir: str) -> Dict[str, Any]:
    """Compile and run C# code"""
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

        # Run with input
        input_bytes = input_data.encode() if input_data else None
        run_process = subprocess.run(
            ['mono', str(executable)],
            input=input_bytes,
            capture_output=True,
            text=True,
            timeout=5
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

class CompilerQueue:
    """Simple queue for managing compilation requests"""
    def __init__(self, max_workers: int = 2):
        self.queue = queue.Queue()
        self.max_workers = max_workers
        self._shutdown = threading.Event()
        self.workers = []
        self.start_workers()

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

    def _worker_loop(self):
        """Worker thread main loop"""
        while not self._shutdown.is_set():
            try:
                code, language, input_data, result_queue = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                result = compile_and_run(code, language, input_data)
                result_queue.put(result)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                result_queue.put({
                    'success': False,
                    'output': '',
                    'error': f"Erreur d'exécution: {str(e)}"
                })
            finally:
                self.queue.task_done()

    def submit(self, code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
        """Submit code for execution"""
        if self._shutdown.is_set():
            return {
                'success': False,
                'output': '',
                'error': "Le service est en cours d'arrêt"
            }

        result_queue = queue.Queue()
        try:
            self.queue.put((code, language, input_data, result_queue), timeout=5)
        except queue.Full:
            return {
                'success': False,
                'output': '',
                'error': "Le serveur est occupé"
            }

        try:
            result = result_queue.get(timeout=10)
            return result
        except queue.Empty:
            return {
                'success': False,
                'output': '',
                'error': "Le délai d'exécution a été dépassé"
            }

    def shutdown(self):
        """Graceful shutdown"""
        self._shutdown.set()
        for worker in self.workers:
            worker.join(timeout=2)

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with proper input/output handling.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'cpp':
                return _compile_and_run_cpp(code, input_data, temp_dir)
            elif language == 'csharp':
                return _compile_and_run_csharp(code, input_data, temp_dir)
            else:
                return {
                    'success': False,
                    'output': '',
                    'error': f"Langage non supporté: {language}"
                }
    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': f"Une erreur s'est produite lors de l'exécution: {str(e)}"
        }

# Initialize global queue
compiler_queue = CompilerQueue(max_workers=2)
optimizer = PerformanceOptimizer()

def log_api_request(start_time: float, client_ip: str, endpoint: str, status_code: int, error: Optional[str] = None):
    """Log API request details"""
    duration = round((time.time() - start_time) * 1000, 2)  # Duration in milliseconds
    logger.info(f"""
    API Request Details:
    - Client IP: {client_ip}
    - Endpoint: {endpoint}
    - Duration: {duration}ms
    - Status: {status_code}
    {f'- Error: {error}' if error else ''}
    """)

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
                'worker_count': len([t for t in threading.enumerate() if t.name.startswith('CompilerWorker')]),  # Exclude main thread
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

from typing import List
import queue
import threading
optimizer = PerformanceOptimizer()
request_queue = compiler_queue #Rename to avoid conflict

def compile_and_run_wrapper(code: str, language: str, input_data: Optional[str] = None,
                   client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Submit code to the request queue with optimization tracking"""
    if language not in ['cpp', 'csharp']:
        return {
            'success': False,
            'output': '',
            'error': f"Langage non supporté: {language}"
        }

    # Execute code
    result = compiler_queue.submit(code, language, input_data)

    # Generate optimization suggestions
    try:
        metrics = {
            'language': language,
            'compilation_time': result.get('compilation_time', 0),
            'memory_used': result.get('memory_usage', 0),
            'peak_memory': result.get('peak_memory', 0),
            'success': result.get('success', False),
            'error_type': result.get('error_type'),
            'client_info': client_info
        }

        suggestions = optimizer.analyze_compiler_metrics(metrics)
        if suggestions:
            logger.info("Performance optimization suggestions generated:")
            for suggestion in suggestions:
                logger.info(f"- {suggestion.category} ({suggestion.priority}): {suggestion.issue}")
                logger.info(f"  Impact: {suggestion.impact}")
                logger.info(f"  Recommendation: {suggestion.recommendation}")

            # Add suggestions to result for monitoring
            result['optimization_suggestions'] = [
                {
                    'category': s.category,
                    'priority': s.priority,
                    'issue': s.issue,
                    'recommendation': s.recommendation
                } for s in suggestions
            ]
    except Exception as e:
        logger.error(f"Error generating optimization suggestions: {e}")

    return result

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

compile_and_run = compile_and_run_wrapper #Rename to avoid conflict

import signal
import re