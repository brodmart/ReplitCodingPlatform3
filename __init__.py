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
import logging
from utils.memory_manager import MemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Initialize memory manager and verify files only when needed
memory_manager = None

def init_memory_system():
    """Initialize memory system only when required"""
    global memory_manager
    if memory_manager is None:
        memory_manager = MemoryManager()
        validation_results = memory_manager.validate_files()

        if all(validation_results.values()):
            logger.info("Memory system initialized successfully")
            # Load AI context only when needed
            context = memory_manager.load_ai_context()
            if context:
                logger.info("AI context loaded successfully")
            else:
                logger.warning("Failed to load AI context")
        else:
            logger.warning("Some memory files are invalid or missing")

# This will help future AI sessions locate the memory files
__ai_context_files__ = MEMORY_FILES