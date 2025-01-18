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

        # More flexible pattern for finding sections
        self._section_pattern = r'(?:^|\n)\s*([A-D])\s*\.\s*([^\n]+?)(?=\s*(?:ATTENTES|$))'

        # Simplified patterns for expectations sections
        self._attentes_pattern = r'ATTENTES.*?(?:pouvoir|:)\s*(.*?)(?=\s*CONTENUS)'
        self._contenus_pattern = r'CONTENUS.*?(?:pouvoir|:)\s*(.*?)(?=\s*(?:[A-D]\.|$))'

        # Patterns for individual expectations
        self._overall_exp_pattern = r'{}\s*(\d+)\.\s*([^.]+(?:\.[^.]+)*)'
        self._specific_exp_pattern = r'{}\s*(\d+)\.(\d+)\s*([^.]+(?:\.[^.]+)*)'

    def clean_text(self, text: str) -> str:
        """Clean and normalize French text"""
        if not text:
            return ""

        try:
            # Remove headers and formatting
            text = re.sub(r'(?m)^\s*\d+\s*$', '', text)
            text = re.sub(r'(?i)curriculum\s+de\s+l\'ontario.*?\n', '\n', text)
            text = re.sub(r'(?i)cours\s+préuniversitaire.*?\n', '\n', text)

            # Handle French characters
            replacements = [
                ('"', '"'), ('"', '"'),
                ("'", "'"), ("'", "'"),
                ('e´', 'é'), ('e`', 'è'),
                ('a`', 'à'), ('e^', 'ê'),
                ('–', '-'), ('—', '-'),
                ('...', '…')
            ]
            for old, new in replacements:
                text = text.replace(old, new)

            # Clean whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            return text
        except Exception as e:
            self.logger.error(f"Error in clean_text: {str(e)}")
            raise

    def _extract_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract main curriculum sections"""
        sections = []
        try:
            # Clean content for better parsing
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            content = re.sub(r'\n{3,}', '\n\n', content)

            # Find sections
            matches = list(re.finditer(self._section_pattern, content, re.MULTILINE | re.DOTALL))
            self.logger.debug(f"Found {len(matches)} potential sections")

            for i, match in enumerate(matches):
                code = match.group(1)
                title = self.clean_text(match.group(2))

                # Get content until next section
                start = match.end()
                end = matches[i + 1].start() if i < len(matches) - 1 else len(content)
                section_content = content[start:end].strip()

                if title and section_content:
                    sections.append((code, title, section_content))
                    self.logger.debug(f"\nProcessed section {code}:")
                    self.logger.debug(f"Title: {title}")
                    self.logger.debug(f"Content preview: {section_content[:200]}")

            return sections
        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            self.logger.debug(f"Content preview:\n{content[:1000]}")
            raise

    def _parse_section_content(self, section_content: str) -> Dict:
        """Parse section content into ATTENTES and CONTENUS"""
        try:
            # Extract subsections
            attentes_match = re.search(self._attentes_pattern, section_content, re.MULTILINE | re.DOTALL)
            contenus_match = re.search(self._contenus_pattern, section_content, re.MULTILINE | re.DOTALL)

            self.logger.debug("\nMatched sections:")
            self.logger.debug(f"ATTENTES found: {bool(attentes_match)}")
            self.logger.debug(f"CONTENUS found: {bool(contenus_match)}")

            result = {
                "attentes": self.clean_text(attentes_match.group(1) if attentes_match else ""),
                "contenus": self.clean_text(contenus_match.group(1) if contenus_match else "")
            }

            self.logger.debug("\nProcessed content:")
            self.logger.debug(f"ATTENTES: {result['attentes'][:200]}")
            self.logger.debug(f"CONTENUS: {result['contenus'][:200]}")

            return result
        except Exception as e:
            self.logger.error(f"Error parsing section: {str(e)}")
            raise

    def _extract_expectations(self, section_code: str, content: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Extract expectations from content"""
        overall_expectations = []
        specific_expectations = []

        try:
            # Process overall expectations
            if content["attentes"]:
                pattern = self._overall_exp_pattern.format(section_code)
                matches = list(re.finditer(pattern, content["attentes"], re.MULTILINE))

                for match in matches:
                    exp = {
                        "number": match.group(1),
                        "description": self.clean_text(match.group(2))
                    }
                    overall_expectations.append(exp)
                    self.logger.debug(f"Found overall {section_code}{exp['number']}")

            # Process specific expectations
            if content["contenus"]:
                pattern = self._specific_exp_pattern.format(section_code)
                matches = list(re.finditer(pattern, content["contenus"], re.MULTILINE))

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
            # Extract sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No curriculum sections found in content")

            # Clear existing data
            self.clear_existing_data()

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

            # Process sections
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

                # Parse expectations
                parsed = self._parse_section_content(section_content)
                overall_exps, specific_exps = self._extract_expectations(code, parsed)

                # Add overall expectations
                for overall in overall_exps:
                    overall_exp = OverallExpectation(
                        strand_id=strand.id,
                        code=f"{code}{overall['number']}",
                        description_fr=overall['description'],
                        description_en=''
                    )
                    db.session.add(overall_exp)
                    db.session.commit()

                    # Add specific expectations
                    for specific in specific_exps:
                        if specific['overall_num'] == overall['number']:
                            spec_exp = SpecificExpectation(
                                overall_expectation_id=overall_exp.id,
                                code=f"{code}{specific['overall_num']}.{specific['specific_num']}",
                                description_fr=specific['description'],
                                description_en=''
                            )
                            db.session.add(spec_exp)
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