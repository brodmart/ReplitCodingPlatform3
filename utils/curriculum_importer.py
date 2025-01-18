"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from app import db
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Define regex patterns as class attributes for better maintainability
        self._section_pattern = r'([A-D])\s*\.\s*([^.]+?)(?=\s*[A-D]\s*\.|\s*$)'
        self._attentes_pattern = r'(?:^|\s)ATTENTES\s*(?:À la fin du cours[^:]*:)?\s*(.*?)(?=\s*CONTENUS|$)'
        self._contenus_pattern = r'(?:^|\s)CONTENUS\s+D(?:\'|')APPRENTISSAGE\s*(?:Pour satisfaire[^:]*:)?\s*(.*?)(?=(?:[A-D]\s*\.(?!\d))|$)'
        self._overall_exp_pattern = r'{}\s*(\d+)\s*\.\s*(.*?)(?={}|\s*$)'
        self._specific_exp_pattern = r'{}\s*(\d+)\s*\.\s*(\d+)\s*(.*?)(?={}|$)'

    def clean_text(self, text: str) -> str:
        """Clean up text by removing artifacts and normalizing French characters"""
        if not text:
            return ""

        # French character normalization map
        char_map = {
            'e\x60': 'è', 'e\^': 'ê', 'a\`': 'à', 'e\´': 'é',
            'E\x60': 'È', 'E\^': 'Ê', 'A\`': 'À', 'E\´': 'É',
            'c\¸': 'ç', 'C\¸': 'Ç',
            ''': "'", '"': '"', '"': '"',  # Normalize quotes
            'oe': 'œ', 'ae': 'æ'  # Additional French ligatures
        }

        # Apply character normalization
        for old, new in char_map.items():
            text = text.replace(old, new)

        # Remove headers and page numbers
        text = re.sub(r'(?:ICS[234]U|Introduction au génie informatique).*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d{1,3}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*Cours préuniversitaire.*?$', '', text, flags=re.MULTILINE)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        self.logger.debug(f"Cleaned text length: {len(text)}")
        return text

    def extract_course_description(self, content: str) -> str:
        """Extract course description using simplified pattern"""
        pattern = r'Ce cours\s+([^.]*(?:[^P]\.)+)(?=\s*Préalable\s*:|$)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            desc = self.clean_text(match.group(1))
            self.logger.info(f"Extracted course description ({len(desc)} chars)")
            return desc

        self.logger.warning("Failed to extract course description")
        return ""

    def extract_prerequisite(self, content: str) -> str:
        """Extract prerequisite with simplified pattern"""
        pattern = r'Préalable\s*:\s*([^A-D][^\n]*?)(?=\s*[A-D]\s*\.|\s*$)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            prereq = self.clean_text(match.group(1))
            self.logger.info(f"Extracted prerequisite: {prereq}")
            return prereq

        self.logger.warning("No prerequisite found, using default")
        return "Aucun"

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections using simplified patterns"""
        self.logger.info("Starting strand extraction...")
        sections = []

        # Find all strand sections
        matches = re.finditer(self._section_pattern, content, re.DOTALL)
        sections_list = list(matches)

        if not sections_list:
            self.logger.warning("No strand sections found in content")
            return sections

        for i, match in enumerate(sections_list):
            code = match.group(1)
            title = self.clean_text(match.group(2))
            start_pos = match.start()

            # Calculate end position
            if i < len(sections_list) - 1:
                end_pos = sections_list[i + 1].start()
            else:
                end_pos = len(content)

            section_content = content[start_pos:end_pos]

            # Verify section components
            has_attentes = bool(re.search(r'ATTENTES', section_content, re.IGNORECASE))
            has_contenus = bool(re.search(r'CONTENUS', section_content, re.IGNORECASE))

            if has_attentes and has_contenus:
                self.logger.info(f"Found valid strand {code}: {title}")
                sections.append((code, title, section_content))
            else:
                self.logger.warning(f"Strand {code} missing required sections")

        self.logger.info(f"Extracted {len(sections)} valid strands")
        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations with simplified patterns"""
        expectations = []

        # Extract ATTENTES section
        attentes_match = re.search(self._attentes_pattern, content, re.DOTALL | re.IGNORECASE)
        if not attentes_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return expectations

        expectations_text = self.clean_text(attentes_match.group(1))
        pattern = self._overall_exp_pattern.format(
            re.escape(strand_code),
            re.escape(strand_code)
        )

        matches = re.finditer(pattern, expectations_text, re.DOTALL)
        for match in matches:
            number = match.group(1)
            description = self.clean_text(match.group(2))

            if description:
                code = f"{strand_code}{number}"
                expectations.append({
                    'code': code,
                    'description_fr': description,
                    'description_en': ''
                })
                self.logger.info(f"Found overall expectation {code}")

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations with simplified patterns"""
        specifics_by_overall = {}

        # Extract CONTENUS section
        contenus_match = re.search(self._contenus_pattern, content, re.DOTALL | re.IGNORECASE)
        if not contenus_match:
            self.logger.warning(f"No CONTENUS section found for strand {strand_code}")
            return specifics_by_overall

        content_text = self.clean_text(contenus_match.group(1))
        pattern = self._specific_exp_pattern.format(
            re.escape(strand_code),
            re.escape(strand_code)
        )

        matches = re.finditer(pattern, content_text, re.DOTALL)
        for match in matches:
            overall_num = match.group(1)
            specific_num = match.group(2)
            description = self.clean_text(match.group(3))

            if description:
                overall_code = f"{strand_code}{overall_num}"
                specific_code = f"{strand_code}{overall_num}.{specific_num}"

                if overall_code not in specifics_by_overall:
                    specifics_by_overall[overall_code] = []

                specifics_by_overall[overall_code].append({
                    'code': specific_code,
                    'description_fr': description,
                    'description_en': ''
                })
                self.logger.info(f"Found specific expectation {specific_code}")

        return specifics_by_overall

    def clear_existing_data(self):
        """Clear existing curriculum data using SQLAlchemy ORM"""
        self.logger.info("Clearing existing ICS3U curriculum data")
        try:
            course = Course.query.options(
                joinedload(Course.strands)
                .joinedload(Strand.overall_expectations)
                .joinedload(OverallExpectation.specific_expectations)
            ).filter_by(code='ICS3U').first()

            if course:
                db.session.delete(course)
                db.session.commit()
                self.logger.info("Successfully cleared existing data")
            else:
                self.logger.info("No existing ICS3U data found to clear")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise

    def import_curriculum(self, content: str):
        """Import curriculum content into database with improved error handling"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clear existing data first
            self.clear_existing_data()

            # Create course
            course = Course(
                code='ICS3U',
                title_fr='Introduction au génie informatique, 11e année cours préuniversitaire',
                title_en='Introduction to Computer Science, Grade 11 University Preparation',
                description_fr=self.extract_course_description(content),
                description_en='',
                prerequisite_fr=self.extract_prerequisite(content),
                prerequisite_en='None'
            )

            db.session.add(course)
            db.session.flush()
            self.logger.info(f"Created course: {course.code}")

            # Process strands
            for strand_code, strand_title, strand_content in self.extract_strand_sections(content):
                strand = Strand(
                    course_id=course.id,
                    code=strand_code,
                    title_fr=strand_title,
                    title_en=''
                )
                db.session.add(strand)
                db.session.flush()

                # Process expectations
                for overall_data in self.parse_overall_expectations(strand_content, strand_code):
                    overall = OverallExpectation(
                        strand_id=strand.id,
                        code=overall_data['code'],
                        description_fr=overall_data['description_fr'],
                        description_en=overall_data['description_en']
                    )
                    db.session.add(overall)
                    db.session.flush()

                    # Process specific expectations
                    specifics = self.parse_specific_expectations(strand_content, strand_code)
                    for specific_data in specifics.get(overall_data['code'], []):
                        specific = SpecificExpectation(
                            overall_expectation_id=overall.id,
                            code=specific_data['code'],
                            description_fr=specific_data['description_fr'],
                            description_en=specific_data['description_en']
                        )
                        db.session.add(specific)

                db.session.commit()
                self.logger.info(f"Processed strand {strand_code}")

            self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during curriculum import: {str(e)}")
            raise