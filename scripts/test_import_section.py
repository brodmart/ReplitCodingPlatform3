"""
Test script to import the first section of the ICS3U curriculum
"""
import sys
import logging
from pathlib import Path
import chardet

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from utils.curriculum_importer import CurriculumImporter

def detect_encoding(file_path):
    """Detect the file encoding"""
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def main():
    # Configure detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting test import of first ICS3U curriculum section...")

        with app.app_context():
            # Verify database connection
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Found tables: {tables}")

            # Read curriculum file
            curriculum_file = project_root / 'attached_assets' / 'Pasted--Introduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initie-l--1737160312256.txt'
            
            if not curriculum_file.exists():
                raise FileNotFoundError(f"Curriculum file not found: {curriculum_file}")

            # Detect and use correct encoding
            encoding = detect_encoding(curriculum_file)
            logger.info(f"Using encoding: {encoding}")

            with open(curriculum_file, 'r', encoding=encoding) as f:
                content = f.read()
                logger.info(f"Successfully read file. Content length: {len(content)} bytes")
                logger.debug(f"Content preview:\n{content[:500]}")

                # Create importer and try importing first section
                importer = CurriculumImporter()
                importer.import_first_section(content)

    except Exception as e:
        logger.error(f"Error during test import: {str(e)}", exc_info=True)
        sys.exit(1)

    logger.info("Test import completed!")

if __name__ == '__main__':
    main()
