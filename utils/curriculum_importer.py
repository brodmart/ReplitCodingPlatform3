"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from app import db, app

class CurriculumImporter:
    def __init__(self):
        self.current_course = None
        self.current_strand = None
        self.current_overall = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def clean_text(self, text: str) -> str:
        """Clean up text by removing extra spaces and newlines while preserving French accents"""
        if not text:
            return ""

        # Fix common OCR issues with French text
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = text.replace(' e ', 'e')  # Fix common OCR errors
        text = text.replace(' E ', 'E')
        text = text.replace('e e', 'e')  # Fix double e's
        text = text.replace('E E', 'E')

        # Fix French specific issues
        text = text.replace('tE ', 'té ')
        text = text.replace('Em ', 'EM ')
        text = text.replace('dE ', 'de ')
        text = text.replace('( p. ex.,', '(p. ex.,')

        # Fix split words
        text = re.sub(r'([A-Z])\s+([A-Z][a-z])', r'\1\2', text)  # Join split uppercase words
        text = re.sub(r'([a-z])\s+([A-Z][a-z])', r'\1\2', text)  # Join split camelCase words

        # Fix punctuation spacing (French convention)
        text = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([()])\s*', r'\1', text)

        # Remove any remaining excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def ensure_database_tables(self):
        """Ensure all required database tables exist"""
        self.logger.info("Creating database tables if they don't exist")
        db.create_all()
        self.logger.info("Database tables verified")

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import for ICS3U")

        with app.app_context():
            try:
                # Ensure database tables exist
                db.create_all()

                # Clear existing data first
                self.clear_existing_data()

                # Extract course information
                course_info = self.extract_course_info(content)

                # Create course
                course = Course(
                    code='ICS3U',
                    title_fr="Introduction au génie informatique, 11e année",
                    title_en="Introduction to Computer Science, Grade 11",
                    description_fr=course_info["description_fr"],
                    description_en=f"[NEEDS TRANSLATION] {course_info['description_fr']}",
                    prerequisite_fr=course_info["prerequisite_fr"],
                    prerequisite_en="None"
                )
                db.session.add(course)
                db.session.flush()
                self.logger.info(f"Created course: {course.code}")

                # Process each strand section
                strand_sections = self.get_strand_sections(content)
                for strand_code, title_fr, section_content in strand_sections:
                    self.logger.debug(f"Processing strand {strand_code}")

                    # Create Strand
                    strand = Strand(
                        course_id=course.id,
                        code=strand_code,
                        title_fr=title_fr,
                        title_en=f"[NEEDS TRANSLATION] {title_fr}"
                    )
                    db.session.add(strand)
                    db.session.flush()
                    self.logger.info(f"Created strand {strand_code}: {title_fr}")

                    # Parse and add overall expectations
                    overall_expectations = self.parse_overall_expectations(section_content, strand_code)
                    for exp_data in overall_expectations:
                        overall = OverallExpectation(
                            strand_id=strand.id,
                            **exp_data
                        )
                        db.session.add(overall)
                        db.session.flush()

                        # Parse and add specific expectations
                        specific_expectations = self.parse_specific_expectations(
                            section_content, 
                            strand_code,
                            exp_data['code'],
                            overall.id
                        )
                        for spec_data in specific_expectations:
                            specific = SpecificExpectation(**spec_data)
                            db.session.add(specific)
                            self.logger.debug(f"Created specific expectation: {spec_data['code']}")

                db.session.commit()
                self.logger.info("Curriculum import completed successfully")

            except Exception as e:
                db.session.rollback()
                self.logger.error(f"Error importing curriculum: {str(e)}")
                raise

    def extract_course_info(self, content: str) -> Dict[str, str]:
        """Extract course description and prerequisite"""
        # Look for the main course description between title and prerequisite
        desc_pattern = r'Ce cours.*?(?=Préalable\s*:)'
        desc_match = re.search(desc_pattern, content, re.DOTALL | re.IGNORECASE)
        desc_fr = self.clean_text(desc_match.group()) if desc_match else ""

        # Look for prerequisite
        prereq_pattern = r'Préalable\s*:\s*(.*?)(?=\n\n|\n[A-Z]\.|\Z)'
        prereq_match = re.search(prereq_pattern, content, re.DOTALL | re.IGNORECASE)
        prereq_fr = self.clean_text(prereq_match.group(1)) if prereq_match else "Aucun"

        return {
            "description_fr": desc_fr,
            "prerequisite_fr": prereq_fr
        }

    def get_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract individual strand sections from the curriculum content"""
        self.logger.debug("Extracting strand sections")

        # Split content into main sections using the letter headers
        # Updated pattern to better handle French formatting
        pattern = r'([A-D])\.\s+((?:[A-Za-zÀ-ÿ]|\s|\')+)(?:\s+ATTENTES|\s+année)\s*(.*?)(?=(?:[A-D]\.\s+[^\n]+\s+(?:ATTENTES|année))|$)'
        matches = list(re.finditer(pattern, content, re.DOTALL))

        sections = []
        seen_titles = set()

        for match in matches:
            code = match.group(1)
            title = self.clean_text(match.group(2))
            section_content = match.group(3)

            # Skip if we've already seen this title or it's empty
            if title in seen_titles or not title:
                continue

            seen_titles.add(title)
            self.logger.debug(f"Found strand {code}: {title}")

            # Extract content between ATTENTES and next major section
            content_pattern = r'ATTENTES.*?(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE)(.*?)(?=[A-D]\.\s+|$)'
            content_match = re.search(content_pattern, section_content, re.DOTALL)

            if content_match:
                expectations = content_match.group(1).strip()
                learning_content = content_match.group(2).strip()
                cleaned_content = f"ATTENTES\n{expectations}\nCONTENUS D'APPRENTISSAGE\n{learning_content}"
            else:
                cleaned_content = section_content.strip()

            sections.append((code, title, cleaned_content))

        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from ATTENTES section"""
        self.logger.debug(f"Parsing overall expectations for strand {strand_code}")

        # Find the ATTENTES section with improved pattern matching
        section_pattern = r'ATTENTES.*?(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        section_match = re.search(section_pattern, content, re.DOTALL | re.IGNORECASE)

        if not section_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return []

        expectations = []
        section = section_match.group(1)
        seen_codes = set()

        # Look for numbered expectations with improved pattern
        exp_pattern = rf'{strand_code}([0-9])\.\s*([^{strand_code}]+?)(?=(?:{strand_code}[0-9]\.|\n\s*{strand_code}[0-9]\.|\n\n|$))'
        matches = re.finditer(exp_pattern, section, re.DOTALL)

        for match in matches:
            number = match.group(1)
            description = self.clean_text(match.group(2))
            code = f'{strand_code}{number}'

            # Skip if already processed or empty
            if code in seen_codes or not description:
                continue

            seen_codes.add(code)
            self.logger.debug(f"Found overall expectation {code}: {description}")

            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': f"[NEEDS TRANSLATION] {description}"
            })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str, overall_code: str, overall_id: int) -> List[Dict[str, str]]:
        """Parse specific expectations from CONTENUS D'APPRENTISSAGE section"""
        self.logger.debug(f"Parsing specific expectations for {overall_code}")

        # Find the CONTENUS D'APPRENTISSAGE section
        section_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?\n(.*?)(?=(?:ATTENTES|[A-D]\.\s+|$))'
        section_match = re.search(section_pattern, content, re.DOTALL | re.IGNORECASE)

        if not section_match:
            self.logger.warning(f"No CONTENUS D'APPRENTISSAGE section found for strand {strand_code}")
            return []

        expectations = []
        section = section_match.group(1)
        seen_codes = set()

        # Improved pattern for specific expectations
        exp_pattern = rf'{overall_code}\.(\d+)\s+([^{strand_code}]+?)(?=(?:{strand_code}\d+\.\d+|\n\n|$))'
        matches = re.finditer(exp_pattern, section, re.DOTALL)

        for match in matches:
            sub_number = match.group(1)
            description = self.clean_text(match.group(2))
            code = f'{overall_code}.{sub_number}'

            # Skip if already processed or empty
            if code in seen_codes or not description:
                continue

            seen_codes.add(code)
            self.logger.debug(f"Found specific expectation {code}: {description}")

            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': f"[NEEDS TRANSLATION] {description}",
                'overall_expectation_id': overall_id
            })

        return expectations

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate placeholder English descriptions"""
        # For now, just indicate this needs translation
        return f"[NEEDS TRANSLATION] {desc_fr}"

    def clear_existing_data(self):
        """Clear existing curriculum data in the correct order to respect foreign key constraints"""
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