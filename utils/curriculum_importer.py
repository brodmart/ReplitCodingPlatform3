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
            ' ann e ': ' année ',
            'EntinformatiqueE': 'ent informatique',
            'Edetravail': 'e de travail',
            'téchniqu E': 'technique',
            'progr Amm Ation': 'programmation'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Fix spaces between words more carefully
        text = re.sub(r'(?<=[a-zà-ÿ])([A-ZÀ-Ÿ])', r' \1', text)  # Add space before capital letters
        text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ÿ])', r'\1 \2', text)   # Space between lowercase and uppercase
        text = re.sub(r'(\d)\s*([eE])\s+', r'\1\2 ', text)        # Fix ordinal numbers (e.g., "11e année")

        # Fix French punctuation spacing
        text = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', text)
        text = re.sub(r'\s*([()])\s*', r'\1', text)

        # Normalize multiple spaces and clean up
        text = re.sub(r'\s+', ' ', text).strip()

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

        # Split content into sections
        sections = re.split(r'(?:\n\s*){2,}', content)

        # Find the CONTENUS D'APPRENTISSAGE section
        contenus_pattern = r'CONTENUS\s+D(?:\'|E)?\s*APPRENTISSAGE'
        contenus_section = None

        for section in sections:
            if re.search(contenus_pattern, section, re.IGNORECASE):
                contenus_section = section
                break

        if not contenus_section:
            self.logger.warning(f"No specific expectations section found for strand {strand_code}")
            self.logger.debug(f"Content sections available:\n" + "\n---\n".join(sections[:3]))
            return {}

        self.logger.debug(f"Found CONTENUS D'APPRENTISSAGE section:\n{contenus_section[:500]}...")

        # Extract expectations content
        intro_pattern = r'Pour satisfaire.*?:\s*(.*?)(?=(?:\n\s*){2,}|$)'
        content_match = re.search(intro_pattern, contenus_section, re.DOTALL | re.IGNORECASE)

        if not content_match:
            self.logger.warning(f"Could not extract expectations content from section")
            return {}

        specifics_by_overall = {}
        content_text = content_match.group(1)

        # Clean and normalize the content text
        content_text = re.sub(r'\n+', ' ', content_text)
        content_text = re.sub(r'\s+', ' ', content_text)
        content_text = self.clean_text(content_text)

        self.logger.debug(f"Processing cleaned content:\n{content_text}")

        # Extract expectations with improved pattern
        exp_pattern = rf'{strand_code}(\d+)\.(\d+)\s*([^{strand_code}\d]+?)(?={strand_code}\d+\.\d+|$)'
        matches = list(re.finditer(exp_pattern, content_text))

        self.logger.debug(f"Found {len(matches)} potential expectations")

        for match in matches:
            overall_num = match.group(1)
            specific_num = match.group(2)
            description = self.clean_specific_expectation(match.group(3))

            code = f"{strand_code}{overall_num}.{specific_num}"
            overall_code = f"{strand_code}{overall_num}"

            if description:
                if overall_code not in specifics_by_overall:
                    specifics_by_overall[overall_code] = []

                self.logger.info(f"Found specific expectation {code}: {description[:100]}...")
                specifics_by_overall[overall_code].append({
                    'code': code,
                    'description_fr': description,
                    'description_en': self.get_english_description(code, description)
                })

        if not specifics_by_overall:
            self.logger.warning(f"No specific expectations found in content for strand {strand_code}")
            self.logger.debug("Content searched:\n" + content_text[:500])

        return specifics_by_overall

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
            with db.session.begin():
                # Delete specific expectations first
                specific_subquery = (
                    db.select(OverallExpectation.id)
                    .join(Strand)
                    .join(Course)
                    .where(Course.code == 'ICS3U')
                    .scalar_subquery()
                )
                db.session.execute(
                    db.delete(SpecificExpectation)
                    .where(SpecificExpectation.overall_expectation_id.in_(specific_subquery))
                )

                # Delete overall expectations
                overall_subquery = (
                    db.select(Strand.id)
                    .join(Course)
                    .where(Course.code == 'ICS3U')
                    .scalar_subquery()
                )
                db.session.execute(
                    db.delete(OverallExpectation)
                    .where(OverallExpectation.strand_id.in_(overall_subquery))
                )

                # Delete strands
                strand_subquery = (
                    db.select(Course.id)
                    .where(Course.code == 'ICS3U')
                    .scalar_subquery()
                )
                db.session.execute(
                    db.delete(Strand)
                    .where(Strand.course_id.in_(strand_subquery))
                )

                # Finally delete the course
                db.session.execute(
                    db.delete(Course)
                    .where(Course.code == 'ICS3U')
                )

                self.logger.info("Successfully cleared existing data")

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error clearing existing data: {str(e)}")
            raise