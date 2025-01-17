"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from app import db

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def clean_text(self, text: str) -> str:
        """Clean up text by removing OCR artifacts and fixing French text"""
        if not text:
            return ""

        # First remove page headers/footers and numbers
        text = re.sub(r'Introduction au génie informatique\s*\n', '', text)
        text = re.sub(r'E CURRICULUM DE L\'ONTARIO.*?12 e', '', text, flags=re.DOTALL)
        text = re.sub(r'\d{2,3}\s*\n', '', text)  # Remove page numbers

        # Fix common OCR patterns for French words
        replacements = {
            'EMEnt': 'ement',
            'AtiquE': 'atique',
            'AvAil': 'avail',
            'informAtiquE': 'informatique',
            'tE ': 'té ',
            'Em ': 'em ',
            'dE ': 'de ',
            'quE ': 'que ',
            'Atiqu': 'atique',
            ' e ': 'e ',
            ' E ': 'E ',
            'e e': 'e',
            'E E': 'E',
            '( p. ex.,': '(p. ex.,',
            'annéee': 'année',
            'année e': 'année',
            ' ANNÉE': 'ANNÉE',
            'é e': 'ée',
            'émE': 'ème',
            'génie e': 'génie',
            'au génie e': 'au génie',
            ' ann e ': ' année '
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Carefully join split words while preserving intentional spaces
        text = re.sub(r'(?<=[a-zà-ÿ])\s+(?=[a-zà-ÿ])', '', text)  # Join lowercase splits
        text = re.sub(r'(?<=[A-ZÀ-Ÿ])\s+(?=[a-zà-ÿ])', '', text)  # Join camelCase splits
        text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)  # Join split numbers

        # Fix French punctuation spacing
        text = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([()])\s*', r'\1', text)

        # Normalize multiple spaces and clean up
        text = re.sub(r'\s+', ' ', text).strip()

        # Fix common spacing issues in course title/headers
        text = re.sub(r'Introduction au génie', 'Introduction au génie ', text)
        text = re.sub(r'informatique(\d)', r'informatique \1', text)
        text = re.sub(r'(\d)année', r'\1 année', text)

        return text

    def extract_course_info(self, content: str) -> Dict[str, str]:
        """Extract course information including title, description and prerequisite"""
        # Match the header section more precisely
        header_pattern = r'Introduction au génie\s+.*?(?=Ce cours)'
        desc_pattern = r'Ce cours.*?(?=Préalable\s*:)'
        prereq_pattern = r'Préalable\s*:\s*(.*?)(?=\n\n|\n[A-Z]\.|\Z)'

        header_match = re.search(header_pattern, content, re.DOTALL)
        desc_match = re.search(desc_pattern, content, re.DOTALL)
        prereq_match = re.search(prereq_pattern, content, re.DOTALL)

        course_info = {
            "title_fr": self.clean_text(header_match.group() if header_match else ""),
            "description_fr": self.clean_text(desc_match.group() if desc_match else ""),
            "prerequisite_fr": self.clean_text(prereq_match.group(1) if prereq_match else "Aucun")
        }

        self.logger.info(f"Extracted course title: {course_info['title_fr']}")
        return course_info

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections with their content"""
        self.logger.debug("Extracting strand sections")

        # Clean up the content first
        content = re.sub(r'Introduction au génie informatique\s*\n', '', content)
        content = re.sub(r'E CURRICULUM DE L\'ONTARIO.*?12 e', '', content, flags=re.DOTALL)
        content = re.sub(r'\d{2,3}\s*\n', '', content)

        sections = []
        seen_codes = set()

        # Match sections more precisely
        section_pattern = r'([A-D])\.\s*(.*?)\s*(?=ATTENTES).*?ATTENTES.*?(?:À la fin du cours[^:]*:)?(.*?)(?=(?:[A-D]\.\s|$))'
        matches = list(re.finditer(section_pattern, content, re.DOTALL))

        for match in matches:
            code = match.group(1)
            if code in seen_codes:
                continue

            title = self.clean_text(match.group(2))
            section_content = match.group(3)

            if title and section_content:
                self.logger.info(f"Found strand {code}: {title}")
                sections.append((code, title, section_content))
                seen_codes.add(code)

        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content"""
        self.logger.debug(f"Parsing overall expectations for strand {strand_code}")

        # Extract overall expectations section
        attentes_pattern = r'(?:À la fin du cours[^:]*:)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        attentes_match = re.search(attentes_pattern, content, re.DOTALL)

        if not attentes_match:
            self.logger.warning(f"No overall expectations found for strand {strand_code}")
            return []

        expectations = []
        section_text = attentes_match.group(1)

        # Match expectations with their codes
        exp_pattern = rf'{strand_code}(\d+)\.\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.|$)'
        for match in re.finditer(exp_pattern, section_text, re.DOTALL):
            number = match.group(1)
            description = self.clean_text(match.group(2))

            if description:
                code = f"{strand_code}{number}"
                self.logger.info(f"Found overall expectation {code}")
                expectations.append({
                    'code': code,
                    'description_fr': description,
                    'description_en': f"[NEEDS TRANSLATION] {description}"
                })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations grouped by overall expectations"""
        self.logger.debug(f"Parsing specific expectations for strand {strand_code}")

        # Extract CONTENUS D'APPRENTISSAGE section
        contenus_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?Pour satisfaire aux attentes.*?:(.*?)(?=(?:[A-D]\.\s|$))'
        contenus_match = re.search(contenus_pattern, content, re.DOTALL)

        if not contenus_match:
            self.logger.warning(f"No specific expectations found for strand {strand_code}")
            return {}

        specifics_by_overall = {}
        section_text = contenus_match.group(1)

        # Match specific expectations using lookahead for better boundary detection
        spec_pattern = rf'{strand_code}(\d+)\.(\d+)\s*([^{strand_code}0-9]+?)(?={strand_code}\d+\.\d+|$)'
        for match in re.finditer(spec_pattern, section_text, re.DOTALL):
            overall_num = match.group(1)
            specific_num = match.group(2)
            description = self.clean_text(match.group(3))

            if description:
                overall_code = f"{strand_code}{overall_num}"
                specific_code = f"{overall_code}.{specific_num}"

                if overall_code not in specifics_by_overall:
                    specifics_by_overall[overall_code] = []

                self.logger.info(f"Found specific expectation {specific_code}")
                specifics_by_overall[overall_code].append({
                    'code': specific_code,
                    'description_fr': description,
                    'description_en': f"[NEEDS TRANSLATION] {description}"
                })

        return specifics_by_overall

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import")

        try:
            # Extract course information
            course_info = self.extract_course_info(content)
            self.logger.info("Extracted course information")

            # Create course
            course = Course(
                code='ICS3U',
                title_fr=course_info["title_fr"],
                title_en="Introduction to Computer Science, Grade 11",
                description_fr=course_info["description_fr"],
                description_en="[NEEDS TRANSLATION]",
                prerequisite_fr=course_info["prerequisite_fr"],
                prerequisite_en="None"
            )
            db.session.add(course)
            db.session.flush()

            # Process each strand
            for code, title, content in self.extract_strand_sections(content):
                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_fr=title,
                    title_en=f"[NEEDS TRANSLATION] {title}"
                )
                db.session.add(strand)
                db.session.flush()

                # Get specific expectations first
                specifics_by_overall = self.parse_specific_expectations(content, code)

                # Process overall expectations and their specifics
                for overall_data in self.parse_overall_expectations(content, code):
                    overall = OverallExpectation(
                        strand_id=strand.id,
                        **overall_data
                    )
                    db.session.add(overall)
                    db.session.flush()

                    # Add associated specific expectations
                    for spec_data in specifics_by_overall.get(overall_data['code'], []):
                        specific = SpecificExpectation(
                            overall_expectation_id=overall.id,
                            **spec_data
                        )
                        db.session.add(specific)

            db.session.commit()
            self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error importing curriculum: {str(e)}")
            raise

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate placeholder English descriptions"""
        return f"[NEEDS TRANSLATION] {desc_fr}"

    def clear_existing_data(self):
        """Clear existing curriculum data"""
        self.logger.info("Clearing existing ICS3U curriculum data")

        try:
            course = Course.query.filter_by(code='ICS3U').first()
            if course:
                # Delete in correct order to respect foreign key constraints
                SpecificExpectation.query.join(OverallExpectation).join(Strand).filter(Strand.course_id == course.id).delete(synchronize_session=False)
                OverallExpectation.query.join(Strand).filter(Strand.course_id == course.id).delete(synchronize_session=False)
                Strand.query.filter_by(course_id=course.id).delete(synchronize_session=False)
                Course.query.filter_by(code='ICS3U').delete()

                db.session.commit()
                self.logger.info("Successfully cleared existing data")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise