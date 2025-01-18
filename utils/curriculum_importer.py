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
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        # Normalize apostrophes and quotes
        text = text.replace('''', "'")
        text = text.replace('"', '"').replace('"', '"')
        # Clean up whitespace and line endings
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _extract_sections(self, content: str) -> List[Dict[str, str]]:
        """Extract curriculum sections from content"""
        sections = []
        # Split at ATTENTES markers
        raw_sections = re.split(r'(?:\n|^)\s*ATTENTES\s*:', content)[1:]  # Skip header

        for raw_section in raw_sections:
            # Split section into ATTENTES and CONTENUS parts
            parts = re.split(r"CONTENUS\s+D'APPRENTISSAGE", raw_section, flags=re.IGNORECASE)
            if len(parts) != 2:
                self.logger.warning(f"Invalid section format, found {len(parts)} parts instead of 2")
                continue

            attentes_text, contenus_text = parts

            # Extract strand code from first expectation
            strand_match = re.search(r'([A-Za-z])\d+\.', attentes_text)
            if not strand_match:
                self.logger.warning("Could not find strand code")
                continue

            sections.append({
                'code': strand_match.group(1).upper(),
                'attentes': attentes_text.strip(),
                'contenus': contenus_text.strip()
            })

        return sections

    def _parse_expectations(self, section: Dict[str, str]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract overall and specific expectations from a section"""
        overall_exp = []
        specific_exp = []

        try:
            # Extract overall expectations (e.g., "B1. analyser...")
            for match in re.finditer(r'([A-Za-z]\d+)\s*\.\s*([^\n]+)', section['attentes']):
                code, desc = match.groups()
                if desc.strip():
                    overall_exp.append((code.upper(), desc.strip()))

            # Extract specific expectations (e.g., "B1.1 décrire...")
            current_exp = None
            current_lines = []

            for line in section['contenus'].split('\n'):
                line = line.strip()
                if not line or 'pour satisfaire aux attentes' in line.lower():
                    if current_exp and current_lines:
                        specific_exp.append((current_exp, ' '.join(current_lines)))
                    current_exp = None
                    current_lines = []
                    continue

                # Check for new expectation
                exp_match = re.match(r'([A-Za-z]\d+\.\d+)\s+(.+)', line)
                if exp_match:
                    # Save previous expectation if exists
                    if current_exp and current_lines:
                        specific_exp.append((current_exp, ' '.join(current_lines)))
                    # Start new expectation
                    current_exp = exp_match.group(1).upper()
                    current_lines = [exp_match.group(2)]
                elif current_exp:
                    # Continue previous expectation description
                    current_lines.append(line)

            # Add last expectation if exists
            if current_exp and current_lines:
                specific_exp.append((current_exp, ' '.join(current_lines)))

        except Exception as e:
            self.logger.error(f"Error extracting expectations: {str(e)}")

        return overall_exp, specific_exp

    def import_curriculum(self, content: str) -> None:
        """Import curriculum content into database"""
        try:
            content = self.clean_text(content)

            # Extract and validate sections
            sections = self._extract_sections(content)
            if not sections:
                raise ValueError("No valid sections found in curriculum")

            self.logger.info(f"Found {len(sections)} valid sections")

            # Create database entries
            with db.session.begin():
                # Create course
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11'
                )
                db.session.add(course)
                db.session.flush()

                # Process each section
                for section in sections:
                    # Create strand
                    strand = Strand(
                        course_id=course.id,
                        code=section['code'],
                        title_fr='',  # Will be filled later
                        title_en=''
                    )
                    db.session.add(strand)
                    db.session.flush()

                    # Extract and create expectations
                    overall_exp, specific_exp = self._parse_expectations(section)

                    # Create overall expectations
                    for code, desc in overall_exp:
                        overall = OverallExpectation(
                            strand_id=strand.id,
                            code=code,
                            description_fr=desc,
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.flush()

                        # Create related specific expectations
                        base_code = code + "."
                        related_specs = [
                            (c, d) for c, d in specific_exp 
                            if c.startswith(base_code)
                        ]

                        for spec_code, spec_desc in related_specs:
                            specific = SpecificExpectation(
                                overall_expectation_id=overall.id,
                                code=spec_code,
                                description_fr=spec_desc,
                                description_en=''
                            )
                            db.session.add(specific)

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
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}")
            db.session.rollback()
            raise