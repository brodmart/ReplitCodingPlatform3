"""
Test script to parse a single section of the ICS3U curriculum
Shows each step of the parsing process
"""
import sys
import logging
from pathlib import Path

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db

def main():
    # Configure detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting test parse of a single curriculum section...")

        # Read curriculum file
        curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum.txt'
        if not curriculum_file.exists():
            raise FileNotFoundError(f"Curriculum file not found: {curriculum_file}")

        with open(curriculum_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract first complete section (starting from ATTENTES)
        start_idx = content.find('ATTENTES:')
        if start_idx == -1:
            raise ValueError("Could not find ATTENTES section")

        end_idx = content.find('ATTENTES:', start_idx + 1)
        if end_idx == -1:
            end_idx = len(content)

        section_content = content[start_idx:end_idx].strip()
        logger.info("\n=== Raw Section Content ===\n%s\n==================", section_content)

        # Split into ATTENTES and CONTENUS parts
        attentes_start = section_content.find('ATTENTES:')
        contenus_start = section_content.find('CONTENUS D\'APPRENTISSAGE')

        if attentes_start == -1 or contenus_start == -1:
            raise ValueError("Could not find required section markers")

        attentes_text = section_content[attentes_start:contenus_start].strip()
        contenus_text = section_content[contenus_start:].strip()

        logger.info("\n=== ATTENTES Part ===\n%s", attentes_text)
        logger.info("\n=== CONTENUS Part ===\n%s", contenus_text)

    except Exception as e:
        logger.error(f"Error during test parse: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()