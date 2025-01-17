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
        return ' '.join(text.split())

    def parse_course_info(self, lines: List[str]) -> Tuple[str, str, str, str]:
        """Parse course title and description in both languages"""
        title_fr = "Introduction au génie informatique, 11e année"
        title_en = "Introduction to Computer Science, Grade 11"
        desc_fr = "Ce cours initie l'élève aux concepts fondamentaux de l'informatique et aux techniques de développement de logiciels."
        desc_en = "This course introduces students to computer science concepts and software development practices."

        # Find more detailed description in the content
        for i, line in enumerate(lines):
            if "ICS3U" in line and i < len(lines) - 3:
                # Extract French description from following lines
                desc_fr = ' '.join([
                    self.clean_text(lines[i+2]),
                    self.clean_text(lines[i+3])
                ])
                break

        return title_fr, title_en, desc_fr, desc_en

    def parse_strand(self, text: str) -> Optional[Dict[str, str]]:
        """Parse strand information"""
        parts = text.strip().split('.')
        if len(parts) < 2 or not parts[0].strip():
            return None

        code = parts[0].strip()
        # Extract French title after the code
        title_fr = self.clean_text('.'.join(parts[1:]))

        # Map to English titles
        title_map = {
            'A': ('Environnement informatique de travail', 'Computer Environment'),
            'B': ('Techniques de programmation', 'Programming Techniques'),
            'C': ('Développement de logiciels', 'Software Development'),
            'D': ('Enjeux sociétaux et perspectives professionnelles', 'Computer Science Topics and Career Exploration')
        }

        title_fr, title_en = title_map.get(code, (title_fr, title_fr))

        return {
            'code': code,
            'title_fr': title_fr,
            'title_en': title_en
        }

    def parse_expectation(self, text: str) -> Optional[Dict[str, str]]:
        """Parse expectation codes and descriptions"""
        # Extract code (e.g., A1.1, B2.3)
        code_match = re.match(r'([A-D][0-9]+(\.[0-9]+)?)', text)
        if not code_match:
            return None

        code = code_match.group(1)
        description_fr = text[len(code):].strip()

        # Map to English descriptions based on the French content
        description_en = self.get_english_description(code, description_fr)

        return {
            'code': code,
            'description_fr': description_fr,
            'description_en': description_en
        }

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate English description based on code and French description"""
        # This is a placeholder implementation
        # In a production environment, this would use proper translations
        english_map = {
            'A1': 'explain the operation of a personal computer using appropriate terminology.',
            'A2': 'apply file management techniques.',
            'A3': 'use appropriate tools to develop programs.',
            'B1': 'apply the main rules of syntax and semantics of a programming language.',
            'B2': 'explain elementary algorithms and data structures.',
            'B3': 'apply software quality assurance techniques.',
            'C1': 'apply software development techniques.',
            'C2': 'design algorithms that respond to given problems.',
            'C3': 'develop programs that respond to given problems.',
            'D1': 'analyze measures favorable for the environment and public health concerning the use of computer equipment.',
            'D2': 'analyze various career and professional training opportunities in computer science.'
        }

        # For overall expectations, use the map
        if len(code.split('.')) == 1:
            if code in english_map:
                return english_map[code]

        # For specific expectations, create a meaningful English translation
        return f"English translation of: {desc_fr}"

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        lines = content.split('\n')

        # Create course
        title_fr, title_en, desc_fr, desc_en = self.parse_course_info(lines)
        course = Course(
            code='ICS3U',
            title_fr=title_fr,
            title_en=title_en,
            description_fr=desc_fr,
            description_en=desc_en
        )
        db.session.add(course)
        db.session.flush()

        current_strand = None
        current_overall = None
        in_expectation_section = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for start of expectations section
            if "ATTENTES" in line:
                in_expectation_section = True
                continue

            if not in_expectation_section:
                continue

            # Parse strand
            if re.match(r'^[A-D]\.', line):
                strand_data = self.parse_strand(line)
                if strand_data:
                    current_strand = Strand(
                        course_id=course.id,
                        **strand_data
                    )
                    db.session.add(current_strand)
                    db.session.flush()

            # Parse overall expectation
            elif re.match(r'^[A-D][0-9]+', line) and not re.match(r'^[A-D][0-9]+\.[0-9]+', line):
                exp_data = self.parse_expectation(line)
                if exp_data and current_strand:
                    current_overall = OverallExpectation(
                        strand_id=current_strand.id,
                        **exp_data
                    )
                    db.session.add(current_overall)
                    db.session.flush()

            # Parse specific expectation
            elif re.match(r'^[A-D][0-9]+\.[0-9]+', line):
                exp_data = self.parse_expectation(line)
                if exp_data and current_overall:
                    specific = SpecificExpectation(
                        overall_expectation_id=current_overall.id,
                        **exp_data
                    )
                    db.session.add(specific)

        db.session.commit()