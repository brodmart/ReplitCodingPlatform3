"""
Test script to parse a single section of the ICS3U curriculum
Shows each step of the parsing process
"""
import sys
import logging
import re
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

        # Debug: Show where all ATTENTES sections are
        all_attentes = list(re.finditer(r'(?:^|\n)\s*ATTENTES\s*:', content, re.MULTILINE))
        logger.info(f"Found {len(all_attentes)} potential ATTENTES sections at positions: " + 
                   ", ".join(str(m.start()) for m in all_attentes))

        # Get the second section (index 1)
        if len(all_attentes) < 2:
            raise ValueError("Not enough sections found")

        current_section_start = all_attentes[1].start()
        next_section_start = all_attentes[2].start() if len(all_attentes) > 2 else len(content)

        # Extract the full section content
        section_content = content[current_section_start:next_section_start].strip()
        logger.info("\n=== Raw Section Content ===\n%s\n==================", section_content)

        # Extract expectations and content
        attentes_text = ""
        contenus_text = ""
        current_subtitle = ""

        # Split the content into lines for processing
        lines = section_content.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('ATTENTES:'):
                current_section = 'attentes'
                continue
            elif line.startswith('CONTENUS D\'APPRENTISSAGE'):
                current_section = 'contenus'
                continue
            elif re.match(r'^[A-Z][\w\s-]+$', line):  # Subtitle like "Syntaxe et sémantique"
                current_subtitle = line
                continue
            elif line.startswith('Pour satisfaire aux attentes'):
                continue

            if current_section:
                current_content.append(line)

            if current_section == 'attentes':
                attentes_text = '\n'.join(current_content)
            elif current_section == 'contenus':
                contenus_text = '\n'.join(current_content)

        logger.info("\n=== ATTENTES Part ===\n%s", attentes_text)
        logger.info("\n=== CONTENUS Part ===\n%s", contenus_text)

        # Extract expectations using more flexible regex
        overall_exp = re.findall(r'([A-D]\d+)\s*\.\s*([^\n]+)', attentes_text)
        specific_exp = re.findall(r'([A-D]\d+\.\d+)\s*([^\n]+(?:\n[^\n]+)*)', contenus_text)

        logger.info("\n=== Parsed Expectations ===")
        logger.info("Overall Expectations:")
        for code, desc in overall_exp:
            logger.info(f"{code}: {desc}")

        logger.info("\nSpecific Expectations:")
        for code, desc in specific_exp:
            # Join multiline descriptions with spaces
            desc = ' '.join(line.strip() for line in desc.split('\n'))
            logger.info(f"{code}: {desc}")

    except Exception as e:
        logger.error(f"Error during test parse: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()