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
        # Remove automatic loading of course data during initialization
        # Data will be loaded on-demand when needed

    def parse_expectation(self, line: str) -> Tuple[str, str, str, str]:
        """
        Parse an expectation line into components
        Returns: (strand_code, overall_code, specific_code, description)
        """
        line = line.strip()
        if not line or not any(char.isalpha() for char in line):
            return None, None, None, None

        # Split at first space (format is like "A1.1 description")
        parts = line.split(' ', 1)
        if len(parts) != 2:
            return None, None, None, None

        code = parts[0].strip()
        description = parts[1].strip()

        # Validate and parse code components
        if not code[0].isalpha():
            return None, None, None, None

        strand_code = code[0]  # e.g., 'A' from 'A1.1'

        # Handle overall expectations (e.g., 'A1')
        if len(code) == 2 and code[1].isdigit():
            return strand_code, code, None, description

        # Handle specific expectations (e.g., 'A1.1')
        elif '.' in code:
            overall_code = code.split('.')[0]  # e.g., 'A1' from 'A1.1'
            if len(overall_code) == 2 and overall_code[1].isdigit():
                return strand_code, overall_code, code, description

        return None, None, None, None

    def import_curriculum(self, content: str, course_code: str = "ICS3U") -> None:
        """Import curriculum content into database"""
        try:
            # Initialize tracking dictionaries
            strands = {}  # key: strand_code, value: Strand object
            overall_expectations = {}  # key: overall_code, value: OverallExpectation object

            with db.session.begin():
                # Clear existing course data
                Course.query.filter_by(code=course_code).delete()
                db.session.commit()
                self.logger.debug(f"Cleared existing {course_code} data")

                # Create course
                course = Course(
                    code=course_code,
                    title_fr=f'Introduction au génie informatique, {course_code[-2:]}e année',
                    title_en=f'Introduction to Computer Science, Grade {course_code[-2:]}'
                )
                db.session.add(course)
                db.session.flush()
                self.logger.debug(f"Created course: {course.code}")

                # Process each line
                lines = [line for line in content.split('\n') if line.strip()]
                for line in lines:
                    strand_code, overall_code, specific_code, description = self.parse_expectation(line)
                    if not strand_code:
                        continue

                    # Create strand if needed
                    if strand_code not in strands:
                        strand = Strand(
                            course_id=course.id,
                            code=strand_code,
                            title_fr='',  # Will be filled later if needed
                            title_en=''
                        )
                        db.session.add(strand)
                        db.session.flush()
                        strands[strand_code] = strand
                        self.logger.debug(f"Created strand: {strand_code}")

                    # Handle overall expectation
                    if overall_code and not specific_code:
                        overall = OverallExpectation(
                            strand_id=strands[strand_code].id,
                            code=overall_code,
                            description_fr=description,
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.flush()
                        overall_expectations[overall_code] = overall
                        self.logger.debug(f"Created overall expectation: {overall_code}")

                    # Handle specific expectation
                    elif specific_code:
                        if overall_code not in overall_expectations:
                            self.logger.warning(f"Skipping specific expectation {specific_code} - parent {overall_code} not found")
                            continue

                        specific = SpecificExpectation(
                            overall_expectation_id=overall_expectations[overall_code].id,
                            code=specific_code,
                            description_fr=description,
                            description_en=''
                        )
                        db.session.add(specific)
                        self.logger.debug(f"Created specific expectation: {specific_code}")

                db.session.commit()
                self.logger.info("Curriculum import completed successfully")

        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            db.session.rollback()
            raise

    def clear_existing_data(self, course_code: str = "ICS3U") -> None:
        """Clear existing curriculum data"""
        try:
            with db.session.begin():
                Course.query.filter_by(code=course_code).delete()
            db.session.commit()
        except Exception as e:
            self.logger.error(f"Error clearing data: {str(e)}")
            db.session.rollback()
            raise