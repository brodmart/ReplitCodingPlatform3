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
        """Clean up text by removing artifacts and fixing French formatting"""
        if not text:
            return ""

        # Remove course code and other headers
        text = re.sub(r'ICS3U\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'Introduction au génie informatique.*?\n', '', text)
        text = re.sub(r'LE CURRICULUM DE L\'ONTARIO.*?12e ANNÉE', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\d{1,3}\s*$', '', text, flags=re.MULTILINE)  # Remove page numbers
        text = re.sub(r'\s*Cours préuniversitaire.*?$', '', text, flags=re.MULTILINE)

        # Fix OCR issues with French text
        replacements = {
            'EnvironnEmEnt': 'Environnement',
            'informAtiquE': 'informatique',
            'trAvAil': 'travail',
            'tEchniquEs': 'techniques',
            'progrAmmAtion': 'programmation',
            'dévEloppEmEnt': 'développement',
            'logiciEls': 'logiciels',
            'sociétAux': 'sociétaux',
            'EnjEux': 'Enjeux',
            'pErspEctivEs': 'perspectives',
            'profEssionnEllEs': 'professionnelles',
            'g nie': 'génie',
            'pr universitaire': 'préuniversitaire',
            'e ann e': 'e année',
            '11e ann e': '11e année',
            'g nie informatique': 'génie informatique',
            'émE': 'ème',
            'ee ': 'e ',
            ' e ': 'e ',
            'é e': 'ée',
            'dE ': 'de ',
            'Et ': 'et ',
            'AtiquE': 'atique',
            ' EMEnt': 'ement',
            'E e': 'e',
            'e E': 'e',
            'tE ': 'té ',
            'Em ': 'em ',
            'quE ': 'que ',
            ' E ': 'e ',
            '( p. ex.,': '(p. ex.,'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Clean up whitespace and typography
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections from curriculum content"""
        self.logger.info("Starting strand extraction...")

        # Normalize newlines and clean up content
        content = content.replace('\r\n', '\n')

        # Look for strand headers and their content
        sections = []
        # Updated pattern to better match French curriculum format
        strand_pattern = (
            r'(?:^|\n)\s*'  # Start of line or newline
            r'([A-D])'      # Strand letter
            r'\s*\.'        # Optional spaces and period
            r'\s*([^\n]+?)'  # Strand title (non-greedy)
            r'(?=\s*\n+\s*ATTENTES)'  # Followed by ATTENTES
            r'(.*?)'        # Content (non-greedy)
            r'(?=(?:\n\s*[A-D]\s*\.|$))'  # Until next strand or end
        )

        matches = list(re.finditer(strand_pattern, content, re.DOTALL | re.IGNORECASE))

        for match in matches:
            code = match.group(1)
            title = self.clean_text(match.group(2))
            section_content = match.group(3)

            if title and "ATTENTES" in section_content:
                self.logger.info(f"Found strand {code}: {title}")
                sections.append((code, title, section_content))
                self.logger.debug(f"Content length for strand {code}: {len(section_content)}")

        self.logger.info(f"Extracted {len(sections)} strand sections")
        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content"""
        expectations = []

        # Extract content between ATTENTES and CONTENUS D'APPRENTISSAGE
        pattern = r'ATTENTES.*?(?:À la fin du cours[^:]*:)?\s*(.*?)(?=\s*CONTENUS|$)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            expectations_text = match.group(1)
            self.logger.debug(f"Found expectations text for strand {strand_code}")

            # Extract individual expectations with their codes
            exp_pattern = rf'{strand_code}(\d+)\.\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.|$)'
            exp_matches = list(re.finditer(exp_pattern, expectations_text, re.DOTALL))

            for match in exp_matches:
                number = match.group(1)
                description = self.clean_text(match.group(2))

                if description:
                    code = f"{strand_code}{number}"
                    self.logger.info(f"Found overall expectation {code}")
                    expectations.append({
                        'code': code,
                        'description_fr': description,
                        'description_en': ''  # Will be translated later
                    })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations grouped by overall expectations"""
        specifics_by_overall = {}

        # Find CONTENUS D'APPRENTISSAGE section
        pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?Pour satisfaire.*?:\s*(.*?)(?=(?:\n\s*[A-D]\s*\.|\s*Cours|$))'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            content_text = match.group(1)
            self.logger.debug(f"Processing specific expectations for strand {strand_code}")

            # Extract specific expectations with their codes
            exp_pattern = rf'{strand_code}(\d+)\.(\d+)\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.\d+|{strand_code}\d+\.|$)'
            exp_matches = list(re.finditer(exp_pattern, content_text, re.DOTALL))

            for match in exp_matches:
                overall_num = match.group(1)
                specific_num = match.group(2)
                description = self.clean_text(match.group(3))

                if description:
                    code = f"{strand_code}{overall_num}.{specific_num}"
                    overall_code = f"{strand_code}{overall_num}"

                    if overall_code not in specifics_by_overall:
                        specifics_by_overall[overall_code] = []

                    self.logger.info(f"Found specific expectation {code}")
                    specifics_by_overall[overall_code].append({
                        'code': code,
                        'description_fr': description,
                        'description_en': ''  # Will be translated later
                    })

        return specifics_by_overall

    def extract_course_info(self, content: str) -> Dict[str, str]:
        """Extract course information"""
        # Extract course description
        desc_pattern = r'Ce cours.*?(?=\s*Préalable\s*:)'
        desc_match = re.search(desc_pattern, content, re.DOTALL)
        description = self.clean_text(desc_match.group()) if desc_match else ''

        # Extract prerequisite
        prereq_pattern = r'Préalable\s*:\s*(.*?)(?=\n\s*[A-Z]|\Z)'
        prereq_match = re.search(prereq_pattern, content, re.DOTALL)
        prerequisite = self.clean_text(prereq_match.group(1)) if prereq_match else 'Aucun'

        return {
            'description_fr': description,
            'prerequisite_fr': prerequisite
        }

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clear existing data
            self.clear_existing_data()

            # Extract course information
            course_info = self.extract_course_info(content)

            # Create course
            course = Course(
                code='ICS3U',
                title_fr='Introduction au génie informatique, 11e année cours préuniversitaire',
                title_en='Introduction to Computer Science, Grade 11 University Preparation',
                description_fr=course_info['description_fr'],
                description_en='',  # Will be translated later
                prerequisite_fr=course_info['prerequisite_fr'],
                prerequisite_en='None'
            )

            db.session.add(course)
            db.session.flush()
            self.logger.info(f"Created course: {course.code}")

            # Process all strands
            strands = self.extract_strand_sections(content)
            for strand_code, strand_title, strand_content in strands:
                self.logger.info(f"Processing strand {strand_code}: {strand_title}")

                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=strand_code,
                    title_fr=strand_title,
                    title_en=''  # Will be translated later
                )
                db.session.add(strand)
                db.session.flush()

                # Process overall expectations
                overall_expectations = self.parse_overall_expectations(strand_content, strand_code)
                for overall_data in overall_expectations:
                    overall = OverallExpectation(
                        strand_id=strand.id,
                        code=overall_data['code'],
                        description_fr=overall_data['description_fr'],
                        description_en=overall_data['description_en']
                    )
                    db.session.add(overall)
                    db.session.flush()

                    # Process specific expectations for this overall expectation
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
            self.logger.info("Successfully completed curriculum import")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during curriculum import: {str(e)}")
            raise

    def clear_existing_data(self):
        """Clear existing curriculum data"""
        self.logger.info("Clearing existing ICS3U curriculum data")
        try:
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate placeholder English descriptions"""
        return f"[NEEDS TRANSLATION] {desc_fr}"