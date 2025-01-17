"""
Enhanced Memory Manager for AI Context

This module helps manage and maintain the AI context memory files with improved performance,
error handling, and automatic versioning.
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

logger = logging.getLogger(__name__)

MEMORY_FILES = [
    'AI_CONTEXT.md',
    'project_memory.md',
    'architectural_decisions.md',
    'development_patterns.md',
    'integration_notes.md'
]

class MemoryManager:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.backup_dir = os.path.join(self.base_dir, 'memory_backups')
        self.change_log_file = os.path.join(self.base_dir, 'memory_changes.json')
        self.version_file = os.path.join(self.base_dir, 'memory_versions.json')
        self.cache = {}
        os.makedirs(self.backup_dir, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.load_ai_context()
        self._cleanup_old_backups()

    @lru_cache(maxsize=32)
    def load_ai_context(self) -> Optional[str]:
        """Load and cache the AI context at the start of each session."""
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
        """Update the timestamp in a memory file and log the change with versioning."""
        try:
            # Create backup before modification
            backup_path = self._create_backup(file_path)
            if not backup_path:
                raise Exception("Backup creation failed")

            with open(file_path, 'r') as f:
                content = f.read()

            # Update version before modifying
            self._update_version(file_path)

            # Update or add timestamp
            date_line = f"Last Updated: {datetime.now().strftime('%B %d, %Y')}"
            if "Last Updated:" in content:
                content = content.replace(content.split('\n')[1], date_line)
            else:
                header = content.split('\n')[0]
                content = f"{header}\n{date_line}\n" + '\n'.join(content.split('\n')[1:])

            # Check for conflicts
            if self._check_conflicts(file_path, content):
                logger.warning(f"Potential conflict detected in {file_path}")
                self._handle_conflict(file_path, content)

            # Log change before writing
            self._log_change(file_path, 'update_timestamp')

            with open(file_path, 'w') as f:
                f.write(content)

            # Clear cache for this file
            self.cache.pop(file_path, None)
            return True
        except Exception as e:
            logger.error(f"Error updating timestamp: {str(e)}")
            return False

    def _update_version(self, file_path: str) -> None:
        """Track versions of memory files."""
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
        """Check for potential conflicts in file changes."""
        try:
            if file_path in self.cache:
                cached_content = self.cache[file_path]
                return cached_content != new_content
            return False
        except Exception:
            return False

    def _handle_conflict(self, file_path: str, content: str) -> None:
        """Handle detected conflicts in file changes."""
        conflict_path = f"{file_path}.conflict"
        try:
            with open(conflict_path, 'w') as f:
                f.write(content)
            logger.warning(f"Conflict version saved to {conflict_path}")
        except Exception as e:
            logger.error(f"Conflict handling failed: {str(e)}")

    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create a compressed backup of a file before modification."""
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
        """Clean up backups older than 7 days."""
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
        """Validate all memory files exist and have proper structure."""
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
        """Validate a single memory file."""
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
        """Validate the content format of a memory file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for minimum content requirements
            if len(content.strip()) < 10:
                return False

            # Validate markdown structure
            headers = re.findall(r'^#{1,6}\s+.+$', content, re.MULTILINE)
            if not headers:
                return False

            return True
        except Exception:
            return False

    def _log_change(self, file_path: str, operation: str) -> None:
        """Log changes made to memory files with enhanced metadata."""
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
        """Get the current version number of a file."""
        try:
            if os.path.exists(self.version_file):
                with open(self.version_file, 'r') as f:
                    versions = json.load(f)
                return versions.get(os.path.basename(file_path), 0)
            return 0
        except Exception:
            return 0

    def _validate_file_structure(self, file_path: str) -> bool:
        """Validate the structure of a memory file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for required sections
            required_sections = ['#', 'Last Updated:']
            return all(section in content for section in required_sections)
        except Exception:
            return False

    def _validate_cross_references(self, file_path: str) -> bool:
        """Validate cross-references between memory files."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Find all markdown-style references to other memory files
            references = re.findall(r'\[.*?\]\((.*?\.md)\)', content)

            # Verify each referenced file exists
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
        """Update timestamps in all memory files."""
        updated = []
        for file_name in MEMORY_FILES:
            file_path = os.path.join(self.base_dir, file_name)
            if self.update_timestamp(file_path):
                updated.append(file_name)
        return updated


# Initialize the memory manager
memory_manager = MemoryManager()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Validate files on import
    validation = memory_manager.validate_files()
    if not all(validation.values()):
        logger.warning("Some memory files are missing or invalid: %s", 
              [f for f, valid in validation.items() if not valid])

    # Update timestamps
    updated = memory_manager.update_all_timestamps()
    logger.info("Updated timestamps in: %s", ', '.join(updated))