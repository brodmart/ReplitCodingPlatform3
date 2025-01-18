"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from app import db
from sqlalchemy.orm import joinedload
from sqlalchemy import and_

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

    def preprocess_content(self, content: str) -> str:
        """Preprocess the curriculum content to prepare for strand extraction"""
        # Normalize newlines and clean content
        content = content.replace('\r\n', '\n')
        content = self.clean_text(content)

        # Remove the introduction section before the first strand
        content = re.sub(r'^.*?(?=\n[A-D]\s*\.)', '', content, flags=re.DOTALL)

        # Ensure proper spacing around strand markers
        content = re.sub(r'([A-D])\s*\.\s*', r'\n\1. ', content)

        # Remove any remaining page headers or footers
        content = re.sub(r'\n.*?ICS3U.*?\n', '\n', content)

        return content.strip()

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections from curriculum content"""
        self.logger.info("Starting strand extraction...")

        # Preprocess the content
        content = self.preprocess_content(content)

        # Log preprocessed content for debugging
        self.logger.debug(f"Preprocessed content preview (first 1000 chars):\n{content[:1000]}")

        # Find all strand sections (A, B, C, D)
        sections = []

        # Split content at main strand markers
        strand_splits = re.split(r'\n(?=[A-D]\s*\.)', content)

        for split in strand_splits:
            if not split.strip():
                continue

            # Extract strand code, title, and content
            match = re.match(r'([A-D])\s*\.\s*(.*?)(?:\n|$)(.*)', split.strip(), re.DOTALL)
            if not match:
                continue

            code = match.group(1).upper()
            title = self.clean_text(match.group(2))
            content = self.clean_text(match.group(3))

            self.logger.debug(f"Potential strand match found:")
            self.logger.debug(f"  Code: {code}")
            self.logger.debug(f"  Title: {title[:100]}...")
            self.logger.debug(f"  Content preview: {content[:200]}...")

            # Verify this is a valid strand section
            if title and content and ('ATTENTES' in content or 'CONTENUS' in content):
                self.logger.info(f"Found valid strand {code}: {title}")
                sections.append((code, title, content))
            else:
                self.logger.warning(f"Skipping invalid strand {code} - missing required sections")

        self.logger.info(f"Found {len(sections)} strands")

        # Log details of found strands
        for code, title, _ in sections:
            self.logger.info(f"  Strand {code}: {title}")

        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content"""
        expectations = []

        # Updated pattern to better match French curriculum format
        attentes_pattern = r'(?:ATTENTES|À la fin de ce cours.*?).*?(?:À la fin du cours[^:]*:)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        attentes_match = re.search(attentes_pattern, content, re.DOTALL | re.IGNORECASE)

        if not attentes_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return expectations

        expectations_text = attentes_match.group(1).strip()
        self.logger.debug(f"Found expectations text for strand {strand_code}: {expectations_text[:200]}...")

        # Extract individual expectations with improved pattern
        exp_pattern = rf'{strand_code}\s*(\d+)\s*\.?\s*(.*?)(?={strand_code}\s*\d+\s*\.|\n\s*\n|$)'
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

        # Updated pattern to better match French curriculum format
        contenus_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?(?:Pour satisfaire.*?:)?\s*(.*?)(?=(?:\n\s*[A-D]|\s*Cours|$))'
        contenus_match = re.search(contenus_pattern, content, re.DOTALL | re.IGNORECASE)

        if not contenus_match:
            self.logger.warning(f"No CONTENUS D'APPRENTISSAGE section found for strand {strand_code}")
            return specifics_by_overall

        content_text = contenus_match.group(1).strip()
        self.logger.debug(f"Found specific expectations text for strand {strand_code}: {content_text[:200]}...")

        # Extract specific expectations with improved pattern
        exp_pattern = (
            rf'{strand_code}\s*(\d+)\s*\.\s*(\d+)\s*'  # Code pattern (e.g., A1.1)
            r'([^{]+)'  # Description (non-greedy match until next code)
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

    def clear_existing_data(self):
        """Clear existing curriculum data using SQLAlchemy ORM"""
        self.logger.info("Clearing existing ICS3U curriculum data")
        try:
            # Get the course with related data
            course = Course.query.options(
                joinedload(Course.strands).joinedload(Strand.overall_expectations).joinedload(OverallExpectation.specific_expectations)
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
            db.session.flush()  # Get the course ID without committing
            self.logger.info(f"Created course: {course.code}")

            # Process strands with batch processing
            strands = self.extract_strand_sections(content)
            self.logger.info(f"Processing {len(strands)} strands")

            for strand_code, strand_title, strand_content in strands:
                self.logger.info(f"Processing strand {strand_code}: {strand_title}")

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

                # Batch process overall expectations
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

                    # Batch process specific expectations
                    for specific_data in specific_list:
                        specific = SpecificExpectation(
                            overall_expectation_id=overall.id,
                            code=specific_data['code'],
                            description_fr=specific_data['description_fr'],
                            description_en=specific_data['description_en']
                        )
                        db.session.add(specific)

                # Commit after each strand's data is processed
                db.session.commit()

            self.logger.info("Successfully completed curriculum import")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during curriculum import: {str(e)}")
            raise

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