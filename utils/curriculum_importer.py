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

    def parse_course_info(self, content: str) -> Tuple[str, str, str, str]:
        """Parse course title and description in both languages"""
        # Extract French title
        title_pattern = r'Introduction au génie\s+informatique,\s*11e année(?:\s+cours préuniversitaire)?\s+ICS3U'
        title_match = re.search(title_pattern, content, re.MULTILINE)
        title_fr = "Introduction au génie informatique, 11e année"
        if title_match:
            title_fr = re.sub(r'\s+ICS3U$', '', title_match.group(0).strip())

        title_en = "Introduction to Computer Science, Grade 11"

        # Extract French description - looking for the description that starts after the title
        desc_pattern = r'Ce cours initie l\'élève[^\.]+\.[^\.]+\.'
        desc_match = re.search(desc_pattern, content)
        desc_fr = self.clean_text(desc_match.group(0)) if desc_match else ""

        # English description
        desc_en = (
            "This course introduces students to computer science concepts and practices. "
            "Through hands-on projects, students will develop software skills, explore "
            "algorithm design, and understand the fundamentals of computer science."
        )

        return title_fr, title_en, desc_fr, desc_en

    def parse_strand(self, text: str) -> Optional[Dict[str, str]]:
        """Parse strand information from text"""
        # Look for strand headers
        strand_pattern = r'^([A-D])\s*\.\s*([^0-9]+)'
        match = re.match(strand_pattern, text, re.MULTILINE)
        if not match:
            return None

        code = match.group(1)
        if code not in ['A', 'B', 'C', 'D']:
            return None

        # Define strand mappings
        strand_map = {
            'A': ('Environnement informatique de travail', 'Computing Environment'),
            'B': ('Techniques de programmation', 'Programming Techniques'),
            'C': ('Développement de logiciels', 'Software Development'),
            'D': ('Enjeux sociétaux et perspectives professionnelles', 'Career and Societal Impact')
        }

        title_fr, title_en = strand_map[code]
        return {
            'code': code,
            'title_fr': title_fr,
            'title_en': title_en
        }

    def parse_expectation(self, text: str) -> Optional[Dict[str, str]]:
        """Parse expectation information from text"""
        # Match expectation patterns (A1, B2.1, etc.)
        exp_pattern = r'^([A-D][0-9]+(?:\.[0-9]+)?)\s+(.+?)(?:\s*\(p\. ex\.,|\.|$)'
        match = re.match(exp_pattern, text)
        if not match:
            return None

        code = match.group(1)
        description_fr = self.clean_text(match.group(2))

        # Get corresponding English description
        description_en = self.get_english_description(code, description_fr)

        return {
            'code': code,
            'description_fr': description_fr,
            'description_en': description_en
        }

    def get_english_description(self, code: str, desc_fr: str) -> str:
        """Generate English descriptions based on code and French text"""
        # Overall expectations mapping
        overall_map = {
            'A1': 'explain the operation of a personal computer using appropriate terminology.',
            'A2': 'apply file management techniques.',
            'A3': 'use appropriate tools to develop programs.',
            'B1': 'apply the main rules of syntax and semantics of a programming language.',
            'B2': 'explain elementary algorithms and data structures.',
            'B3': 'apply software quality assurance techniques.',
            'C1': 'apply software development techniques.',
            'C2': 'design algorithms that respond to given problems.',
            'C3': 'develop programs that respond to given problems.',
            'D1': 'analyze environmental and public health measures related to computer hardware use.',
            'D2': 'analyze various career and professional training opportunities in computer science.'
        }

        # Specific expectations mapping
        specific_map = {
            'A1.1': 'explain the functions of internal hardware components (e.g., motherboard, processor, RAM, video card, sound card).',
            'A1.2': 'explain the functions of commonly used external peripherals (e.g., mouse, keyboard, monitor, printer, digital camera, USB key).',
            'A1.3': 'compare computer hardware performance using objective measurements.',
            'A1.4': 'explain the relationship between programming languages and computer components.',
            'A2.1': 'organize program files using operating system functions.',
            'A2.2': 'implement systematic file backup procedures.',
            'A2.3': 'describe various types of malware and corresponding security measures.',
            'A2.4': 'use local network services for file management during program development.',
            'A3.1': 'compare the functions of operating systems and application software.',
            'A3.2': 'explain the characteristics and advantages of development environments.',
            'A3.3': 'use compiler or interpreter functions.',
            'A3.4': 'use available help resources to develop programs.',
            'B1.1': 'describe primitive data types defined by the programming language.',
            'B1.2': 'describe internal representation of various data types.',
            'B1.3': 'define literal values, constants, and variables.',
            'B1.4': 'define variable scope and lifetime concepts.',
            'B1.5': 'describe different types of functions.',
            'B1.6': 'apply fundamental syntax rules.',
            'B2.1': 'define characteristics of one-dimensional arrays.',
            'B2.2': 'explain algorithms for reading and modifying array elements.',
            'B2.3': 'explain control structures functionality.',
            'B2.4': 'explain algorithms for processing user input and displaying output.',
            'C1.1': 'describe problems in terms of input data, data processing, and output data.',
            'C1.2': 'use different approaches to solve problems.',
            'C1.3': 'document software development activities and deliverables.',
            'C2.1': 'design algorithms for mathematical problems.',
            'C2.2': 'design algorithms for data processing.',
            'C2.3': 'design nested control structures.',
            'C2.4': 'design algorithms handling exceptions.',
            'C3.1': 'design functions for given requirements.',
            'C3.2': 'model programming problems using various techniques.',
            'C3.3': 'apply modularization principles.',
            'C3.4': 'design user-friendly interfaces.',
            'D1.1': 'explain the impact of computer industry on environment and public health.',
            'D1.2': 'evaluate initiatives promoting sustainable management and environmental protection.',
            'D1.3': 'determine strategies to reduce computer system consumption.',
            'D1.4': 'describe prevention methods for computer-related health issues.',
            'D2.1': 'compare possible career choices in computer science.',
            'D2.2': 'identify available training programs in computer science.',
            'D2.3': 'identify opportunities to gain computer science experience.',
            'D2.4': 'describe support services for non-traditional careers.'
        }

        if '.' not in code:  # Overall expectation
            return overall_map.get(code, f"English translation needed for: {desc_fr}")
        else:  # Specific expectation
            return specific_map.get(code, f"English translation needed for: {desc_fr}")

    def import_curriculum(self, content: str):
        """Import curriculum content into database"""
        # Create course
        title_fr, title_en, desc_fr, desc_en = self.parse_course_info(content)
        course = Course(
            code='ICS3U',
            title_fr=title_fr,
            title_en=title_en,
            description_fr=desc_fr,
            description_en=desc_en,
            prerequisite_fr="Aucun",
            prerequisite_en="None"
        )
        db.session.add(course)
        db.session.flush()

        lines = content.split('\n')
        current_strand = None
        current_overall = None
        in_expectations = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for expectations sections
            if re.search(r'ATTENTES|CONTENUS\s+D[\'"]APPRENTISSAGE', line, re.IGNORECASE):
                in_expectations = True
                continue

            if not in_expectations:
                continue

            # Parse strand sections
            if re.match(r'^[A-D]\s*\.', line):
                strand_data = self.parse_strand(line)
                if strand_data:
                    current_strand = Strand(
                        course_id=course.id,
                        **strand_data
                    )
                    db.session.add(current_strand)
                    db.session.flush()
                    current_overall = None  # Reset current overall expectation

            # Parse overall expectations
            elif current_strand and re.match(r'^[A-D][0-9]+(?!\.[0-9])\s', line):
                exp_data = self.parse_expectation(line)
                if exp_data:
                    current_overall = OverallExpectation(
                        strand_id=current_strand.id,
                        **exp_data
                    )
                    db.session.add(current_overall)
                    db.session.flush()

            # Parse specific expectations
            elif current_overall and re.match(r'^[A-D][0-9]+\.[0-9]+\s', line):
                exp_data = self.parse_expectation(line)
                if exp_data:
                    specific = SpecificExpectation(
                        overall_expectation_id=current_overall.id,
                        **exp_data
                    )
                    db.session.add(specific)

        db.session.commit()