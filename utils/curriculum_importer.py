"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
from typing import Dict, List, Tuple, Optional
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from app import db

class CurriculumImporter:
    def __init__(self):
        self.current_course = None
        self.current_strand = None
        self.current_overall = None

    def clean_text(self, text: str) -> str:
        """Clean up text by removing extra spaces and newlines"""
        return ' '.join(text.split()).strip()

    def parse_overall_expectations(self, content: str, strand_code: str) -> List[Dict[str, str]]:
        """Parse overall expectations (A1, A2, A3) from ATTENTES section"""
        # Find the section between ATTENTES and CONTENUS D'APPRENTISSAGE
        section_pattern = r'ATTENTES\s*(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=CONTENUS\s+D\'APPRENTISSAGE)'
        section_match = re.search(section_pattern, content, re.DOTALL | re.MULTILINE)

        if not section_match:
            return []

        expectations = []
        section = section_match.group(1)

        # Look for expectations like A1., A2., A3.
        exp_pattern = rf'{strand_code}([0-9])\s*\.\s*([^\.]+)\.'
        for match in re.finditer(exp_pattern, section):
            number = match.group(1)
            description = self.clean_text(match.group(2))

            expectations.append({
                'code': f'{strand_code}{number}',
                'description_fr': description,
                'description_en': self.get_english_description(f'{strand_code}{number}', description)
            })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str, overall_id: int) -> List[Dict[str, str]]:
        """Parse specific expectations (A1.1, A1.2, etc.) from CONTENUS D'APPRENTISSAGE section"""
        # Find the CONTENUS D'APPRENTISSAGE section
        section_pattern = r'CONTENUS\s+D\'APPRENTISSAGE(.*?)(?=(?:[A-D]\.|ATTENTES|$))'
        section_match = re.search(section_pattern, content, re.DOTALL | re.MULTILINE)

        if not section_match:
            return []

        expectations = []
        section = section_match.group(1)

        # Look for specific expectations like A1.1, A1.2, etc.
        exp_pattern = rf'{strand_code}\d\.(\d)\s+([^\.]+)\.'
        for match in re.finditer(exp_pattern, section):
            sub_number = match.group(1)
            description = self.clean_text(match.group(2))

            code = f'{strand_code}1.{sub_number}'  # Using strand_code1 as we're focusing on section A
            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': self.get_english_description(code, description),
                'overall_expectation_id': overall_id
            })

        return expectations

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate English descriptions based on code"""
        # Overall expectations mapping for section A
        overall_map = {
            'A1': 'explain the operation of a personal computer using appropriate terminology.',
            'A2': 'apply file management techniques.',
            'A3': 'use appropriate tools to develop programs.'
        }

        # Specific expectations mapping for section A
        specific_map = {
            'A1.1': 'explain the functions of internal hardware components.',
            'A1.2': 'explain the functions of commonly used external peripherals.',
            'A1.3': 'compare computer hardware performance using objective measurements.',
            'A1.4': 'explain the relationship between programming languages and computer components.',
            'A2.1': 'organize program files using operating system functions.',
            'A2.2': 'implement systematic file backup procedures.',
            'A2.3': 'describe various types of malware and corresponding security measures.',
            'A2.4': 'use local network services for file management during program development.',
            'A3.1': 'explain the functions of operating systems and application software.',
            'A3.2': 'explain the characteristics and advantages of development environments.',
            'A3.3': 'use compiler or interpreter functions.',
            'A3.4': 'use available help resources to develop programs.'
        }

        if '.' not in code:  # Overall expectation
            return overall_map.get(code, f"English translation needed for: {desc_fr}")
        else:  # Specific expectation
            return specific_map.get(code, f"English translation needed for: {desc_fr}")

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        # First clear existing data for strand A
        Course.query.filter_by(code='ICS3U').delete()
        db.session.commit()

        # Create the course
        course = Course(
            code='ICS3U',
            title_fr="Introduction au génie informatique, 11e année",
            title_en="Introduction to Computer Science, Grade 11",
            description_fr="",  # We'll add this later
            description_en="This course introduces students to computer science concepts and practices.",
            prerequisite_fr="Aucun",
            prerequisite_en="None"
        )
        db.session.add(course)
        db.session.flush()

        # Create Strand A
        strand = Strand(
            course_id=course.id,
            code='A',
            title_fr='Environnement informatique de travail',
            title_en='Computing Environment'
        )
        db.session.add(strand)
        db.session.flush()

        # Parse and add overall expectations for Strand A
        overall_expectations = self.parse_overall_expectations(content, 'A')
        for exp_data in overall_expectations:
            overall = OverallExpectation(
                strand_id=strand.id,
                **exp_data
            )
            db.session.add(overall)
            db.session.flush()  # Flush to get the ID for specific expectations

            # Parse and add specific expectations for this overall expectation
            specific_expectations = self.parse_specific_expectations(content, 'A', overall.id)
            for spec_data in specific_expectations:
                specific = SpecificExpectation(
                    overall_expectation_id=overall.id,
                    **spec_data
                )
                db.session.add(specific)

        db.session.commit()