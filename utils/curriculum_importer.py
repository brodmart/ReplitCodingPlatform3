"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from app import db
from sqlalchemy import text

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def clean_text(self, text: str) -> str:
        """Clean up text by removing artifacts and fixing French formatting"""
        if not text:
            return ""

        # Fix OCR artifacts in French text
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
            ' e ': 'e ',
            'é e': 'ée',
            'dE ': 'de ',
            'Et ': 'et ',
            'AtiquE': 'atique',
            ' EMEnt': 'ement',
            '  ': ' '  # Remove double spaces
        }

        # Apply text replacements
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Remove headers and page numbers
        text = re.sub(r'ICS3U\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'Introduction au génie informatique.*?\n', '', text)
        text = re.sub(r'LE CURRICULUM DE L\'ONTARIO.*?12e ANNÉE', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\d{1,3}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*Cours préuniversitaire.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections from curriculum content"""
        self.logger.info("Starting strand extraction...")

        # Normalize newlines
        content = content.replace('\r\n', '\n')

        # Find all strand sections (A, B, C, D)
        sections = []
        strand_pattern = r'(?:^|\n)\s*([A-D])\s*\.\s*([^\n]+)(?:\n|$)(.*?)(?=(?:\n\s*[A-D]\s*\.|\Z))'
        matches = re.finditer(strand_pattern, content, re.DOTALL)

        for match in matches:
            code = match.group(1)
            title = self.clean_text(match.group(2))
            content = self.clean_text(match.group(3))

            if 'ATTENTES' in content:
                self.logger.info(f"Found strand {code}: {title}")
                self.logger.debug(f"Content preview: {content[:200]}...")
                sections.append((code, title, content))

        self.logger.info(f"Found {len(sections)} strands")
        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content"""
        expectations = []

        # Extract ATTENTES section
        attentes_pattern = r'ATTENTES.*?(?:À la fin du cours[^:]*:)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        attentes_match = re.search(attentes_pattern, content, re.DOTALL | re.IGNORECASE)

        if not attentes_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return expectations

        expectations_text = attentes_match.group(1).strip()
        self.logger.debug(f"Found expectations text for strand {strand_code}: {expectations_text[:200]}...")

        # Extract individual expectations
        exp_pattern = rf'{strand_code}\s*(\d+)\s*\.\s*(.*?)(?={strand_code}\s*\d+\s*\.|$)'
        matches = re.finditer(exp_pattern, expectations_text, re.DOTALL)

        for match in matches:
            number = match.group(1)
            description = self.clean_text(match.group(2))

            if description:
                code = f"{strand_code}{number}"
                self.logger.info(f"Found overall expectation {code}")
                expectations.append({
                    'code': code,
                    'description_fr': description,
                    'description_en': ''
                })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations grouped by overall expectations"""
        specifics_by_overall = {}

        # Extract CONTENUS D'APPRENTISSAGE section
        contenus_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?Pour satisfaire.*?:\s*(.*?)(?=(?:\n\s*[A-D]|\s*Cours|$))'
        contenus_match = re.search(contenus_pattern, content, re.DOTALL | re.IGNORECASE)

        if not contenus_match:
            self.logger.warning(f"No CONTENUS D'APPRENTISSAGE section found for strand {strand_code}")
            return specifics_by_overall

        content_text = contenus_match.group(1).strip()
        self.logger.debug(f"Found specific expectations text for strand {strand_code}: {content_text[:200]}...")

        # Extract specific expectations
        exp_pattern = (
            rf'{strand_code}\s*(\d+)\s*\.\s*(\d+)\s*'  # Code pattern (e.g., A1.1)
            r'(.*?)'  # Description
            rf'(?={strand_code}\s*\d+\s*\.\s*\d+|{strand_code}\s*\d+\s*\.|$)'  # Look ahead
        )

        matches = re.finditer(exp_pattern, content_text, re.DOTALL)
        for match in matches:
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
                    'description_en': ''
                })

        return specifics_by_overall

    def extract_course_description(self, content: str) -> str:
        """Extract course description"""
        desc_pattern = r'Ce cours[^P]*?(?=Préalable\s*:)'
        desc_match = re.search(desc_pattern, content, re.DOTALL)
        desc = self.clean_text(desc_match.group()) if desc_match else ''
        self.logger.debug(f"Extracted course description: {desc[:200]}...")
        return desc

    def extract_prerequisite(self, content: str) -> str:
        """Extract prerequisite"""
        prereq_pattern = r'Préalable\s*:\s*([^A-D][^\n]*)'
        prereq_match = re.search(prereq_pattern, content, re.DOTALL)
        prereq = self.clean_text(prereq_match.group(1)) if prereq_match else 'Aucun'
        self.logger.debug(f"Extracted prerequisite: {prereq}")
        return prereq

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
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
            strands = self.extract_strand_sections(content)
            self.logger.info(f"Processing {len(strands)} strands")

            for strand_code, strand_title, strand_content in strands:
                self.logger.info(f"Processing strand {strand_code}: {strand_title}")

                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=strand_code,
                    title_fr=strand_title,
                    title_en=''
                )
                db.session.add(strand)
                db.session.flush()

                # Process overall expectations
                overall_expectations = self.parse_overall_expectations(strand_content, strand_code)
                self.logger.info(f"Found {len(overall_expectations)} overall expectations")

                for overall_data in overall_expectations:
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
                    specific_list = specifics.get(overall_data['code'], [])
                    self.logger.info(f"Found {len(specific_list)} specific expectations for {overall.code}")

                    for specific_data in specific_list:
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
        """Clear existing curriculum data with proper cascading"""
        self.logger.info("Clearing existing ICS3U curriculum data")
        try:
            # Use raw SQL with proper cascading
            db.session.execute(text("""
                DELETE FROM specific_expectations 
                WHERE overall_expectation_id IN (
                    SELECT oe.id 
                    FROM overall_expectations oe
                    JOIN strands s ON oe.strand_id = s.id
                    JOIN courses c ON s.course_id = c.id
                    WHERE c.code = 'ICS3U'
                )
            """))

            db.session.execute(text("""
                DELETE FROM overall_expectations 
                WHERE strand_id IN (
                    SELECT s.id 
                    FROM strands s
                    JOIN courses c ON s.course_id = c.id
                    WHERE c.code = 'ICS3U'
                )
            """))

            db.session.execute(text("""
                DELETE FROM strands 
                WHERE course_id IN (
                    SELECT id FROM courses WHERE code = 'ICS3U'
                )
            """))

            db.session.execute(text("DELETE FROM courses WHERE code = 'ICS3U'"))

            db.session.commit()
            self.logger.info("Successfully cleared existing data")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise