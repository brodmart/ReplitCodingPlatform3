"""
Enhanced Memory Manager for AI Context

This module helps manage and maintain the AI context memory files with improved performance,
error handling, automatic versioning, and intelligent context summarization.
"""

import os
import json
import shutil
import gzip
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import uuid
import re
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

@dataclass
class ContextRelevance:
    """Stores relevance information for context entries"""
    score: float
    last_accessed: datetime
    access_count: int
    importance_weight: float

class MemoryManager:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.backup_dir = os.path.join(self.base_dir, 'memory_backups')
        self.change_log_file = os.path.join(self.base_dir, 'memory_changes.json')
        self.version_file = os.path.join(self.base_dir, 'memory_versions.json')
        self.relevance_file = os.path.join(self.base_dir, 'context_relevance.json')
        self.cache = {}
        self.relevance_scores: Dict[str, ContextRelevance] = {}
        self.vectorizer = TfidfVectorizer(stop_words='english')

        os.makedirs(self.backup_dir, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._load_relevance_scores()
        self.load_ai_context()
        self._cleanup_old_backups()

    @lru_cache(maxsize=32)
    def load_ai_context(self) -> Optional[str]:
        try:
            context_path = os.path.join(self.base_dir, 'AI_CONTEXT.md')
            if os.path.exists(context_path):
                with open(context_path, 'r') as f:
                    context = f.read()
                self.cache['ai_context'] = context
                logger.info("AI context loaded and cached successfully")
                return context
            else:
                logger.warning("AI_CONTEXT.md not found")
                return None
        except Exception as e:
            logger.error(f"Error loading AI context: {str(e)}")
            return None

    def update_timestamp(self, file_path: str) -> bool:
        try:
            backup_path = self._create_backup(file_path)
            if not backup_path:
                raise Exception("Backup creation failed")

            with open(file_path, 'r') as f:
                content = f.read()

            self._update_version(file_path)

            date_line = f"Last Updated: {datetime.now().strftime('%B %d, %Y')}"
            if "Last Updated:" in content:
                content = content.replace(content.split('\n')[1], date_line)
            else:
                header = content.split('\n')[0]
                content = f"{header}\n{date_line}\n" + '\n'.join(content.split('\n')[1:])

            if self._check_conflicts(file_path, content):
                logger.warning(f"Potential conflict detected in {file_path}")
                self._handle_conflict(file_path, content)

            self._log_change(file_path, 'update_timestamp')

            with open(file_path, 'w') as f:
                f.write(content)

            self.cache.pop(file_path, None)
            return True
        except Exception as e:
            logger.error(f"Error updating timestamp: {str(e)}")
            return False

    def _update_version(self, file_path: str) -> None:
        try:
            versions = {}
            if os.path.exists(self.version_file):
                with open(self.version_file, 'r') as f:
                    versions = json.load(f)

            file_name = os.path.basename(file_path)
            current_version = versions.get(file_name, 0)
            versions[file_name] = current_version + 1

            with open(self.version_file, 'w') as f:
                json.dump(versions, f, indent=2)
        except Exception as e:
            logger.error(f"Version update failed: {str(e)}")

    def _check_conflicts(self, file_path: str, new_content: str) -> bool:
        try:
            if file_path in self.cache:
                cached_content = self.cache[file_path]
                return cached_content != new_content
            return False
        except Exception:
            return False

    def _handle_conflict(self, file_path: str, content: str) -> None:
        conflict_path = f"{file_path}.conflict"
        try:
            with open(conflict_path, 'w') as f:
                f.write(content)
            logger.warning(f"Conflict version saved to {conflict_path}")
        except Exception as e:
            logger.error(f"Conflict handling failed: {str(e)}")

    def _create_backup(self, file_path: str) -> Optional[str]:
        try:
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(
                self.backup_dir, 
                f"{filename}.{timestamp}.bak.gz"
            )

            with open(file_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            logger.info(f"Created compressed backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            return None

    def _cleanup_old_backups(self) -> None:
        try:
            current_time = datetime.now()
            for backup_file in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, backup_file)
                file_time = datetime.fromtimestamp(os.path.getctime(backup_path))
                if current_time - file_time > timedelta(days=7):
                    os.remove(backup_path)
                    logger.info(f"Removed old backup: {backup_file}")
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")

    def validate_files(self) -> Dict[str, bool]:
        results = {}
        futures = []

        for file_name in MEMORY_FILES:
            file_path = os.path.join(self.base_dir, file_name)
            future = self.executor.submit(self._validate_single_file, file_path)
            futures.append((file_name, future))

        for file_name, future in futures:
            try:
                results[file_name] = future.result()
            except Exception as e:
                logger.error(f"Validation failed for {file_name}: {str(e)}")
                results[file_name] = False

        return results

    def _validate_single_file(self, file_path: str) -> bool:
        try:
            exists = os.path.exists(file_path)
            if exists:
                structure_valid = self._validate_file_structure(file_path)
                cross_refs_valid = self._validate_cross_references(file_path)
                content_valid = self._validate_content_format(file_path)
                return all([structure_valid, cross_refs_valid, content_valid])
            return False
        except Exception as e:
            logger.error(f"Single file validation failed: {str(e)}")
            return False

    def _validate_content_format(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            if len(content.strip()) < 10:
                return False

            headers = re.findall(r'^#{1,6}\s+.+$', content, re.MULTILINE)
            if not headers:
                return False

            return True
        except Exception:
            return False

    def _log_change(self, file_path: str, operation: str) -> None:
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'file': os.path.basename(file_path),
                'operation': operation,
                'version': self._get_current_version(file_path),
                'metadata': {
                    'size': os.path.getsize(file_path),
                    'modified_time': datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    ).isoformat()
                }
            }

            existing_logs = []
            if os.path.exists(self.change_log_file):
                with open(self.change_log_file, 'r') as f:
                    existing_logs = json.load(f)

            existing_logs.append(log_entry)

            with open(self.change_log_file, 'w') as f:
                json.dump(existing_logs, f, indent=2)
            logger.info(f"Logged change: {operation} on {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Logging failed: {str(e)}")

    def _get_current_version(self, file_path: str) -> int:
        try:
            if os.path.exists(self.version_file):
                with open(self.version_file, 'r') as f:
                    versions = json.load(f)
                return versions.get(os.path.basename(file_path), 0)
            return 0
        except Exception:
            return 0

    def _validate_file_structure(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            required_sections = ['#', 'Last Updated:']
            return all(section in content for section in required_sections)
        except Exception:
            return False

    def _validate_cross_references(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            references = re.findall(r'\[.*?\]\((.*?\.md)\)', content)

            for ref in references:
                ref_path = os.path.join(self.base_dir, ref)
                if not os.path.exists(ref_path):
                    logger.warning(f"Missing cross-reference in {file_path}: {ref}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating cross-references: {str(e)}")
            return False

    def update_all_timestamps(self) -> List[str]:
        updated = []
        for file_name in MEMORY_FILES:
            file_path = os.path.join(self.base_dir, file_name)
            if self.update_timestamp(file_path):
                updated.append(file_name)
        return updated

    def _load_relevance_scores(self) -> None:
        try:
            if os.path.exists(self.relevance_file):
                with open(self.relevance_file, 'r') as f:
                    data = json.load(f)
                    for file_name, score_data in data.items():
                        self.relevance_scores[file_name] = ContextRelevance(
                            score=score_data['score'],
                            last_accessed=datetime.fromisoformat(score_data['last_accessed']),
                            access_count=score_data['access_count'],
                            importance_weight=score_data['importance_weight']
                        )
        except Exception as e:
            logger.error(f"Error loading relevance scores: {str(e)}")

    def _save_relevance_scores(self) -> None:
        try:
            data = {
                file_name: {
                    'score': relevance.score,
                    'last_accessed': relevance.last_accessed.isoformat(),
                    'access_count': relevance.access_count,
                    'importance_weight': relevance.importance_weight
                }
                for file_name, relevance in self.relevance_scores.items()
            }
            with open(self.relevance_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving relevance scores: {str(e)}")

    def calculate_context_relevance(self, file_path: str, current_context: str) -> float:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            tfidf_matrix = self.vectorizer.fit_transform([content, current_context])
            similarity = (tfidf_matrix * tfidf_matrix.T).toarray()[0][1]

            file_name = os.path.basename(file_path)
            relevance = self.relevance_scores.get(file_name, ContextRelevance(
                score=0.0,
                last_accessed=datetime.now(),
                access_count=0,
                importance_weight=1.0
            ))

            relevance.access_count += 1
            relevance.last_accessed = datetime.now()

            time_factor = 1.0 / (1.0 + (datetime.now() - relevance.last_accessed).days)
            usage_factor = min(1.0, relevance.access_count / 100)

            final_score = (
                similarity * 0.4 +
                time_factor * 0.3 +
                usage_factor * 0.3
            ) * relevance.importance_weight

            relevance.score = final_score
            self.relevance_scores[file_name] = relevance
            self._save_relevance_scores()

            return final_score

        except Exception as e:
            logger.error(f"Error calculating relevance: {str(e)}")
            return 0.0

    def prune_outdated_context(self, threshold: float = 0.3) -> List[str]:
        pruned_files = []
        try:
            for file_name, relevance in self.relevance_scores.items():
                if (
                    relevance.score < threshold and
                    datetime.now() - relevance.last_accessed > timedelta(days=30)
                ):
                    file_path = os.path.join(self.base_dir, file_name)
                    backup_path = self._create_backup(file_path)
                    if backup_path:
                        pruned_files.append(file_name)
                        os.remove(file_path) #remove the file after backup
                        logger.info(f"Pruned outdated context: {file_name}")
            return pruned_files
        except Exception as e:
            logger.error(f"Error pruning context: {str(e)}")
            return []

    def compress_context(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            headers = re.findall(r'^#{1,3}\s+.*$', content, re.MULTILINE)
            key_points = re.findall(r'^\s*[-*]\s+.*$', content, re.MULTILINE)

            sentences = re.split(r'[.!?]+', content)
            sentence_scores = []

            for sentence in sentences:
                score = 0
                if any(term in sentence.lower() for term in ['important', 'critical', 'key', 'must']):
                    score += 2
                if 10 <= len(sentence.split()) <= 30:
                    score += 1
                sentence_scores.append((sentence, score))

            important_sentences = [s[0] for s in sorted(sentence_scores, key=lambda x: x[1], reverse=True)[:10]]

            compressed_content = "# Compressed Context Summary\n\n"
            compressed_content += "## Key Headers\n" + '\n'.join(headers) + "\n\n"
            compressed_content += "## Important Points\n" + '\n'.join(key_points) + "\n\n"
            compressed_content += "## Key Content\n" + '\n'.join(important_sentences)

            compressed_path = file_path + '.compressed'
            with open(compressed_path, 'w') as f:
                f.write(compressed_content)

            return compressed_path

        except Exception as e:
            logger.error(f"Error compressing context: {str(e)}")
            return None


MEMORY_FILES = [
    'AI_CONTEXT.md',
    'project_memory.md',
    'architectural_decisions.md',
    'development_patterns.md',
    'integration_notes.md'
]

# Initialize the memory manager
memory_manager = MemoryManager()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    validation = memory_manager.validate_files()
    if not all(validation.values()):
        logger.warning("Some memory files are missing or invalid: %s", 
              [f for f, valid in validation.items() if not valid])

    updated = memory_manager.update_all_timestamps()
    logger.info("Updated timestamps in: %s", ', '.join(updated))

    #Example usage of new functions
    current_context = "This is the current context."
    for file_name in MEMORY_FILES:
        file_path = os.path.join(memory_manager.base_dir, file_name)
        relevance_score = memory_manager.calculate_context_relevance(file_path, current_context)
        logger.info(f"Relevance score for {file_name}: {relevance_score}")

    pruned = memory_manager.prune_outdated_context()
    logger.info(f"Pruned files: {pruned}")

    for file_name in MEMORY_FILES:
        file_path = os.path.join(memory_manager.base_dir, file_name)
        compressed_path = memory_manager.compress_context(file_path)
        if compressed_path:
            logger.info(f"Compressed {file_name} to {compressed_path}")