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

    def clean_text(self, text: str) -> str:
        """Clean up text by removing extra spaces and newlines while preserving French accents"""
        # Fix common OCR issues with French text
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
        text = text.replace('e e', 'e')  # Fix double e's
        text = text.replace('E E', 'E')  # Fix uppercase double E's
        text = text.replace('tE ', 'TE ')
        text = text.replace('Em ', 'EM ')
        text = text.replace('dE ', 'DE ')
        # Fix split words
        text = re.sub(r'([A-Z])\s+([A-Z])', r'\1\2', text)  # Join split uppercase words
        text = re.sub(r'([a-z])\s+([A-Z])', r'\1\2', text)  # Join split camelCase words
        text = re.sub(r'\s*([.,;:!?])\s*', r'\1 ', text)  # Fix spacing around punctuation
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
            # Ensure database tables exist
            self.ensure_database_tables()

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
                description_en="[NEEDS TRANSLATION] " + course_info["description_fr"],
                prerequisite_fr=course_info["prerequisite_fr"],
                prerequisite_en="None"
            )
            db.session.add(course)
            db.session.flush()
            self.logger.info(f"Created course: {course.code}")

            # Process each strand section
            strand_sections = self.get_strand_sections(content)
            for strand_code, title_fr, section_content in strand_sections:
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

                # Parse and add overall expectations for this strand
                overall_expectations = self.parse_overall_expectations(section_content, strand_code)
                for exp_data in overall_expectations:
                    overall = OverallExpectation(
                        strand_id=strand.id,
                        **exp_data
                    )
                    db.session.add(overall)
                    db.session.flush()
                    self.logger.debug(f"Created overall expectation: {exp_data['code']}")

                    # Parse and add specific expectations for this overall expectation
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

    def extract_course_info(self, content: str) -> Dict[str, str]:
        """Extract course description and prerequisite"""
        # Look for the main course description at the start
        desc_pattern = r'Ce cours.*?(?=Préalable)'
        desc_match = re.search(desc_pattern, content, re.DOTALL)
        desc_fr = self.clean_text(desc_match.group()) if desc_match else ""

        # Look for prerequisite
        prereq_pattern = r'Préalable\s*:\s*(.*?)(?=\n\n|\n[A-Z]\.)'
        prereq_match = re.search(prereq_pattern, content)
        prereq_fr = self.clean_text(prereq_match.group(1)) if prereq_match else "Aucun"

        return {
            "description_fr": desc_fr,
            "prerequisite_fr": prereq_fr
        }

    def get_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract individual strand sections from the curriculum content"""
        self.logger.debug("Extracting strand sections")

        # Split content into main sections using the letter headers
        pattern = r'([A-D])\.\s+((?:[A-Za-zÀ-ÿ]|\s|\')+)\s*(?:ATTENTES|année)\s*(.*?)(?=(?:[A-D]\.\s+[^\n]+\s+(?:ATTENTES|année))|$)'
        matches = list(re.finditer(pattern, content, re.DOTALL))

        sections = []
        seen_titles = set()

        for match in matches:
            code = match.group(1)
            title = self.clean_text(match.group(2))
            content = match.group(3)

            # Skip if we've already seen this title or it's empty
            if title in seen_titles or not title:
                continue

            seen_titles.add(title)
            self.logger.debug(f"Found strand {code}: {title}")

            # Extract the content between ATTENTES and next major section
            content_pattern = r'ATTENTES.*?(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE)(.*?)(?=[A-D]\.\s+|$)'
            content_match = re.search(content_pattern, content, re.DOTALL)

            if content_match:
                cleaned_content = f"ATTENTES\n{content_match.group(1)}\nCONTENUS D'APPRENTISSAGE\n{content_match.group(2)}"
            else:
                cleaned_content = content

            sections.append((code, title, cleaned_content))

        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from ATTENTES section"""
        self.logger.debug(f"Parsing overall expectations for strand {strand_code}")

        # Find the ATTENTES section
        section_pattern = r'ATTENTES.*?(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        section_match = re.search(section_pattern, content, re.DOTALL)

        if not section_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return []

        expectations = []
        section = section_match.group(1)
        seen_codes = set()

        # Look for numbered expectations (e.g., "A1.", "A2.", etc.)
        exp_pattern = rf'{strand_code}([0-9])\.\s*([^\.]+?)(?=(?:{strand_code}[0-9]\.|\n\s*{strand_code}[0-9]\.|\n\n|$))'
        matches = re.finditer(exp_pattern, section, re.DOTALL)

        for match in matches:
            number = match.group(1)
            description = self.clean_text(match.group(2))
            code = f'{strand_code}{number}'

            # Skip if we've already processed this code or description is empty
            if code in seen_codes or not description:
                continue

            seen_codes.add(code)
            self.logger.debug(f"Found overall expectation {code}: {description}")
            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': self.get_english_description(code, description)
            })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str, overall_code: str, overall_id: int) -> List[Dict[str, str]]:
        """Parse specific expectations from CONTENUS D'APPRENTISSAGE section"""
        self.logger.debug(f"Parsing specific expectations for {overall_code}")

        # Find the CONTENUS D'APPRENTISSAGE section
        section_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?\n(.*?)(?=(?:ATTENTES|[A-D]\.\s+|$))'
        section_match = re.search(section_pattern, content, re.DOTALL)

        if not section_match:
            self.logger.warning(f"No CONTENUS D'APPRENTISSAGE section found for strand {strand_code}")
            return []

        expectations = []
        section = section_match.group(1)
        seen_codes = set()

        # Look for specific expectations that match the overall expectation code
        exp_pattern = rf'{overall_code}\.(\d+)\s+([^\.]+?)(?=(?:{strand_code}\d+\.\d+|\n\n|$))'
        matches = re.finditer(exp_pattern, section, re.DOTALL)

        for match in matches:
            sub_number = match.group(1)
            description = self.clean_text(match.group(2))
            code = f'{overall_code}.{sub_number}'

            # Skip if we've already processed this code or description is empty
            if code in seen_codes or not description:
                continue

            seen_codes.add(code)
            self.logger.debug(f"Found specific expectation {code}: {description}")

            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': self.get_english_description(code, description),
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

        course = Course.query.filter_by(code='ICS3U').first()
        if course:
            # First delete all specific expectations
            strands = Strand.query.filter_by(course_id=course.id).all()
            for strand in strands:
                overall_expectations = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                for overall in overall_expectations:
                    SpecificExpectation.query.filter_by(overall_expectation_id=overall.id).delete()
                # Then delete overall expectations
                OverallExpectation.query.filter_by(strand_id=strand.id).delete()
            # Then delete strands
            Strand.query.filter_by(course_id=course.id).delete()
            # Finally delete the course
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
            self.logger.info("Successfully cleared existing data")