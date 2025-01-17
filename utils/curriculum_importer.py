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

        # Remove page numbers and headers
        text = re.sub(r'\d{1,3}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'LE CURRICULUM DE L\'ONTARIO.*?12e ANNÉE', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'Introduction au génie informatique.*?\n', '', text)
        text = re.sub(r'ICS3U[\s\n]+', '', text)  # Remove course code occurrences

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
            ' ann e ': ' année ',
            'EntinformatiqueE': 'ent informatique',
            'Edetravail': 'e de travail',
            'téchniqu E': 'technique',
            'progr Amm Ation': 'programmation',
            'g nie': 'génie',
            'pr universitaire': 'préuniversitaire',
            ' informatique': 'informatique',
            'e ann e': 'e année',
            '11e ann e': '11e année',
            'g nie informatique': 'génie informatique',
            # Strand-specific fixes
            'EnvironnEmEnt': 'Environnement',
            'informAtiquE': 'informatique',
            'trAvAil': 'travail',
            'tEchniquEs': 'techniques',
            'progrAmmAtion': 'programmation',
            'dévEloppEmEnt': 'développement',
            'logiciEls': 'logiciels',
            'sociétAux': 'sociétaux',
            'EnjEux': 'Enjeux'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Fix spaces around punctuation according to French rules
        text = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([()])\s*', r'\1', text)

        # Fix ordinal numbers
        text = re.sub(r'(\d+)\s*[eE]\s+', r'\1e ', text)

        # Remove multiple spaces and clean up
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections from the curriculum content"""
        self.logger.info("Starting strand extraction...")

        # Remove any leading/trailing whitespace and normalize newlines
        content = content.strip()
        content = re.sub(r'\r\n', '\n', content)

        # Split content into major sections using strand identifiers
        strand_pattern = r'([A-D])\.\s*([^\.]+?)(?=ATTENTES|$)(.*?)(?=(?:[A-D]\.\s)|$)'
        strand_matches = list(re.finditer(strand_pattern, content, re.DOTALL))

        self.logger.debug(f"Found {len(strand_matches)} potential strand matches")

        sections = []
        for match in strand_matches:
            code = match.group(1)
            title = self.clean_text(match.group(2))
            section_content = match.group(3)

            if title and section_content:
                if "ATTENTES" in section_content:
                    self.logger.info(f"Found valid strand {code}: {title}")
                    sections.append((code, title, section_content))
                    self.logger.debug(f"Content snippet: {section_content[:200]}...")
                else:
                    self.logger.warning(f"Skipping strand {code} - missing ATTENTES section")

        self.logger.info(f"Successfully extracted {len(sections)} strand sections")
        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content"""
        self.logger.info(f"Parsing overall expectations for strand {strand_code}")

        expectations = []

        # Extract the ATTENTES section
        attentes_pattern = r'ATTENTES.*?(?:À la fin du cours[^:]*:)?\s*(.*?)(?=CONTENUS|$)'
        attentes_match = re.search(attentes_pattern, content, re.DOTALL | re.IGNORECASE)

        if attentes_match:
            expectations_text = attentes_match.group(1)
            self.logger.debug(f"Found ATTENTES section: {expectations_text[:200]}...")

            # Match individual expectations with their codes
            exp_pattern = rf'{strand_code}(\d+)\.\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.|$)'
            matches = list(re.finditer(exp_pattern, expectations_text, re.DOTALL))

            for match in matches:
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
        else:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations from strand content"""
        self.logger.info(f"Parsing specific expectations for strand {strand_code}")

        specifics_by_overall = {}

        # Extract the CONTENUS D'APPRENTISSAGE section
        contenus_pattern = r'CONTENUS\s+D[\'E]\s*APPRENTISSAGE.*?Pour satisfaire.*?:\s*(.*?)(?=\Z|\n\n[A-D]\.)'
        contenus_match = re.search(contenus_pattern, content, re.DOTALL | re.IGNORECASE)

        if contenus_match:
            content_text = contenus_match.group(1)
            self.logger.debug(f"Found CONTENUS section: {content_text[:200]}...")

            # Extract specific expectations with their codes
            exp_pattern = rf'{strand_code}(\d+)\.(\d+)\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.\d+|$)'
            matches = list(re.finditer(exp_pattern, content_text, re.DOTALL))

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
                        'description_en': ''  # Will be translated later
                    })
        else:
            self.logger.warning(f"No CONTENUS section found for strand {strand_code}")

        return specifics_by_overall

    def extract_course_info(self, content: str) -> Dict[str, str]:
        """Extract course information including title and description"""
        self.logger.info("Extracting course information...")

        info = {}

        # Extract description
        desc_pattern = r'Ce cours.*?(?=Préalable\s*:)'
        desc_match = re.search(desc_pattern, content, re.DOTALL)
        if desc_match:
            info['description_fr'] = self.clean_text(desc_match.group())
            self.logger.info("Found course description")
        else:
            self.logger.warning("Could not find course description")
            info['description_fr'] = ''

        # Extract prerequisite
        prereq_pattern = r'Préalable\s*:\s*(.*?)(?=\n\n|\Z)'
        prereq_match = re.search(prereq_pattern, content)
        if prereq_match:
            info['prerequisite_fr'] = self.clean_text(prereq_match.group(1))
            self.logger.info(f"Found prerequisite: {info['prerequisite_fr']}")
        else:
            info['prerequisite_fr'] = 'Aucun'
            self.logger.info("No prerequisite found, using default: Aucun")

        return info

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import process")

        try:
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

            # Process strands
            strands = self.extract_strand_sections(content)
            self.logger.info(f"Processing {len(strands)} strands")

            for strand_code, strand_title, strand_content in strands:
                # Create strand
                strand = Strand(
                    course_id=course.id,
                    code=strand_code,
                    title_fr=strand_title,
                    title_en=''  # Will be translated later
                )

                db.session.add(strand)
                db.session.flush()
                self.logger.info(f"Created strand {strand_code}: {strand_title}")

                # Process overall expectations
                overall_expectations = self.parse_overall_expectations(strand_content, strand_code)
                self.logger.info(f"Found {len(overall_expectations)} overall expectations for strand {strand_code}")

                for overall_data in overall_expectations:
                    overall = OverallExpectation(
                        strand_id=strand.id,
                        code=overall_data['code'],
                        description_fr=overall_data['description_fr'],
                        description_en=overall_data['description_en']
                    )

                    db.session.add(overall)
                    db.session.flush()
                    self.logger.info(f"Created overall expectation: {overall.code}")

                    # Process specific expectations
                    specifics = self.parse_specific_expectations(strand_content, strand_code).get(overall_data['code'], [])
                    self.logger.info(f"Found {len(specifics)} specific expectations for {overall.code}")

                    for specific_data in specifics:
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
            self.logger.info("Successfully cleared existing data")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise

    def clean_specific_expectation(self, text: str) -> str:
        """Clean and format specific expectation text"""
        if not text:
            return ""

        # Initial cleaning
        text = text.strip()
        text = re.sub(r'^\s*\d+\.\s*', '', text)
        text = re.sub(r'^\s*[•●⚫⬤]\s*', '', text)

        # Handle examples in parentheses
        text = re.sub(r'\(\s*p\.\s*ex\.,([^)]+)\)', r'(p. ex., \1)', text)
        text = re.sub(r'\(\s*p\.\s*ex\.\s*:', r'(p. ex., ', text)
        text = re.sub(r'\(\s*p\.\s*ex\.\s*\)', r'(p. ex.)', text)

        # Fix common OCR artifacts and French text issues
        replacements = {
            ' e année': 'e année',
            'p.ex.': 'p. ex.',
            '( p. ex.,': '(p. ex.,',
            'etc...)': 'etc.)',
            '...)': '.)',
            '–': '-',
            '«': '"',
            '»': '"',
            ' :': ' :',
            ';e': 'e',
            'E e': 'e',
            'e E': 'e',
            'émE': 'ème',
            ' ee ': 'e ',
            'eeé': 'é',
            'éee': 'ée'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Fix spaces around punctuation according to French typography rules
        text = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([()])\s*', r'\1', text)

        # Remove any remaining OCR artifacts (single letters with spaces)
        text = re.sub(r'\s+([A-Za-z])\s+', r'\1', text)

        # Final cleanup
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate placeholder English descriptions"""
        return f"[NEEDS TRANSLATION] {desc_fr}"

    def clear_existing_data(self):
        """Clear existing curriculum data"""
        self.logger.info("Clearing existing ICS3U curriculum data")

        try:
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
            self.logger.info("Successfully cleared existing data")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise