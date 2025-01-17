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
        """Parse overall expectations from ATTENTES section"""
        # Find the section between ATTENTES and CONTENUS D'APPRENTISSAGE or next strand
        section_pattern = r'ATTENTES\s*(?:À la fin du cours, l\'élève doit pouvoir :)?\s*(.*?)(?=(?:CONTENUS D\'APPRENTISSAGE|[A-D]\.\s+[A-Za-z]))'
        section_match = re.search(section_pattern, content, re.DOTALL | re.MULTILINE)

        if not section_match:
            return []

        expectations = []
        section = section_match.group(1)

        # Look for expectations in format A1., A2., etc. or numbered list
        exp_pattern = rf'{strand_code}([0-9])[\.|\)]?\s*([^\.]+)(?:\.|$)'
        for match in re.finditer(exp_pattern, section, re.MULTILINE):
            number = match.group(1)
            description = self.clean_text(match.group(2))

            expectations.append({
                'code': f'{strand_code}{number}',
                'description_fr': description,
                'description_en': self.get_english_description(f'{strand_code}{number}', description)
            })

        return expectations

    def parse_specific_expectations(self, content: str, strand_code: str, overall_id: int) -> List[Dict[str, str]]:
        """Parse specific expectations from CONTENUS D'APPRENTISSAGE section"""
        # Find the CONTENUS D'APPRENTISSAGE section until next section or strand
        section_pattern = r'CONTENUS D\'APPRENTISSAGE\s*(.*?)(?=(?:ATTENTES|[A-D]\.\s+[A-Za-z]|$))'
        section_match = re.search(section_pattern, content, re.DOTALL | re.MULTILINE)

        if not section_match:
            return []

        expectations = []
        section = section_match.group(1)

        # Look for specific expectations like A1.1, A1.2, etc.
        exp_pattern = rf'{strand_code}\d\.(\d+)\s*([^\.]+)(?:\.|$)'
        for match in re.finditer(exp_pattern, section, re.MULTILINE):
            sub_number = match.group(1)
            description = self.clean_text(match.group(2))

            code = f'{strand_code}1.{sub_number}'  # Using numbering convention from curriculum
            expectations.append({
                'code': code,
                'description_fr': description,
                'description_en': self.get_english_description(code, description),
                'overall_expectation_id': overall_id
            })

        return expectations

    def get_strand_sections(self, content: str) -> List[Tuple[str, str, str]]:
        """Extract individual strand sections from the curriculum content"""
        # Look for strand headers like "A. COMPUTING ENVIRONMENT" or "B. SOFTWARE DEVELOPMENT"
        strand_pattern = r'([A-D])\.\s+([^\n]+)\n(.*?)(?=[A-D]\.\s+|$)'
        matches = re.finditer(strand_pattern, content, re.DOTALL)
        return [(m.group(1), m.group(2), m.group(3)) for m in matches]

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate English descriptions based on code"""
        # This is a placeholder - in production, this should be replaced with actual translations
        # For now, returning a standard placeholder
        return f"English translation needed for: {desc_fr}"

    def clear_existing_data(self):
        """Clear existing curriculum data in the correct order to respect foreign key constraints"""
        course = Course.query.filter_by(code='ICS3U').first()
        if course:
            # First delete all specific expectations related to this course
            strands = Strand.query.filter_by(course_id=course.id).all()
            for strand in strands:
                overall_expectations = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                for overall in overall_expectations:
                    SpecificExpectation.query.filter_by(overall_expectation_id=overall.id).delete()
                # Then delete overall expectations
                OverallExpectation.query.filter_by(strand_id=strand.id).delete()
            # Then delete strands
            Strand.query.filter_by(course_id=course.id).delete()
            # Finally delete the course
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        # First clear existing data
        self.clear_existing_data()

        # Create the course
        course = Course(
            code='ICS3U',
            title_fr="Introduction au génie informatique, 11e année",
            title_en="Introduction to Computer Science, Grade 11",
            description_fr="Ce cours initie l'élève aux concepts fondamentaux de la programmation.",
            description_en="This course introduces students to computer science concepts and practices.",
            prerequisite_fr="Aucun",
            prerequisite_en="None"
        )
        db.session.add(course)
        db.session.flush()

        # Process each strand section
        strand_sections = self.get_strand_sections(content)
        for strand_code, title_fr, section_content in strand_sections:
            # Create Strand
            strand = Strand(
                course_id=course.id,
                code=strand_code,
                title_fr=title_fr,
                title_en=f"English translation needed for: {title_fr}"
            )
            db.session.add(strand)
            db.session.flush()

            # Parse and add overall expectations for this strand
            overall_expectations = self.parse_overall_expectations(section_content, strand_code)
            for exp_data in overall_expectations:
                overall = OverallExpectation(
                    strand_id=strand.id,
                    **exp_data
                )
                db.session.add(overall)
                db.session.flush()

                # Parse and add specific expectations for this overall expectation
                specific_expectations = self.parse_specific_expectations(section_content, strand_code, overall.id)
                for spec_data in specific_expectations:
                    specific = SpecificExpectation(
                        overall_expectation_id=overall.id,
                        **spec_data
                    )
                    db.session.add(specific)

        db.session.commit()