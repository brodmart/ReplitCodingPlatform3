"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from app import db
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Define regex patterns for curriculum structure
        self._section_pattern = (
            r'(?:^|\n)\s*'           # Start of line or after newline
            r'([A-D])\s*\.\s*'       # Section letter with optional whitespace
            r'([^.]+?)'              # Section title (non-greedy)
            r'(?=\s*(?:[A-D]\s*\.|$))'  # Look ahead for next section or end
        )

        self._attentes_pattern = (
            r'ATTENTES\s*'           # Match ATTENTES header
            r'(?:À la fin[^:]*:)?\s*'  # Optional intro text
            r'((?:(?!\s*CONTENUS\s+D).)*)'  # Capture until CONTENUS
        )

        self._contenus_pattern = (
            r'CONTENUS\s+D[\'']?APPRENTISSAGE\s*'  # Match CONTENUS with optional quote
            r'(?:Pour satisfaire[^:]*:)?\s*'       # Optional intro text
            r'((?:(?!\s*[A-D]\s*\.).)*)'          # Capture until next major section
        )

        # Patterns for expectations
        self._overall_exp_pattern = (
            r'{}\s*'           # Section code
            r'(\d+)\s*\.\s*'   # Overall expectation number with dot
            r'([^.]+(?:\.[^.]+)*)'  # Description (allowing multiple sentences)
        )

        self._specific_exp_pattern = (
            r'{}\s*'           # Section code
            r'(\d+)\s*\.\s*'   # Overall number
            r'(\d+)\s*'        # Specific number
            r'([^.]+(?:\.[^.]+)*)'  # Description (allowing multiple sentences)
        )

    def clean_text(self, text: str) -> str:
        """Clean and normalize French text"""
        if not text:
            return ""

        # French character normalization
        char_map = {
            # Accents
            'é': 'é', 'è': 'è', 'ê': 'ê', 'ë': 'ë',
            'à': 'à', 'â': 'â', 'ä': 'ä',
            'ù': 'ù', 'û': 'û', 'ü': 'ü',
            'ô': 'ô', 'ö': 'ö',
            'î': 'î', 'ï': 'ï',
            'ç': 'ç',
            # Quotes and apostrophes
            '’': "'", '‘': "'", '"': '"', '"': '"',
            # Special characters
            '–': '-', '—': '-',
            # Common ligatures
            'œ': 'oe', 'æ': 'ae'
        }

        try:
            # Apply character normalization
            for old, new in char_map.items():
                text = text.replace(old, new)

            # Remove headers and page numbers
            text = re.sub(r'(?:^|\n)\s*ICS[234]U.*?\n', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*\d+\s*$', '', text, flags=re.MULTILINE)

            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            self.logger.debug(f"Cleaned text sample: {text[:100]}...")
            return text

        except Exception as e:
            self.logger.error(f"Error in clean_text: {str(e)}", exc_info=True)
            raise

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections with better error handling"""
        try:
            sections = []
            matches = re.finditer(self._section_pattern, content, re.MULTILINE)

            current_section = None
            current_text = ""

            for match in matches:
                if current_section:
                    sections.append((
                        current_section[0],  # code
                        current_section[1],  # title
                        content[current_section[2]:match.start()]  # content
                    ))
                current_section = (
                    match.group(1),  # code
                    self.clean_text(match.group(2)),  # title
                    match.start()  # start position
                )

            if current_section:
                sections.append((
                    current_section[0],
                    current_section[1],
                    content[current_section[2]:]
                ))

            self.logger.info(f"Found {len(sections)} sections")
            for code, title, _ in sections:
                self.logger.debug(f"Section {code}: {title}")

            return sections

        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}", exc_info=True)
            raise

    def import_curriculum(self, content: str):
        """Import curriculum with enhanced validation"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clear existing data
            self.clear_existing_data()

            content = self.clean_text(content)
            if not content:
                raise ValueError("Empty curriculum content after cleaning")

            self.logger.debug(f"Processing content length: {len(content)}")

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
            self.logger.info(f"Created course: {course.id}")

            # Process sections
            sections = self.extract_strand_sections(content)
            if not sections:
                raise ValueError("No valid sections found")

            for code, title, section_content in sections:
                self.logger.info(f"Processing section {code}: {title}")

                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_fr=title,
                    title_en=''
                )
                db.session.add(strand)
                db.session.commit()

                # Extract expectations
                attentes_match = re.search(
                    self._attentes_pattern,
                    section_content,
                    re.MULTILINE | re.IGNORECASE
                )

                if attentes_match:
                    attentes_text = attentes_match.group(1)
                    self.logger.debug(f"Found ATTENTES for {code}")

                    # Process overall expectations
                    overall_pattern = self._overall_exp_pattern.format(re.escape(code))
                    for match in re.finditer(overall_pattern, attentes_text, re.MULTILINE):
                        number = match.group(1)
                        description = self.clean_text(match.group(2))

                        overall = OverallExpectation(
                            strand_id=strand.id,
                            code=f"{code}{number}",
                            description_fr=description,
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.commit()
                        self.logger.info(f"Added overall expectation: {overall.code}")

                # Extract specific expectations
                contenus_match = re.search(
                    self._contenus_pattern,
                    section_content,
                    re.MULTILINE | re.IGNORECASE | re.DOTALL
                )

                if contenus_match:
                    contenus_text = contenus_match.group(1)
                    self.logger.debug(f"Found CONTENUS for {code}")

                    # Process specific expectations
                    specific_pattern = self._specific_exp_pattern.format(re.escape(code))
                    for match in re.finditer(specific_pattern, contenus_text, re.MULTILINE):
                        overall_num = match.group(1)
                        specific_num = match.group(2)
                        description = self.clean_text(match.group(3))

                        overall = OverallExpectation.query.filter_by(
                            strand_id=strand.id,
                            code=f"{code}{overall_num}"
                        ).first()

                        if overall:
                            specific = SpecificExpectation(
                                overall_expectation_id=overall.id,
                                code=f"{code}{overall_num}.{specific_num}",
                                description_fr=description,
                                description_en=''
                            )
                            db.session.add(specific)
                            db.session.commit()
                            self.logger.info(f"Added specific expectation: {specific.code}")

            self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            self.logger.error(f"Error during import: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    def clear_existing_data(self):
        """Clear existing curriculum data"""
        try:
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
            self.logger.info("Cleared existing ICS3U data")
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}", exc_info=True)
            db.session.rollback()
            raise