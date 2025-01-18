"""
Script to analyze the structure of the curriculum file
"""
import sys
from pathlib import Path
import logging
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s'  # Simplified format for readability
)
logger = logging.getLogger(__name__)

def analyze_content_structure(content: str) -> List[Tuple[str, int]]:
    """Analyze content structure and return section positions"""
    section_markers = []
    lines = content.split('\n')

    for i, line in enumerate(lines):
        # Look for section markers (A., B., C., D.)
        if any(line.strip().startswith(f"{letter}.") for letter in ['A', 'B', 'C', 'D']):
            section_markers.append((line.strip(), i + 1))

    return section_markers

def analyze_curriculum_file(file_path):
    """Analyze and display the structure of a curriculum file"""
    try:
        # First try UTF-8
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try Latin-1
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()

        # Display basic file info
        logger.info("\n=== FILE INFORMATION ===")
        logger.info(f"File size: {Path(file_path).stat().st_size} bytes")
        logger.info(f"Total lines: {len(content.splitlines())}")

        # Display content structure
        logger.info("\n=== CONTENT STRUCTURE ===")
        section_markers = analyze_content_structure(content)
        logger.info("\nSection markers found:")
        for marker, line_num in section_markers:
            logger.info(f"Line {line_num}: {marker}")

        # Look for key French curriculum elements
        logger.info("\n=== KEY ELEMENTS ===")
        key_terms = ['ATTENTES', 'CONTENUS', 'À la fin de ce cours']
        for term in key_terms:
            positions = [i for i in range(len(content)) if content.startswith(term, i)]
            if positions:
                logger.info(f"\nFound '{term}' at positions: {positions}")
                for pos in positions[:2]:  # Show context for first 2 occurrences
                    start = max(0, pos - 50)
                    end = min(len(content), pos + 100)
                    context = content[start:end].replace('\n', '↵')
                    logger.info(f"Context: ...{context}...")

        # Analyze section content patterns
        logger.info("\n=== SECTION PATTERNS ===")
        for i, (marker, line_num) in enumerate(section_markers):
            next_pos = section_markers[i + 1][1] if i + 1 < len(section_markers) else len(content.splitlines())
            section_content = '\n'.join(content.splitlines()[line_num-1:next_pos])

            # Look for expectations patterns
            logger.info(f"\nAnalyzing section starting with: {marker}")

            # Find numbered items
            numbered_items = [line.strip() for line in section_content.splitlines() 
                            if any(line.strip().startswith(f"{marker.split('.')[0]}{num}") 
                                 for num in range(10))]

            if numbered_items:
                logger.info("Found numbered items:")
                for item in numbered_items[:3]:  # Show first 3 examples
                    logger.info(f"  {item}")

    except Exception as e:
        logger.error(f"Error analyzing file: {str(e)}")
        raise

if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    curriculum_file = project_root / 'attached_assets' / 'Pasted--Introduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initie-l--1737160312256.txt'

    if not curriculum_file.exists():
        logger.error(f"Curriculum file not found: {curriculum_file}")
        sys.exit(1)

    analyze_curriculum_file(curriculum_file)