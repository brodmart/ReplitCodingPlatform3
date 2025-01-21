"""
Optimization analyzer for compiler service performance.
Provides automated suggestions for improving system performance.
"""
import logging
import psutil
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class OptimizationSuggestion:
    category: str  # 'memory', 'cpu', 'compiler', 'general'
    priority: int  # 1-5, where 5 is highest
    issue: str
    impact: str
    recommendation: str
    metrics: Dict[str, Any]

class ResourceMonitor:
    def __init__(self):
        self.cpu_history: List[float] = []
        self.memory_history: List[float] = []
        self.sample_interval = 1  # seconds
        self.history_size = 60    # Keep last 60 samples

    def get_current_usage(self) -> Dict[str, float]:
        """Get current CPU and memory usage"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        self.cpu_history.append(cpu_percent)
        self.memory_history.append(memory.percent)

        # Keep history size bounded
        if len(self.cpu_history) > self.history_size:
            self.cpu_history.pop(0)
        if len(self.memory_history) > self.history_size:
            self.memory_history.pop(0)

        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available': memory.available / (1024 * 1024)  # MB
        }

    def get_load_level(self) -> str:
        """Determine current load level based on resource usage"""
        if not self.cpu_history or not self.memory_history:
            return 'normal'

        avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
        avg_memory = sum(self.memory_history) / len(self.memory_history)

        if avg_cpu > 80 or avg_memory > 80:
            return 'high'
        elif avg_cpu > 60 or avg_memory > 60:
            return 'medium'
        return 'normal'

class PerformanceOptimizer:
    def __init__(self):
        self.memory_threshold = 80  # Percentage
        self.cpu_threshold = 70     # Percentage
        self.compile_time_threshold = 2.0  # seconds
        self.suggestions_history: List[OptimizationSuggestion] = []
        self.resource_monitor = ResourceMonitor()
        self._init_metrics()

    def _init_metrics(self):
        """Initialize metrics tracking"""
        self.language_metrics: Dict[str, Dict[str, Any]] = {
            lang: {
                'total_executions': 0,
                'failed_executions': 0,
                'avg_compile_time': 0.0,
                'peak_memory': 0.0,
                'common_errors': defaultdict(int)
            }
            for lang in ['cpp', 'csharp']
        }

    def analyze_compiler_metrics(self, metrics: Dict[str, Any]) -> List[OptimizationSuggestion]:
        """Analyze compiler performance metrics and generate optimization suggestions."""
        suggestions = []
        current_usage = self.resource_monitor.get_current_usage()

        # Analyze memory usage
        if current_usage['memory_percent'] > self.memory_threshold:
            suggestions.append(OptimizationSuggestion(
                category='memory',
                priority=5,
                issue='High memory utilization detected',
                impact='Risk of compilation failures and system instability',
                recommendation='Consider increasing worker memory limits or implementing request queuing',
                metrics={'current_usage': current_usage['memory_percent']}
            ))

        # Analyze compilation times
        compile_time = metrics.get('compilation_time', 0)
        if compile_time > self.compile_time_threshold:
            suggestions.append(OptimizationSuggestion(
                category='compiler',
                priority=4,
                issue='Slow compilation times detected',
                impact='Poor user experience and resource blockage',
                recommendation='Review compiler flags and optimization levels',
                metrics={'compile_time': compile_time}
            ))

        # Track language-specific patterns
        language = metrics.get('language', 'unknown')
        self._update_language_metrics(language, metrics)

        return suggestions

    def get_recommended_thread_count(self) -> int:
        """Determine optimal thread count based on current load"""
        load_level = self.resource_monitor.get_load_level()
        cpu_count = psutil.cpu_count() or 4

        if load_level == 'high':
            return max(2, cpu_count // 2)  # Reduce threads under high load
        elif load_level == 'medium':
            return max(2, cpu_count - 1)   # Use most cores but leave one free
        else:
            return cpu_count               # Use all cores under normal load

    def _update_language_metrics(self, language: str, metrics: Dict[str, Any]) -> None:
        """Update language-specific performance metrics"""
        if language not in self.language_metrics:
            return

        stats = self.language_metrics[language]
        stats['total_executions'] += 1

        if not metrics.get('success', True):
            stats['failed_executions'] += 1
            error_type = metrics.get('error_type', 'unknown')
            stats['common_errors'][error_type] += 1

        # Update running averages
        current_avg = float(stats['avg_compile_time'])
        new_time = float(metrics.get('compilation_time', 0.0))
        total_execs = stats['total_executions']
        stats['avg_compile_time'] = ((current_avg * (total_execs - 1) + new_time) / total_execs)

        # Track peak memory
        new_peak = float(metrics.get('peak_memory', 0.0))
        stats['peak_memory'] = max(float(stats['peak_memory']), new_peak)

    def get_system_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive system health report"""
        current_usage = self.resource_monitor.get_current_usage()
        load_level = self.resource_monitor.get_load_level()

        report = {
            'current_state': {
                'cpu_usage': current_usage['cpu_percent'],
                'memory_usage': current_usage['memory_percent'],
                'available_memory_mb': current_usage['memory_available'],
                'load_level': load_level,
                'recommended_threads': self.get_recommended_thread_count()
            },
            'languages': {},
            'system_health': {
                'memory_status': 'healthy' if current_usage['memory_percent'] < self.memory_threshold else 'critical',
                'cpu_status': 'healthy' if current_usage['cpu_percent'] < self.cpu_threshold else 'critical',
            }
        }

        # Add language-specific metrics
        for language, metrics in self.language_metrics.items():
            total_execs = metrics['total_executions']
            failed_execs = metrics['failed_executions']

            if total_execs > 0:
                success_rate = 1 - (failed_execs / total_execs)
                report['languages'][language] = {
                    'success_rate': success_rate,
                    'avg_compile_time': metrics['avg_compile_time'],
                    'peak_memory': metrics['peak_memory'],
                    'common_errors': dict(metrics['common_errors'])
                }

        return report

    def _analyze_error_patterns(self, language: str, metrics: Dict[str, Any]) -> Optional[OptimizationSuggestion]:
        """Analyze error patterns and generate relevant suggestions."""
        error_type = metrics.get('error_type')
        if not error_type or language not in self.language_metrics:
            return None

        lang_stats = self.language_metrics[language]
        error_count = lang_stats['common_errors'].get(error_type, 0)
        total_executions = int(lang_stats['total_executions'])

        if total_executions > 0 and (error_count / total_executions) > 0.1:  # More than 10% error rate
            return OptimizationSuggestion(
                category='compiler',
                priority=5,
                issue=f'Frequent {error_type} errors in {language}',
                impact='High failure rate affecting user experience',
                recommendation=self._get_error_recommendation(error_type, language),
                metrics={
                    'error_rate': error_count / total_executions,
                    'total_occurrences': error_count
                }
            )
        return None

    def _get_error_recommendation(self, error_type: str, language: str) -> str:
        """Get specific recommendations based on error type and language."""
        recommendations = {
            'memory_limit': 'Implement memory usage optimizations and strict limits',
            'compilation': 'Review compiler flags and ensure proper dependency management',
            'execution_timeout': 'Add execution time limits and optimize code analysis',
            'syntax': 'Enhance error reporting and provide detailed feedback to users',
            'libstdc++': 'Verify system library compatibility and container configuration'
        }
        return recommendations.get(error_type, 'Review system logs and monitoring data')