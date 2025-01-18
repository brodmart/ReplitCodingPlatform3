"""
Script to analyze the structure of the curriculum file
"""
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s'  # Simplified format for readability
)
logger = logging.getLogger(__name__)

def analyze_curriculum_file(file_path):
    """Analyze and display the structure of a curriculum file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Display raw content with clear section markers
        logger.info("\n=== RAW CONTENT STRUCTURE ===")
        logger.info("Length: %d characters", len(content))
        logger.info("\nFirst 1000 characters with marked newlines:")
        logger.info("-" * 50)
        formatted_content = content[:1000].replace('\n', '↵\n')
        logger.info(formatted_content)
        logger.info("-" * 50)

        # Look for major section markers
        logger.info("\n=== SECTION MARKERS ===")
        markers = ['ATTENTES', 'CONTENUS', 'A.', 'B.', 'C.', 'D.']
        for marker in markers:
            positions = [i for i in range(len(content)) if content.startswith(marker, i)]
            if positions:
                logger.info(f"\nFound '{marker}' at positions: {positions}")
                for pos in positions[:3]:  # Show context for first 3 occurrences
                    start = max(0, pos - 50)
                    end = min(len(content), pos + 50)
                    context = content[start:end].replace('\n', '↵')
                    logger.info(f"Context: ...{context}...")

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
