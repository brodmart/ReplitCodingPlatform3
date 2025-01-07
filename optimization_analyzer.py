"""
Optimization analyzer for compiler service performance.
Provides automated suggestions for improving system performance.
"""
import logging
from typing import Dict, List, Any, Optional
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

class PerformanceOptimizer:
    def __init__(self):
        self.memory_threshold = 80  # Percentage
        self.cpu_threshold = 70  # Percentage
        self.compile_time_threshold = 2.0  # seconds
        self.suggestions_history: List[OptimizationSuggestion] = []
        self.language_metrics = defaultdict(lambda: {
            'total_executions': 0,
            'failed_executions': 0,
            'avg_compile_time': 0.0,
            'peak_memory': 0.0,
            'common_errors': defaultdict(int)
        })

    def analyze_compiler_metrics(self, metrics: Dict[str, Any]) -> List[OptimizationSuggestion]:
        """Analyze compiler performance metrics and generate optimization suggestions."""
        suggestions = []
        
        # Analyze memory usage
        if metrics.get('memory_used', 0) > self.memory_threshold:
            suggestions.append(OptimizationSuggestion(
                category='memory',
                priority=5,
                issue='High memory utilization detected',
                impact='Risk of compilation failures and system instability',
                recommendation='Consider increasing worker memory limits or implementing request queuing',
                metrics={'current_usage': metrics.get('memory_used', 0)}
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

        # Analyze error patterns
        if metrics.get('error_type'):
            error_suggestion = self._analyze_error_patterns(language, metrics)
            if error_suggestion:
                suggestions.append(error_suggestion)

        return suggestions

    def _update_language_metrics(self, language: str, metrics: Dict[str, Any]) -> None:
        """Update language-specific performance metrics."""
        lang_stats = self.language_metrics[language]
        lang_stats['total_executions'] += 1
        
        if not metrics.get('success', True):
            lang_stats['failed_executions'] += 1
            error_type = metrics.get('error_type', 'unknown')
            lang_stats['common_errors'][error_type] += 1

        # Update running averages
        current_avg = lang_stats['avg_compile_time']
        new_time = metrics.get('compilation_time', 0)
        lang_stats['avg_compile_time'] = (
            (current_avg * (lang_stats['total_executions'] - 1) + new_time) / 
            lang_stats['total_executions']
        )
        
        # Track peak memory
        lang_stats['peak_memory'] = max(
            lang_stats['peak_memory'],
            metrics.get('peak_memory', 0)
        )

    def _analyze_error_patterns(self, language: str, metrics: Dict[str, Any]) -> Optional[OptimizationSuggestion]:
        """Analyze error patterns and generate relevant suggestions."""
        error_type = metrics.get('error_type')
        if not error_type:
            return None

        lang_stats = self.language_metrics[language]
        error_frequency = lang_stats['common_errors'][error_type]
        total_executions = lang_stats['total_executions']

        if error_frequency / total_executions > 0.1:  # More than 10% error rate
            return OptimizationSuggestion(
                category='compiler',
                priority=5,
                issue=f'Frequent {error_type} errors in {language}',
                impact='High failure rate affecting user experience',
                recommendation=self._get_error_recommendation(error_type, language),
                metrics={
                    'error_rate': error_frequency / total_executions,
                    'total_occurrences': error_frequency
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

    def get_system_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive system health report with optimization suggestions."""
        report = {
            'languages': {},
            'system_health': {
                'memory_status': 'healthy',
                'cpu_status': 'healthy',
                'compiler_status': 'healthy'
            },
            'optimization_suggestions': []
        }

        # Analyze per-language metrics
        for language, metrics in self.language_metrics.items():
            failure_rate = (metrics['failed_executions'] / metrics['total_executions'] 
                          if metrics['total_executions'] > 0 else 0)
            
            report['languages'][language] = {
                'success_rate': 1 - failure_rate,
                'avg_compile_time': metrics['avg_compile_time'],
                'peak_memory': metrics['peak_memory'],
                'common_errors': dict(metrics['common_errors'])
            }

            # Generate language-specific suggestions
            if failure_rate > 0.05:  # More than 5% failure rate
                report['optimization_suggestions'].append({
                    'category': 'compiler',
                    'priority': 4,
                    'issue': f'High failure rate in {language}',
                    'recommendation': 'Review error patterns and implement preventive measures'
                })

        return report
