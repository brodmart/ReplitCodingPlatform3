"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
import logging
from typing import Dict, List, Tuple
from app import db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

class CurriculumImporter:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def _extract_sections(self, content: str) -> List[Dict[str, str]]:
        """Extract curriculum sections from content"""
        sections = []

        # Find all section boundaries
        section_markers = list(re.finditer(r'(?:^|\n)\s*ATTENTES\s*:', content, re.MULTILINE))

        for i, match in enumerate(section_markers):
            start_pos = match.start()
            end_pos = section_markers[i + 1].start() if i + 1 < len(section_markers) else len(content)
            section_text = content[start_pos:end_pos].strip()

            # Split into ATTENTES and CONTENUS using flexible pattern
            parts = re.split(r'CONTENUS', section_text, flags=re.IGNORECASE)

            if len(parts) != 2:
                self.logger.warning(f"Section {i+1} invalid format - found {len(parts)} parts instead of 2")
                self.logger.debug(f"Section content preview:\n{section_text[:200]}")
                continue

            attentes_text, contenus_text = parts[0], parts[1]

            # Clean up the texts
            attentes_text = self._clean_section_text(attentes_text)
            contenus_text = self._clean_section_text(contenus_text)

            # Extract strand code from first expectation
            strand_match = re.search(r'([A-Za-z])\d+\.', attentes_text)
            if not strand_match:
                self.logger.warning(f"Could not find strand code in section {i+1}")
                continue

            sections.append({
                'code': strand_match.group(1).upper(),
                'attentes': attentes_text,
                'contenus': contenus_text
            })

        return sections

    def _clean_section_text(self, text: str) -> str:
        """Clean up section text content"""
        # Skip 'pour satisfaire aux attentes' line
        text = re.sub(r'^.*?Pour satisfaire aux attentes.*?\n', '', text, flags=re.MULTILINE | re.IGNORECASE)

        # Remove any "D'APPRENTISSAGE" header text
        text = re.sub(r"D[''']APPRENTISSAGE.*?\n", '', text, flags=re.MULTILINE | re.IGNORECASE)

        # Join hyphenated line breaks
        text = re.sub(r'-\s*\n\s*', '', text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)

        return text.strip()

    def _parse_expectations(self, section: Dict[str, str]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Extract overall and specific expectations from a section"""
        overall_exp = []
        specific_exp = []

        try:
            # Extract overall expectations (e.g., "B1. analyser...")
            for match in re.finditer(r'([A-Za-z]\d+)\s*\.\s*([^\n]+)', section['attentes']):
                code, desc = match.groups()
                overall_exp.append((code.upper(), desc.strip()))

            # Process specific expectations
            current_code = None
            current_text = []

            for line in section['contenus'].split('\n'):
                line = line.strip()

                # Skip empty lines and section titles
                if not line or line.lower().startswith(('fonctionnement', 'gestion', 'outils', 'syntaxe', 'assurance')):
                    if current_code and current_text:
                        specific_exp.append((current_code, ' '.join(current_text)))
                        current_code = None
                        current_text = []
                    continue

                # Try to match new expectation
                exp_match = re.match(r'([A-Za-z]\d+\.\d+)\s+(.+)', line)
                if exp_match:
                    # Save previous if exists
                    if current_code and current_text:
                        specific_exp.append((current_code, ' '.join(current_text)))

                    # Start new expectation
                    current_code = exp_match.group(1).upper()
                    current_text = [exp_match.group(2)]
                elif current_code:
                    current_text.append(line)

            # Save final expectation if exists
            if current_code and current_text:
                specific_exp.append((current_code, ' '.join(current_text)))

        except Exception as e:
            self.logger.error(f"Error parsing expectations: {str(e)}")
            raise

        return overall_exp, specific_exp

    def import_curriculum(self, content: str) -> None:
        """Import curriculum content into database"""
        try:
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
                    self.logger.debug(f"Processing section {section['code']}")

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
                    self.logger.debug(f"Found {len(overall_exp)} overall and {len(specific_exp)} specific expectations")

                    # Create expectations
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
            with db.session.begin():
                Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}")
            db.session.rollback()
            raise