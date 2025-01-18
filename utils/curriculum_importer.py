"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from app import db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Updated patterns to better match the French curriculum format
        self._section_pattern = r'(?:^|\n)\s*([^:\n]+?)(?=\s*ATTENTES\s*:)'
        self._attentes_pattern = r'ATTENTES\s*:\s*(.*?)(?=\s*CONTENUS\s+D\'APPRENTISSAGE|$)'
        self._contenus_pattern = r'CONTENUS\s+D\'APPRENTISSAGE(?:\s*Pour[^:]*:)?\s*(.*?)(?=\s*(?:ATTENTES|\Z))'
        self._overall_exp_pattern = r'([A-D]\d+)\s*\.\s*([^\n]+)'
        self._specific_exp_pattern = r'([A-D]\d+\.\d+)\s*([^\n]+)'
        self._strand_code_pattern = r'([A-D])'

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""

        # Remove unwanted characters and normalize spacing
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'Pour satisfaire aux attentes,\s+l\'élève doit pouvoir\s*:', '', text)

        return text.strip()

    def _validate_content_structure(self, content: str) -> bool:
        """Pre-validate content structure before parsing"""
        try:
            self.logger.debug("Starting content validation...")

            # Find all ATTENTES and CONTENUS sections
            attentes_matches = re.findall(r'ATTENTES\s*:', content)
            contenus_matches = re.findall(r'CONTENUS\s+D\'APPRENTISSAGE', content)

            self.logger.debug(f"Found {len(attentes_matches)} ATTENTES sections")
            self.logger.debug(f"Found {len(contenus_matches)} CONTENUS sections")

            if not attentes_matches or not contenus_matches:
                self.logger.error(f"Missing required sections: ATTENTES ({len(attentes_matches)}) or CONTENUS ({len(contenus_matches)})")
                return False

            # Verify expectations format
            overall_exp = re.findall(r'[A-D]\d+\.', content)
            specific_exp = re.findall(r'[A-D]\d+\.\d+', content)

            self.logger.debug(f"Found {len(overall_exp)} overall expectations")
            self.logger.debug(f"Found {len(specific_exp)} specific expectations")

            if not overall_exp or not specific_exp:
                self.logger.error("No valid expectations found")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return False

    def _extract_sections(self, content: str) -> List[Dict]:
        """Extract curriculum sections"""
        sections = []
        try:
            # Split content into major sections
            major_sections = re.split(r'\n\s*ATTENTES\s*:', content)[1:]
            self.logger.debug(f"Found {len(major_sections)} major sections to process")

            for section_content in major_sections:
                # Extract section title from previous content
                section_match = re.search(self._section_pattern, content, re.MULTILINE)
                if not section_match:
                    self.logger.warning("Could not find section title, skipping...")
                    continue

                title = self.clean_text(section_match.group(1))
                self.logger.debug(f"Processing section: {title}")

                # Extract ATTENTES content
                attentes_match = re.search(self._attentes_pattern, section_content, re.DOTALL)
                if not attentes_match:
                    self.logger.warning(f"No ATTENTES found for section: {title}")
                    continue

                attentes = self.clean_text(attentes_match.group(1))

                # Extract CONTENUS content
                contenus_match = re.search(self._contenus_pattern, section_content, re.DOTALL)
                if not contenus_match:
                    self.logger.warning(f"No CONTENUS found for section: {title}")
                    continue

                contenus = self.clean_text(contenus_match.group(1))

                # Extract strand code from first expectation
                strand_code = None
                first_exp = re.search(self._overall_exp_pattern, attentes)
                if first_exp:
                    code_match = re.match(self._strand_code_pattern, first_exp.group(1))
                    if code_match:
                        strand_code = code_match.group(1)

                if not strand_code:
                    self.logger.warning(f"Could not determine strand code for section: {title}")
                    continue

                self.logger.debug(f"Successfully extracted section {strand_code}")
                sections.append({
                    'title': title,
                    'code': strand_code,
                    'attentes': attentes,
                    'contenus': contenus
                })

            return sections

        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            raise

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        self.logger.info("Starting curriculum import...")

        try:
            # Clean and validate content
            content = self.clean_text(content)
            if not self._validate_content_structure(content):
                raise ValueError("Invalid curriculum structure")

            # Extract sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No valid sections found")

            self.logger.info(f"Found {len(sections)} valid sections to import")

            # Start database transaction
            with db.session.begin_nested():
                # Create course
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11'
                )
                db.session.add(course)
                db.session.flush()

                # Process each section
                for section_data in sections:
                    # Create strand
                    strand = Strand(
                        course_id=course.id,
                        code=section_data['code'],
                        title_fr=section_data['title'],
                        title_en=''  # Will be added later
                    )
                    db.session.add(strand)
                    db.session.flush()

                    # Extract and create overall expectations
                    overall_exp_count = 0
                    specific_exp_count = 0

                    for match in re.finditer(self._overall_exp_pattern, section_data['attentes'], re.MULTILINE):
                        code, desc = match.groups()
                        overall = OverallExpectation(
                            strand_id=strand.id,
                            code=code,
                            description_fr=desc.strip(),
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.flush()
                        overall_exp_count += 1

                        # Extract and create specific expectations
                        base_code = f"{code}\\."
                        spec_pattern = f"{base_code}\\d+\\s*([^\\n]+)"
                        spec_matches = list(re.finditer(spec_pattern, section_data['contenus'], re.MULTILINE))

                        for idx, spec_match in enumerate(spec_matches, 1):
                            desc = spec_match.group(1)
                            specific = SpecificExpectation(
                                overall_expectation_id=overall.id,
                                code=f"{code}.{idx}",
                                description_fr=desc.strip(),
                                description_en=''
                            )
                            db.session.add(specific)
                            specific_exp_count += 1

                    self.logger.info(
                        f"Processed strand {strand.code}: "
                        f"{overall_exp_count} overall, {specific_exp_count} specific expectations"
                    )

                db.session.commit()
                self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            db.session.rollback()
            raise

    def clear_existing_data(self) -> None:
        """Clear existing curriculum data"""
        try:
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
            self.logger.info("Cleared existing ICS3U data")
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}")
            db.session.rollback()
            raise

    def _verify_imported_data(self, course_id: int) -> None:
        """Verify imported data integrity"""
        try:
            # Verify course
            course = Course.query.get(course_id)
            if not course:
                raise ValueError("Course not found after import")

            # Verify strands
            strands = Strand.query.filter_by(course_id=course_id).all()
            if not strands:
                raise ValueError("No strands found after import")

            # Verify expectations
            for strand in strands:
                overall_exps = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                if not overall_exps:
                    raise ValueError(f"No overall expectations found for strand {strand.code}")

                for overall_exp in overall_exps:
                    specific_exps = SpecificExpectation.query.filter_by(
                        overall_expectation_id=overall_exp.id
                    ).all()
                    if not specific_exps:
                        raise ValueError(
                            f"No specific expectations found for overall expectation {overall_exp.code}"
                        )

            self.logger.info("Data verification completed successfully")
        except Exception as e:
            self.logger.error(f"Data verification failed: {str(e)}")
            raise

    def import_first_section(self, content: str) -> bool:
        """Import only the first section for testing"""
        self.logger.info("Starting first section import...")

        try:
            # Preprocess content
            content = self.clean_text(content)
            self.logger.debug(f"Preprocessed content (first 1000 chars):\n{content[:1000]}")

            # Find first section
            section_match = re.search(r'([A-D])\s*\.\s*(.*?)(?=\s*ATTENTES)', content, re.DOTALL)
            if not section_match:
                self.logger.error("No section found")
                self.logger.debug(f"Content preview: {content[:500]}")
                raise ValueError("No section found in content")

            code = section_match.group(1)
            title = self.clean_text(section_match.group(2))
            self.logger.info(f"Found first section: {code}. {title}")

            # Extract section content
            section_content = content[:content.find('B.')] if 'B.' in content else content
            self.logger.debug(f"Section content preview:\n{section_content[:200]}")

            # Extract expectations
            attentes_match = re.search(self._attentes_pattern, section_content, re.DOTALL)
            contenus_match = re.search(self._contenus_pattern, section_content, re.DOTALL)

            if not attentes_match or not contenus_match:
                self.logger.error("Failed to extract ATTENTES or CONTENUS")
                self.logger.debug(f"Section content: {section_content}")
                raise ValueError("Missing ATTENTES or CONTENUS in section")

            attentes = self.clean_text(attentes_match.group(1))
            contenus = self.clean_text(contenus_match.group(1))

            self.logger.info("Successfully extracted first section content")
            self.logger.debug(f"ATTENTES preview: {attentes[:200]}")
            self.logger.debug(f"CONTENUS preview: {contenus[:200]}")

            # Create course and strand
            with db.session.begin_nested():
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11'
                )
                db.session.add(course)
                db.session.flush()

                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_fr=title
                )
                db.session.add(strand)
                db.session.commit()

            self.logger.info(f"Successfully imported first section: {code}")
            return True

        except Exception as e:
            self.logger.error(f"Error importing first section: {str(e)}")
            db.session.rollback()
            raise