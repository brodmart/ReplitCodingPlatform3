"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from app import db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Define regex patterns for curriculum structure
        self._section_pattern = r'(?:^|\n)\s*([A-D])\s*\.\s*([^.\n]+?)(?:\.|$)'

        self._attentes_pattern = (
            r'(?:^|\n)\s*'           # Start of line or newline
            r'ATTENTES\s*'           # ATTENTES header
            r'(?:À la fin[^:]*:)?\s*' # Optional intro text
            r'((?:.|\n)*?)'          # Capture everything until CONTENUS
            r'(?=\s*CONTENUS\s*D)'   # Look ahead for CONTENUS D'APPRENTISSAGE
        )

        self._contenus_pattern = (
            r'(?:^|\n)\s*'           # Start of line or newline
            r'CONTENUS\s*D\'APPRENTISSAGE\s*'  # CONTENUS D'APPRENTISSAGE header
            r'(?:Pour satisfaire[^:]*:)?\s*'   # Optional intro text
            r'((?:.|\n)*?)'          # Capture everything until next section
            r'(?=\s*(?:[A-D](?:\d+)?\.|\Z))'  # Look ahead for next section or end
        )

        # Patterns for expectations
        self._overall_exp_pattern = (
            r'{}\s*'           # Section code (e.g., A, B)
            r'(\d+)\s*\.\s*'   # Overall expectation number with dot
            r'([^.\n]+(?:\.[^.]+)*)'  # Description (allowing multiple sentences)
        )

        self._specific_exp_pattern = (
            r'{}\s*'           # Section code
            r'(\d+)\s*\.\s*'   # Overall number
            r'(\d+)\s*'        # Specific number
            r'([^.\n]+(?:\.[^.]+)*)'  # Description (allowing multiple sentences)
        )

    def clean_text(self, text: str) -> str:
        """Clean and normalize French text"""
        if not text:
            return ""

        try:
            # Remove headers and page numbers first
            text = re.sub(r'(?:^|\n)\s*(?:Curriculum\s+de\s+l\'Ontario|\d+e\s+année|ICS[234]U).*?\n', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*\d+\s*$', '', text, flags=re.MULTILINE)

            # Handle French characters and special symbols
            replacements = [
                ('"', '"'),  # Smart quotes
                ('"', '"'),
                ("'", "'"),  # Smart apostrophes
                ("'", "'"),
                ('e´', 'é'),  # Common OCR errors with accents
                ('e`', 'è'),
                ('a`', 'à'),
                ('e^', 'ê'),
                ('–', '-'),  # Dashes and hyphens
                ('—', '-'),
                ('...', '…'),  # Ellipsis
            ]

            for old, new in replacements:
                text = text.replace(old, new)

            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            return text

        except Exception as e:
            self.logger.error(f"Error in clean_text: {str(e)}")
            raise

    def _extract_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract main curriculum sections"""
        sections = []
        # Split content by main section headers (A., B., C., D.)
        matches = list(re.finditer(self._section_pattern, content, re.MULTILINE))

        for i, match in enumerate(matches):
            code = match.group(1)
            title = self.clean_text(match.group(2))

            # Get content until next section or end
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()

            if section_content:
                sections.append((code, title, section_content))
                self.logger.debug(f"Found section {code}: {title}")
                self.logger.debug(f"Content preview: {section_content[:200]}...")

        return sections

    def _parse_section_content(self, section_content: str) -> Dict:
        """Parse section content into attentes and contenus"""
        try:
            # Find ATTENTES section
            attentes_match = re.search(self._attentes_pattern, section_content, re.MULTILINE | re.DOTALL)
            contenus_match = re.search(self._contenus_pattern, section_content, re.MULTILINE | re.DOTALL)

            result = {
                "attentes": attentes_match.group(1).strip() if attentes_match else "",
                "contenus": contenus_match.group(1).strip() if contenus_match else ""
            }

            if not result["attentes"] or not result["contenus"]:
                self.logger.warning(f"Missing content - ATTENTES: {bool(result['attentes'])}, CONTENUS: {bool(result['contenus'])}")
                self.logger.debug("Section content preview:")
                self.logger.debug("-" * 50)
                self.logger.debug(section_content[:500])
                self.logger.debug("-" * 50)

            return result

        except Exception as e:
            self.logger.error(f"Error parsing section content: {str(e)}")
            raise

    def _extract_expectations(self, section_code: str, content: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Extract expectations from section content"""
        overall_expectations = []
        specific_expectations = []

        try:
            # Extract overall expectations
            if content["attentes"]:
                pattern = self._overall_exp_pattern.format(section_code)
                for match in re.finditer(pattern, content["attentes"], re.MULTILINE):
                    overall_expectations.append({
                        "number": match.group(1),
                        "description": self.clean_text(match.group(2))
                    })

            # Extract specific expectations
            if content["contenus"]:
                pattern = self._specific_exp_pattern.format(section_code)
                for match in re.finditer(pattern, content["contenus"], re.MULTILINE):
                    specific_expectations.append({
                        "overall_num": match.group(1),
                        "specific_num": match.group(2),
                        "description": self.clean_text(match.group(3))
                    })

            return overall_expectations, specific_expectations

        except Exception as e:
            self.logger.error(f"Error extracting expectations: {str(e)}")
            raise

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clear existing data
            self.clear_existing_data()

            # Clean and validate content
            content = self.clean_text(content)
            if not content:
                raise ValueError("Empty curriculum content after cleaning")

            # Create course
            course = Course(
                code='ICS3U',
                title_fr='Introduction au génie informatique, 11e année',
                title_en='Introduction to Computer Science, Grade 11',
                description_fr='',
                description_en='',
                prerequisite_fr='Aucun',
                prerequisite_en='None'
            )
            db.session.add(course)
            db.session.commit()

            # Extract and process sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No curriculum sections found")

            # Process each section
            for code, title, section_content in sections:
                self.logger.info(f"Processing section {code}: {title}")

                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_fr=title,
                    title_en=''
                )
                db.session.add(strand)
                db.session.commit()

                # Parse section content
                parsed_content = self._parse_section_content(section_content)
                overall_exps, specific_exps = self._extract_expectations(code, parsed_content)

                # Add expectations
                for overall in overall_exps:
                    exp = OverallExpectation(
                        strand_id=strand.id,
                        code=f"{code}{overall['number']}",
                        description_fr=overall['description'],
                        description_en=''
                    )
                    db.session.add(exp)
                    db.session.commit()

                    # Add related specific expectations
                    matching_specifics = [s for s in specific_exps if s['overall_num'] == overall['number']]
                    for specific in matching_specifics:
                        spec = SpecificExpectation(
                            overall_expectation_id=exp.id,
                            code=f"{code}{specific['overall_num']}.{specific['specific_num']}",
                            description_fr=specific['description'],
                            description_en=''
                        )
                        db.session.add(spec)
                        db.session.commit()

            self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            self.logger.error(f"Error during import: {str(e)}")
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