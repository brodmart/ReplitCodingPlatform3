"""
Memory Manager for AI Context

This module helps manage and maintain the AI context memory files.
It provides utilities for:
- Updating timestamps
- Validating file consistency
- Managing cross-references
- Tracking AI session changes
- Preventing accidental overwrites
"""

import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import uuid
import re
import logging

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
        os.makedirs(self.backup_dir, exist_ok=True)
        # Automatically load context on initialization
        self.load_ai_context()

    def load_ai_context(self) -> Optional[str]:
        """Load and return the AI context at the start of each session."""
        try:
            context_path = os.path.join(self.base_dir, 'AI_CONTEXT.md')
            if os.path.exists(context_path):
                with open(context_path, 'r') as f:
                    context = f.read()
                logger.info("AI context loaded successfully")
                return context
            else:
                logger.warning("AI_CONTEXT.md not found")
                return None
        except Exception as e:
            logger.error(f"Error loading AI context: {str(e)}")
            return None

    def update_timestamp(self, file_path: str) -> bool:
        """Update the timestamp in a memory file and log the change."""
        try:
            # Create backup before modification
            self._create_backup(file_path)

            with open(file_path, 'r') as f:
                content = f.read()

            # Update or add timestamp
            date_line = f"Last Updated: {datetime.now().strftime('%B %d, %Y')}"
            if "Last Updated:" in content:
                content = content.replace(content.split('\n')[1], date_line)
            else:
                header = content.split('\n')[0]
                content = f"{header}\n{date_line}\n" + '\n'.join(content.split('\n')[1:])

            # Log change before writing
            self._log_change(file_path, 'update_timestamp')

            with open(file_path, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error updating timestamp: {str(e)}")
            return False

    def validate_files(self) -> Dict[str, bool]:
        """Validate all memory files exist and have proper structure."""
        results = {}
        for file_name in MEMORY_FILES:
            file_path = os.path.join(self.base_dir, file_name)
            exists = os.path.exists(file_path)
            if exists:
                structure_valid = self._validate_file_structure(file_path)
                cross_refs_valid = self._validate_cross_references(file_path)
                results[file_name] = exists and structure_valid and cross_refs_valid
            else:
                results[file_name] = False
                logger.warning(f"Memory file not found: {file_name}")
        return results

    def update_all_timestamps(self) -> List[str]:
        """Update timestamps in all memory files."""
        updated = []
        for file_name in MEMORY_FILES:
            file_path = os.path.join(self.base_dir, file_name)
            if self.update_timestamp(file_path):
                updated.append(file_name)
        return updated

    def _create_backup(self, file_path: str) -> bool:
        """Create a backup of a file before modification."""
        try:
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(
                self.backup_dir, 
                f"{filename}.{timestamp}.bak"
            )
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            return False

    def _log_change(self, file_path: str, operation: str) -> None:
        """Log changes made to memory files."""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'file': os.path.basename(file_path),
                'operation': operation
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

# Initialize the memory manager
memory_manager = MemoryManager()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Validate files on import
    validation = memory_manager.validate_files()
    if not all(validation.values()):
        logger.warning("Some memory files are missing or invalid:", 
              [f for f, valid in validation.items() if not valid])

    # Update timestamps
    updated = memory_manager.update_all_timestamps()
    logger.info(f"Updated timestamps in: {', '.join(updated)}")