"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from app import db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        # Normalize different types of apostrophes
        text = text.replace('''', "'")
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _validate_content_structure(self, content: str) -> bool:
        """Pre-validate content structure before parsing"""
        try:
            self.logger.debug("Starting content validation...")

            # Find all ATTENTES sections with more flexible pattern
            attentes_matches = list(re.finditer(r'(?:^|\n)\s*ATTENTES\s*:', content, re.MULTILINE | re.IGNORECASE))
            if not attentes_matches:
                self.logger.error("No ATTENTES sections found")
                return False

            # Verify CONTENUS sections with more flexible pattern for apostrophes
            contenus_pattern = r"CONTENUS\s+D[''']APPRENTISSAGE"
            contenus_matches = list(re.finditer(contenus_pattern, content, re.MULTILINE | re.IGNORECASE))
            if not contenus_matches:
                self.logger.error("No CONTENUS sections found")
                self.logger.debug("Content preview: " + content[:500])
                return False

            # Verify expectations format
            overall_exp = re.findall(r'[A-D]\d+\.', content)
            specific_exp = re.findall(r'[A-D]\d+\.\d+', content)

            if not overall_exp or not specific_exp:
                self.logger.error("No valid expectations found")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return False

    def _extract_sections(self, content: str) -> List[Dict]:
        """Extract curriculum sections"""
        sections = []
        try:
            # Find all ATTENTES section starts
            attentes_matches = list(re.finditer(r'(?:^|\n)\s*ATTENTES\s*:', content, re.MULTILINE))
            self.logger.debug(f"Found {len(attentes_matches)} sections to process")

            for i, current_match in enumerate(attentes_matches):
                current_start = current_match.start()
                next_start = attentes_matches[i + 1].start() if i + 1 < len(attentes_matches) else len(content)
                section_content = content[current_start:next_start].strip()

                # Process section content line by line
                lines = section_content.split('\n')
                current_section = None
                attentes_lines = []
                contenus_lines = []
                current_subtitle = ""

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Handle section markers
                    if line.startswith('ATTENTES:'):
                        current_section = 'attentes'
                        continue
                    elif any(line.startswith(f"CONTENUS D{apos}APPRENTISSAGE") for apos in ["'", "’", "’"]):
                        current_section = 'contenus'
                        continue
                    elif re.match(r'^[A-Z][\w\s-]+$', line):
                        current_subtitle = line
                        continue
                    elif line.startswith('Pour satisfaire aux attentes'):
                        continue

                    # Add content to appropriate section
                    if current_section == 'attentes':
                        attentes_lines.append(line)
                    elif current_section == 'contenus':
                        contenus_lines.append(line)

                # Extract strand code from first expectation
                strand_code = None
                first_exp = re.search(r'([A-D])\d+\.', '\n'.join(attentes_lines))
                if first_exp:
                    strand_code = first_exp.group(1)

                if not strand_code:
                    self.logger.warning(f"Could not determine strand code for section {i+1}")
                    continue

                sections.append({
                    'title': current_subtitle,
                    'code': strand_code,
                    'attentes': '\n'.join(attentes_lines),
                    'contenus': '\n'.join(contenus_lines)
                })

            return sections

        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            raise

    def _parse_expectations(self, attentes_text: str, contenus_text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Parse overall and specific expectations from text"""
        # Parse overall expectations
        overall_exp = re.findall(r'([A-D]\d+)\s*\.\s*([^\n]+)', attentes_text)

        # Parse specific expectations, handling multiline descriptions
        specific_exp = []
        matches = re.finditer(r'([A-D]\d+\.\d+)\s*([^\n]+(?:\n[^\n]+)*)', contenus_text)
        for match in matches:
            code = match.group(1)
            desc = ' '.join(line.strip() for line in match.group(2).split('\n'))
            specific_exp.append((code, desc))

        return overall_exp, specific_exp

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clean and validate content
            content = self.clean_text(content)
            if not self._validate_content_structure(content):
                raise ValueError("Invalid curriculum structure")

            # Extract sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No valid sections found")

            self.logger.info(f"Found {len(sections)} valid sections to import")

            # Start database transaction
            with db.session.begin_nested():
                # Create course
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11'
                )
                db.session.add(course)
                db.session.flush()

                # Process each section
                for section_data in sections:
                    strand = Strand(
                        course_id=course.id,
                        code=section_data['code'],
                        title_fr=section_data['title'],
                        title_en=''  # Will be added later
                    )
                    db.session.add(strand)
                    db.session.flush()

                    # Parse expectations
                    overall_exp, specific_exp = self._parse_expectations(
                        section_data['attentes'],
                        section_data['contenus']
                    )

                    # Create overall expectations
                    for code, desc in overall_exp:
                        overall = OverallExpectation(
                            strand_id=strand.id,
                            code=code,
                            description_fr=desc.strip(),
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.flush()

                        # Create specific expectations
                        base_code = code + "."
                        related_specifics = [
                            (c, d) for c, d in specific_exp 
                            if c.startswith(base_code)
                        ]

                        for spec_code, spec_desc in related_specifics:
                            specific = SpecificExpectation(
                                overall_expectation_id=overall.id,
                                code=spec_code,
                                description_fr=spec_desc.strip(),
                                description_en=''
                            )
                            db.session.add(specific)

                db.session.commit()
                self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            db.session.rollback()
            raise

    def clear_existing_data(self):
        """Clear existing curriculum data"""
        try:
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
            self.logger.info("Cleared existing ICS3U data")
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}")
            db.session.rollback()
            raise