"""
Test script to parse a single section of the ICS3U curriculum
Shows each step of the parsing process with detailed logging
"""
import sys
import logging
from pathlib import Path
import re

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_parse_section(content: str, section_index: int = 0) -> None:
    """Parse and show debug info for a specific curriculum section"""
    logger = logging.getLogger(__name__)

    # Step 1: Find all section boundaries
    logger.info("\n=== Step 1: Locating Section Boundaries ===")
    section_markers = list(re.finditer(r'(?:^|\n)\s*ATTENTES\s*:', content, re.MULTILINE))

    for i, match in enumerate(section_markers):
        start_pos = match.start()
        preview = content[start_pos:start_pos+50].replace('\n', '\\n')
        logger.info(f"Section {i+1} starts at position {start_pos}: {preview}...")

    if not section_markers:
        logger.error("No section markers found!")
        return

    if section_index >= len(section_markers):
        logger.error(f"Section index {section_index} out of range, only {len(section_markers)} sections found")
        return

    # Step 2: Extract the chosen section
    logger.info("\n=== Step 2: Extracting Section Content ===")
    current_start = section_markers[section_index].start()
    next_start = section_markers[section_index + 1].start() if section_index + 1 < len(section_markers) else len(content)
    section_content = content[current_start:next_start].strip()

    logger.info(f"Raw section content ({len(section_content)} chars):")
    logger.info("-" * 50)
    logger.info(section_content)
    logger.info("-" * 50)

    # Step 3: Split into ATTENTES and CONTENUS
    logger.info("\n=== Step 3: Splitting Section Parts ===")
    contenus_pattern = r"CONTENUS\s+D'APPRENTISSAGE"
    parts = re.split(contenus_pattern, section_content, flags=re.IGNORECASE)

    if len(parts) != 2:
        logger.error(f"Failed to split section into parts. Found {len(parts)} parts instead of 2")
        logger.info("Split points found:")
        for match in re.finditer(contenus_pattern, section_content, re.IGNORECASE):
            logger.info(f"Match at position {match.start()}: {match.group()}")
        return

    attentes_text, contenus_text = parts
    logger.info("\nATTENTES part:")
    logger.info(attentes_text.strip())
    logger.info("\nCONTENUS part:")
    logger.info(contenus_text.strip())

    # Step 4: Extract expectations
    logger.info("\n=== Step 4: Extracting Expectations ===")

    # Overall expectations
    overall_exp = []
    for match in re.finditer(r'([A-Za-z]\d+)\s*\.\s*([^\n]+)', attentes_text):
        code, desc = match.groups()
        overall_exp.append((code, desc.strip()))
        logger.info(f"Found overall expectation: {code} -> {desc.strip()}")

    # Specific expectations
    logger.info("\nExtracting specific expectations...")
    current_exp = None
    current_lines = []

    for line in contenus_text.split('\n'):
        line = line.strip()
        if not line or 'pour satisfaire aux attentes' in line.lower():
            if current_exp and current_lines:
                logger.info(f"Completed multiline expectation {current_exp}: {' '.join(current_lines)}")
            continue

        # Try to match new expectation
        exp_match = re.match(r'([A-Za-z]\d+\.\d+)\s+(.+)', line)
        if exp_match:
            # Save previous if exists
            if current_exp and current_lines:
                logger.info(f"Completed expectation {current_exp}: {' '.join(current_lines)}")

            # Start new expectation
            current_exp = exp_match.group(1)
            current_lines = [exp_match.group(2)]
            logger.info(f"Started new expectation: {current_exp}")
        elif current_exp:
            current_lines.append(line)
            logger.info(f"Added line to {current_exp}: {line}")

    # Save last expectation
    if current_exp and current_lines:
        logger.info(f"Final expectation {current_exp}: {' '.join(current_lines)}")

def main():
    # Configure detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(message)s'  # Simplified format for readability
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting detailed parse test of curriculum sections...")

        # Read curriculum file
        curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum.txt'
        if not curriculum_file.exists():
            raise FileNotFoundError(f"Curriculum file not found: {curriculum_file}")

        with open(curriculum_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Test parse each section
        for section_index in range(3):  # Test first 3 sections
            logger.info(f"\n{'='*20} Testing Section {section_index + 1} {'='*20}")
            test_parse_section(content, section_index)

    except Exception as e:
        logger.error(f"Error during test parse: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()