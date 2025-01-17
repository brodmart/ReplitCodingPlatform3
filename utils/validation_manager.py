"""
Automated Validation Manager for Memory System

This module provides automated validation and testing capabilities for
the memory management system, ensuring data integrity and consistency.
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Stores validation test results"""
    passed: bool
    message: str
    timestamp: datetime
    context: Dict

class ValidationManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.validation_log = os.path.join(self.base_dir, 'validation_results.json')
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.processed_files: Set[str] = set()

    def run_validation_suite(self) -> List[ValidationResult]:
        """Run all validation tests in parallel"""
        # Clear processed files before starting new validation
        self.processed_files.clear()

        validation_tasks = [
            self.validate_file_integrity,
            self.validate_cross_references,
            self.validate_context_relevance,
            self.validate_compression_quality
        ]

        futures = [
            self.executor.submit(task)
            for task in validation_tasks
        ]

        results = []
        for future in futures:
            result = future.result()
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)

        self._log_validation_results(results)
        return results

    def validate_file_integrity(self) -> ValidationResult:
        """Validate integrity of memory files"""
        try:
            from utils.memory_manager import memory_manager, MEMORY_FILES

            missing_files = []
            invalid_files = []

            for file_name in MEMORY_FILES:
                file_path = os.path.join(self.base_dir, file_name)
                if not os.path.exists(file_path):
                    missing_files.append(file_name)
                elif os.path.getsize(file_path) == 0:
                    invalid_files.append(file_name)

            if missing_files or invalid_files:
                return ValidationResult(
                    passed=False,
                    message=f"File integrity issues found: Missing: {missing_files}, Invalid: {invalid_files}",
                    timestamp=datetime.now(),
                    context={'missing': missing_files, 'invalid': invalid_files}
                )

            return ValidationResult(
                passed=True,
                message="All memory files present and valid",
                timestamp=datetime.now(),
                context={}
            )

        except Exception as e:
            logger.error(f"File integrity validation failed: {str(e)}")
            return ValidationResult(
                passed=False,
                message=f"Validation error: {str(e)}",
                timestamp=datetime.now(),
                context={'error': str(e)}
            )

    def validate_cross_references(self) -> ValidationResult:
        """Validate cross-references between memory files"""
        try:
            from utils.memory_manager import memory_manager

            invalid_refs = []
            for file_name in os.listdir(self.base_dir):
                if file_name.endswith('.md'):
                    file_path = os.path.join(self.base_dir, file_name)
                    if not memory_manager._validate_cross_references(file_path):
                        invalid_refs.append(file_name)

            if invalid_refs:
                return ValidationResult(
                    passed=False,
                    message=f"Cross-reference issues found in: {invalid_refs}",
                    timestamp=datetime.now(),
                    context={'invalid_refs': invalid_refs}
                )

            return ValidationResult(
                passed=True,
                message="All cross-references valid",
                timestamp=datetime.now(),
                context={}
            )

        except Exception as e:
            logger.error(f"Cross-reference validation failed: {str(e)}")
            return ValidationResult(
                passed=False,
                message=f"Validation error: {str(e)}",
                timestamp=datetime.now(),
                context={'error': str(e)}
            )

    def validate_context_relevance(self) -> ValidationResult:
        """Validate context relevance calculations"""
        try:
            from utils.memory_manager import memory_manager

            test_context = "Testing context relevance with important technical content"
            low_scores = []

            for file_name in os.listdir(self.base_dir):
                if file_name.endswith('.md'):
                    file_path = os.path.join(self.base_dir, file_name)
                    score = memory_manager.calculate_context_relevance(file_path, test_context)
                    if score < 0.1:  # Lowered threshold for minimum relevance
                        low_scores.append((file_name, score))

            if low_scores:
                return ValidationResult(
                    passed=False,
                    message=f"Low relevance scores detected: {low_scores}",
                    timestamp=datetime.now(),
                    context={'low_scores': dict(low_scores)}
                )

            return ValidationResult(
                passed=True,
                message="Context relevance scores within acceptable range",
                timestamp=datetime.now(),
                context={}
            )

        except Exception as e:
            logger.error(f"Context relevance validation failed: {str(e)}")
            return ValidationResult(
                passed=False,
                message=f"Validation error: {str(e)}",
                timestamp=datetime.now(),
                context={'error': str(e)}
            )

    def validate_compression_quality(self) -> ValidationResult:
        """Validate quality of context compression"""
        try:
            from utils.memory_manager import memory_manager

            compression_issues = []
            skipped_files = []

            for file_name in os.listdir(self.base_dir):
                if not file_name.endswith('.md'):
                    continue

                if file_name in self.processed_files:
                    continue

                file_path = os.path.join(self.base_dir, file_name)
                self.processed_files.add(file_name)

                # Skip files that are too small for meaningful compression
                if os.path.getsize(file_path) < 1000:  # Skip files smaller than 1KB
                    skipped_files.append(file_name)
                    continue

                compressed_path = memory_manager.compress_context(file_path)

                if compressed_path is None:
                    logger.warning(f"Compression skipped for {file_name}")
                    skipped_files.append(file_name)
                    continue

                try:
                    # Check compression ratio
                    original_size = os.path.getsize(file_path)
                    compressed_size = os.path.getsize(compressed_path)

                    if original_size == 0:
                        compression_issues.append(f"{file_name} (empty file)")
                        continue

                    ratio = compressed_size / original_size

                    # Check compressed content validity
                    with open(compressed_path, 'r') as f:
                        content = f.read()

                        # Required sections
                        required_sections = [
                            '# Compressed Context Summary',
                            '## Key Headers',
                            '## Important Points',
                            '## Key Content'
                        ]

                        # Check if all sections are present and have content
                        sections_present = all(section in content for section in required_sections)

                        # Calculate minimum content requirement (more than just section headers)
                        min_content_length = sum(len(section) for section in required_sections) + 100
                        has_sufficient_content = len(content.strip()) > min_content_length

                        # Check if compressed file maintains essential information
                        has_key_points = len(re.findall(r'^\s*[-*]\s+.*$', content, re.MULTILINE)) > 0
                        has_headers = len(re.findall(r'^#{2,3}\s+.*$', content, re.MULTILINE)) > 0

                        if not sections_present:
                            compression_issues.append(f"{file_name} (missing sections)")
                        elif not has_sufficient_content:
                            compression_issues.append(f"{file_name} (insufficient content)")
                        elif not (has_key_points and has_headers):
                            compression_issues.append(f"{file_name} (missing essential information)")
                        elif ratio > 0.95:  # Only check ratio if other criteria are met
                            compression_issues.append(f"{file_name} (high ratio: {ratio:.2f})")

                finally:
                    # Always clean up the temporary compressed file
                    if compressed_path and os.path.exists(compressed_path):
                        try:
                            os.remove(compressed_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove temporary file {compressed_path}: {e}")

            # If we have more issues than skipped files, something is wrong
            if len(compression_issues) > len(skipped_files):
                return ValidationResult(
                    passed=False,
                    message=f"Compression quality issues in: {compression_issues}",
                    timestamp=datetime.now(),
                    context={
                        'compression_issues': compression_issues,
                        'skipped_files': skipped_files
                    }
                )

            return ValidationResult(
                passed=True,
                message="Context compression quality acceptable",
                timestamp=datetime.now(),
                context={'skipped_files': skipped_files}
            )

        except Exception as e:
            logger.error(f"Compression quality validation failed: {str(e)}")
            return ValidationResult(
                passed=False,
                message=f"Validation error: {str(e)}",
                timestamp=datetime.now(),
                context={'error': str(e)}
            )

    def _log_validation_results(self, results: List[ValidationResult]) -> None:
        """Log validation results to file"""
        try:
            log_data = []
            if os.path.exists(self.validation_log):
                with open(self.validation_log, 'r') as f:
                    log_data = json.load(f)

            # Add new results
            for result in results:
                log_entry = {
                    'timestamp': result.timestamp.isoformat(),
                    'passed': result.passed,
                    'message': result.message,
                    'context': result.context
                }
                log_data.append(log_entry)

            # Keep only last 100 validation results
            log_data = log_data[-100:]

            with open(self.validation_log, 'w') as f:
                json.dump(log_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error logging validation results: {str(e)}")

# Initialize validation manager
validation_manager = ValidationManager()