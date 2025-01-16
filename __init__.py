"""
AI Context Loader

Key Project Memory Files:
- AI_CONTEXT.md: Entry point for AI sessions
- project_memory.md: Project overview and status
- architectural_decisions.md: Key technical decisions
- development_patterns.md: Development patterns
- integration_notes.md: System integration details

These files maintain project context across AI sessions.
Update them when making significant changes.
"""

import os

# Define paths to memory files
MEMORY_FILES = [
    'AI_CONTEXT.md',
    'project_memory.md',
    'architectural_decisions.md',
    'development_patterns.md',
    'integration_notes.md'
]

def get_memory_file_paths():
    """Return paths to all memory files"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return [os.path.join(base_dir, file) for file in MEMORY_FILES]

def verify_memory_files():
    """Verify all memory files exist"""
    missing = []
    for file_path in get_memory_file_paths():
        if not os.path.exists(file_path):
            missing.append(os.path.basename(file_path))
    return missing

# This will help future AI sessions locate the memory files
__ai_context_files__ = MEMORY_FILES
