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

        # Define more flexible patterns based on actual file structure
        self._section_start_pattern = r'(?:^|\n)\s*([A-D])\s*\.\s*([^\n]+?)(?=\s*(?:ATTENTES|$))'
        self._attentes_pattern = r'(?:^|\n)\s*ATTENTES\s*(?:À la fin[^:]*:|$)\s*(.*?)(?=\s*(?:CONTENUS|[A-D]\s*\.|$))'
        self._contenus_pattern = r'(?:^|\n)\s*CONTENUS.*?(?:Pour satisfaire[^:]*:)\s*(.*?)(?=\s*(?:[A-D]\s*\.|$))'
        self._overall_exp_pattern = r'(?m)^\s*{}\s*(\d+)\s*\.\s*([^\n]+(?:\n(?!\s*{}\s*\d+\.|CONTENUS|\s*[A-D]\.).+)*)'
        self._specific_exp_pattern = r'(?m)^\s*{}\s*(\d+)\s*\.\s*(\d+)\s*([^\n]+(?:\n(?!\s*{}\s*\d+\.|ATTENTES|\s*[A-D]\.).+)*)'

    def clean_text(self, text: str) -> str:
        """Clean and normalize French text"""
        if not text:
            return ""

        try:
            # Normalize line endings
            text = text.replace('\r\n', '\n').replace('\r', '\n')

            # Remove extra whitespace while preserving meaningful structure
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text)

            # Remove page numbers and headers
            text = re.sub(r'(?m)^\s*\d+\s*$', '', text)
            text = re.sub(r'(?i)curriculum\s+de\s+l\'ontario.*?\n', '\n', text)
            text = re.sub(r'(?i)cours\s+préuniversitaire.*?\n', '\n', text)

            # Handle French characters and special symbols
            replacements = [
                ('"', '"'), ('"', '"'), 
                ("'", "'"), ("'", "'"),
                ('e´', 'é'), ('e`', 'è'), 
                ('a`', 'à'), ('e^', 'ê'),
                ('–', '-'), ('—', '-'),
                ('...', '…'), ('..', '.'),
                ('\u2019', "'"), ('\u2018', "'"),
                ('\u201C', '"'), ('\u201D', '"'),
                ('\u00A0', ' ')  # non-breaking space
            ]
            for old, new in replacements:
                text = text.replace(old, new)

            return text.strip()
        except Exception as e:
            self.logger.error(f"Error in clean_text: {str(e)}")
            raise

    def _extract_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract main curriculum sections"""
        sections = []
        try:
            # Clean initial content
            content = self.clean_text(content)
            self.logger.debug(f"Content length after cleaning: {len(content)} characters")

            # Find all section matches
            matches = list(re.finditer(self._section_start_pattern, content, re.MULTILINE | re.DOTALL))

            for i, match in enumerate(matches):
                code = match.group(1)
                title = self.clean_text(match.group(2))

                # Get content until next section or end
                start_pos = match.end()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                section_content = content[start_pos:end_pos].strip()

                if title and section_content:
                    sections.append((code, title, section_content))
                    self.logger.debug(f"Found section {code}: {title}")

            if not sections:
                self.logger.error("No valid sections found after parsing")
                self.logger.debug(f"Content preview: {content[:500]}")
                raise ValueError("No curriculum sections found in content")

            return sections
        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            raise

    def _parse_section_content(self, section_content: str) -> Dict:
        """Parse section content into ATTENTES and CONTENUS"""
        try:
            # Extract ATTENTES and CONTENUS with more flexible patterns
            attentes_match = re.search(self._attentes_pattern, section_content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            contenus_match = re.search(self._contenus_pattern, section_content, re.MULTILINE | re.DOTALL | re.IGNORECASE)

            if not attentes_match or not contenus_match:
                self.logger.error("Failed to find both ATTENTES and CONTENUS sections")
                self.logger.debug(f"Section content preview: {section_content[:200]}")
                raise ValueError("Missing required sections in content")

            return {
                "attentes": self.clean_text(attentes_match.group(1)),
                "contenus": self.clean_text(contenus_match.group(1))
            }
        except Exception as e:
            self.logger.error(f"Error parsing section content: {str(e)}")
            raise

    def _extract_expectations(self, section_code: str, content: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Extract expectations with improved pattern matching"""
        overall_expectations = []
        specific_expectations = []

        try:
            # Extract overall expectations
            if content["attentes"]:
                pattern = self._overall_exp_pattern.format(section_code, section_code)
                matches = re.finditer(pattern, content["attentes"], re.MULTILINE)
                for match in matches:
                    exp = {
                        "number": match.group(1),
                        "description": self.clean_text(match.group(2))
                    }
                    overall_expectations.append(exp)
                    self.logger.debug(f"Found overall {section_code}{exp['number']}")

            # Extract specific expectations
            if content["contenus"]:
                pattern = self._specific_exp_pattern.format(section_code, section_code)
                matches = re.finditer(pattern, content["contenus"], re.MULTILINE)
                for match in matches:
                    exp = {
                        "overall_num": match.group(1),
                        "specific_num": match.group(2),
                        "description": self.clean_text(match.group(3))
                    }
                    specific_expectations.append(exp)
                    self.logger.debug(f"Found specific {section_code}{exp['overall_num']}.{exp['specific_num']}")

            return overall_expectations, specific_expectations
        except Exception as e:
            self.logger.error(f"Error extracting expectations: {str(e)}")
            raise

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import process...")

        try:
            # Clear existing data to avoid duplicates
            self.clear_existing_data()

            # Extract and validate sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No curriculum sections found in content")

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
            db.session.flush()

            # Process each section
            for code, title, section_content in sections:
                self.logger.info(f"Processing section {code}: {title}")

                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_fr=title,
                    title_en=''  # English title will be added later
                )
                db.session.add(strand)
                db.session.flush()

                # Parse section content
                parsed = self._parse_section_content(section_content)
                overall_exps, specific_exps = self._extract_expectations(code, parsed)

                # Add overall expectations
                for overall in overall_exps:
                    overall_exp = OverallExpectation(
                        strand_id=strand.id,
                        code=f"{code}{overall['number']}",
                        description_fr=overall['description'],
                        description_en=''  # English description will be added later
                    )
                    db.session.add(overall_exp)
                    db.session.flush()

                    # Add specific expectations for this overall expectation
                    for specific in specific_exps:
                        if specific['overall_num'] == overall['number']:
                            spec_exp = SpecificExpectation(
                                overall_expectation_id=overall_exp.id,
                                code=f"{code}{specific['overall_num']}.{specific['specific_num']}",
                                description_fr=specific['description'],
                                description_en=''  # English description will be added later
                            )
                            db.session.add(spec_exp)

                # Commit after each section
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