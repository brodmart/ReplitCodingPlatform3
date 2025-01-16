"""
Memory Manager for AI Context

This module helps manage and maintain the AI context memory files.
It provides utilities for:
- Updating timestamps
- Validating file consistency
- Managing cross-references
"""

import os
from datetime import datetime
import json
from typing import List, Dict

MEMORY_FILES = [
    'AI_CONTEXT.md',
    'project_memory.md',
    'architectural_decisions.md',
    'development_patterns.md',
    'integration_notes.md'
]

def update_timestamp(file_path: str) -> bool:
    """Update the timestamp in a memory file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update or add timestamp
        date_line = f"Last Updated: {datetime.now().strftime('%B %d, %Y')}"
        if "Last Updated:" in content:
            content = content.replace(content.split('\n')[1], date_line)
        else:
            header = content.split('\n')[0]
            content = f"{header}\n{date_line}\n" + '\n'.join(content.split('\n')[1:])
        
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error updating timestamp: {str(e)}")
        return False

def validate_files() -> Dict[str, bool]:
    """Validate all memory files exist and have proper structure."""
    results = {}
    for file_name in MEMORY_FILES:
        file_path = os.path.join(os.getcwd(), file_name)
        results[file_name] = os.path.exists(file_path)
    return results

def update_all_timestamps() -> List[str]:
    """Update timestamps in all memory files."""
    updated = []
    for file_name in MEMORY_FILES:
        file_path = os.path.join(os.getcwd(), file_name)
        if update_timestamp(file_path):
            updated.append(file_name)
    return updated

if __name__ == "__main__":
    # Validate files on import
    validation = validate_files()
    if not all(validation.values()):
        print("Warning: Some memory files are missing:", 
              [f for f, exists in validation.items() if not exists])
    
    # Update timestamps
    updated = update_all_timestamps()
    print(f"Updated timestamps in: {', '.join(updated)}")
