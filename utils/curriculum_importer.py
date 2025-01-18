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

        # Enhanced French text cleaning patterns
        replacements = {
            # Standard OCR corrections
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

            # Additional French-specific corrections
            'InformAtiquE': 'Informatique',
            'ProgrammAtion': 'Programmation',
            'DévEloppEmEnt': 'Développement',
            'SystEmE': 'Système',
            'StructurEs': 'Structures',
            'DonnéEs': 'Données',
            'ModElEs': 'Modèles',
            'AlgorithmEs': 'Algorithmes',
            'ContrOlE': 'Contrôle',
            'SécuritE': 'Sécurité',
            'IntErfacE': 'Interface',

            # Fix common OCR errors with accents
            'e\x60': 'è',
            'e\^': 'ê',
            'a\`': 'à',
            'e\´': 'é',

            # Clean up spacing around punctuation
            ' ,': ',',
            ' .': '.',
            ' ;': ';',
            ' :': ':',
            '( ': '(',
            ' )': ')',
        }

        # Apply text replacements
        for old, new in replacements.items():
            if old in text:
                self.logger.debug(f"Replacing '{old}' with '{new}'")
                text = text.replace(old, new)

        # Remove headers and page numbers with improved patterns
        text = re.sub(r'ICS3U\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'Introduction au génie informatique.*?\n', '', text)
        text = re.sub(r'LE CURRICULUM DE L\'ONTARIO.*?12e ANNÉE', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\d{1,3}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*Cours préuniversitaire.*?$', '', text, flags=re.MULTILINE)

        # Fix multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)

        # Clean up whitespace
        text = text.strip()

        self.logger.debug(f"Text cleaning completed. Original length: {len(text)}")
        return text

    def extract_course_description(self, content: str) -> str:
        """Extract course description with improved pattern matching"""
        # Updated pattern to better match French course description
        desc_patterns = [
            r'Ce cours\s+([^.]*(?:[^P]\.)+)(?=\s*Préalable\s*:)',
            r'Ce cours\s+(.*?)(?=\s*Préalable\s*:)',
            r'Ce cours\s+(.*?)(?=\s*[A-D]\s*\.)'
        ]

        for pattern in desc_patterns:
            desc_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if desc_match:
                desc = self.clean_text(desc_match.group(1))
                if desc:
                    self.logger.info(f"Successfully extracted course description ({len(desc)} chars)")
                    self.logger.debug(f"Description preview: {desc[:200]}...")
                    return desc

        self.logger.warning("Failed to extract course description")
        return ""

    def extract_prerequisite(self, content: str) -> str:
        """Extract prerequisite with improved pattern matching"""
        prereq_patterns = [
            r'Préalable\s*:\s*([^A-D][^\n]*)',
            r'Préalable\s*:\s*(.*?)(?=\s*[A-D]\s*\.)',
            r'Préalable\s*:\s*(.*?)(?=\s*$)'
        ]

        for pattern in prereq_patterns:
            prereq_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if prereq_match:
                prereq = self.clean_text(prereq_match.group(1))
                if prereq:
                    self.logger.info(f"Successfully extracted prerequisite: {prereq}")
                    return prereq

        self.logger.warning("Failed to extract prerequisite, using default")
        return 'Aucun'

    def extract_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract strand sections from curriculum content"""
        self.logger.info("Starting strand extraction...")
        self.logger.debug(f"Content length: {len(content)}")

        sections = []

        # First find all major section markers with French patterns
        section_markers = re.finditer(
            r'(?m)^\s*([A-D])\s*\.\s*(?![\d\.])\s*(?:((?:Environn?[Ee]m[Ee]nt|[Tt][Ee]chniqu[Ee]s|[Dd][Ee]v[Ee]lopp[Ee]m[Ee]nt|[Ee]nj[Ee]ux)\s+[^\n]+)|([^\n]+))',
            content
        )

        # Collect all section starts
        section_starts = []
        for match in section_markers:
            start_pos = match.start()
            code = match.group(1)
            # Take the first non-None group as title
            title = next(g for g in match.groups()[1:] if g is not None)
            section_starts.append((start_pos, code, title.strip()))
            self.logger.debug(f"Found section marker: {code} - {title}")

        if not section_starts:
            self.logger.warning("No section markers found - checking content structure")
            self.logger.debug(f"Content preview:\n{content[:1000]}")
            return sections

        # Process each section
        for i, (start_pos, code, title) in enumerate(section_starts):
            try:
                # Get section content up to next section or end of content
                if i < len(section_starts) - 1:
                    end_pos = section_starts[i + 1][0]
                else:
                    end_pos = len(content)

                section_content = content[start_pos:end_pos].strip()

                # Clean up title
                title = self.clean_text(title)

                self.logger.debug(f"Processing section {code}:")
                self.logger.debug(f"Title: {title}")
                self.logger.debug(f"Content length: {len(section_content)}")
                self.logger.debug(f"Content preview: {section_content[:200]}...")

                # Check for required components with flexible matching
                has_attentes = bool(re.search(r'(?:^|\s)ATTENTES(?:\s|$)', section_content, re.IGNORECASE | re.MULTILINE))
                has_contenus = bool(re.search(r'(?:^|\s)CONTENUS\s+D[\'']APPRENTISSAGE(?:\s|$)', section_content, re.IGNORECASE | re.MULTILINE))

                if has_attentes and has_contenus:
                    self.logger.info(f"Found valid strand {code}: {title}")
                    sections.append((code, title, section_content))
                else:
                    self.logger.warning(
                        f"Strand {code} missing required sections - "
                        f"ATTENTES: {has_attentes}, "
                        f"CONTENUS: {has_contenus}"
                    )
                    self.logger.debug("Markers not found in content:")
                    self.logger.debug(section_content[:500])

            except Exception as e:
                self.logger.error(f"Error processing section {code}: {str(e)}")
                continue

        self.logger.info(f"Found {len(sections)} valid strands")

        if not sections:
            self.logger.warning("No strands extracted - checking content structure")
            # Analyze content markers
            attentes_matches = re.finditer(r'ATTENTES', content, re.IGNORECASE)
            contenus_matches = re.finditer(r'CONTENUS\s+D[\'']APPRENTISSAGE', content, re.IGNORECASE)

            attentes_positions = [m.start() for m in attentes_matches]
            contenus_positions = [m.start() for m in contenus_matches]

            self.logger.debug(f"Content analysis:")
            self.logger.debug(f"- Found {len(attentes_positions)} ATTENTES sections at positions: {attentes_positions}")
            self.logger.debug(f"- Found {len(contenus_positions)} CONTENUS sections at positions: {contenus_positions}")

        return sections

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations from strand content with improved French support"""
        expectations = []

        # Extract ATTENTES section with improved pattern for French
        attentes_pattern = r'ATTENTES.*?(?:À la fin du cours[^:]*:)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE|$)'
        attentes_match = re.search(attentes_pattern, content, re.DOTALL | re.IGNORECASE)

        if not attentes_match:
            self.logger.warning(f"No ATTENTES section found for strand {strand_code}")
            return expectations

        expectations_text = attentes_match.group(1).strip()
        self.logger.debug(f"Found ATTENTES section for strand {strand_code}, length: {len(expectations_text)}")
        self.logger.debug(f"Content preview: {expectations_text[:200]}...")

        # Extract individual expectations with improved French pattern
        exp_pattern = rf'{strand_code}(\d+)\s*\.\s*(.*?)(?={strand_code}\d+\s*\.|\s*$)'
        matches = re.finditer(exp_pattern, expectations_text, re.DOTALL)

        match_count = 0
        for match in matches:
            number = match.group(1)
            description = self.clean_text(match.group(2))

            if description:
                code = f"{strand_code}{number}"
                self.logger.info(f"Found overall expectation {code}")
                self.logger.debug(f"Description: {description[:100]}...")

                expectations.append({
                    'code': code,
                    'description_fr': description,
                    'description_en': ''  # English version to be added later
                })
                match_count += 1

        self.logger.info(f"Total overall expectations found for strand {strand_code}: {match_count}")
        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str) -> Dict[str, List[Dict[str, str]]]:
        """Parse specific expectations grouped by overall expectations with enhanced French support"""
        specifics_by_overall = {}

        # Extract CONTENUS D'APPRENTISSAGE section with improved French pattern
        contenus_pattern = r'CONTENUS\s+D\'APPRENTISSAGE.*?(?:Pour satisfaire.*?:)?\s*(.*?)(?=(?:[A-D]\s*\.(?!\d))|$)'
        contenus_match = re.search(contenus_pattern, content, re.DOTALL | re.IGNORECASE)

        if not contenus_match:
            self.logger.warning(f"No CONTENUS D'APPRENTISSAGE section found for strand {strand_code}")
            return specifics_by_overall

        content_text = contenus_match.group(1).strip()
        self.logger.debug(f"Found CONTENUS section for strand {strand_code}, length: {len(content_text)}")
        self.logger.debug(f"Content preview: {content_text[:200]}...")

        # Improved pattern for French specific expectations
        # Handle potential variations in formatting
        exp_patterns = [
            rf'{strand_code}(\d+)\.(\d+)\s*(.*?)(?={strand_code}\d+\.\d+|$)',  # Standard format
            rf'{strand_code}\s*(\d+)\s*\.\s*(\d+)\s*(.*?)(?={strand_code}\s*\d+\s*\.\s*\d+|$)',  # Spaced format
            rf'{strand_code}(\d+)[\.,](\d+)\s*(.*?)(?={strand_code}\d+[\.,]\d+|$)'  # Handle period/comma variation
        ]

        total_matches = 0
        for pattern in exp_patterns:
            matches = re.finditer(pattern, content_text, re.DOTALL)

            for match in matches:
                try:
                    overall_num = match.group(1)
                    specific_num = match.group(2)
                    description = self.clean_text(match.group(3))

                    if description:
                        overall_code = f"{strand_code}{overall_num}"
                        specific_code = f"{strand_code}{overall_num}.{specific_num}"

                        if overall_code not in specifics_by_overall:
                            specifics_by_overall[overall_code] = []
                            self.logger.debug(f"Created new group for overall expectation {overall_code}")

                        # Check if this specific expectation already exists
                        exists = any(s['code'] == specific_code for s in specifics_by_overall[overall_code])

                        if not exists:
                            self.logger.info(f"Found specific expectation {specific_code}")
                            self.logger.debug(f"Description: {description[:100]}...")

                            specifics_by_overall[overall_code].append({
                                'code': specific_code,
                                'description_fr': description,
                                'description_en': ''  # English version to be added later
                            })
                            total_matches += 1
                        else:
                            self.logger.debug(f"Skipping duplicate specific expectation {specific_code}")

                except Exception as e:
                    self.logger.error(f"Error processing specific expectation match: {str(e)}")
                    continue

        self.logger.info(f"Total unique specific expectations found for strand {strand_code}: {total_matches}")
        for overall_code, specifics in specifics_by_overall.items():
            self.logger.info(f"Overall {overall_code} has {len(specifics)} specific expectations")

        if total_matches == 0:
            self.logger.warning(f"No specific expectations found for strand {strand_code}. Content might be malformed.")
            self.logger.debug(f"Content sample:\n{content_text[:500]}...")

        return specifics_by_overall

    def clear_existing_data(self):
        """Clear existing curriculum data using SQLAlchemy ORM"""
        self.logger.info("Clearing existing ICS3U curriculum data")
        try:
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
            db.session.flush()
            self.logger.info(f"Created course: {course.code}")

            # Process strands
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

                    for specific_data in specific_list:
                        specific = SpecificExpectation(
                            overall_expectation_id=overall.id,
                            code=specific_data['code'],
                            description_fr=specific_data['description_fr'],
                            description_en=specific_data['description_en']
                        )
                        db.session.add(specific)

                # Commit after each strand is processed
                db.session.commit()

            self.logger.info("Successfully completed curriculum import")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during curriculum import: {str(e)}")
            raise