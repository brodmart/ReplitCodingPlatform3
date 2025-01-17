"""
Curriculum Data Importer
Parses and imports Ontario CS curriculum data into the database
"""
import re
from typing import Dict, List, Tuple
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
        title_fr = ""
        title_en = "Introduction to Computer Science"
        desc_fr = ""
        desc_en = ""
        
        for i, line in enumerate(lines):
            if "ICS3U" in line:
                # Extract French title from previous lines
                title_fr = self.clean_text(lines[i-1])
                # Extract French description
                desc_fr = self.clean_text(lines[i+2])
                break
                
        return title_fr, title_en, desc_fr, desc_en

    def parse_strand(self, text: str) -> Dict:
        """Parse strand information"""
        parts = text.split('.')
        if len(parts) < 2:
            return None
            
        code = parts[0].strip()
        title_fr = ' '.join(parts[1:]).strip()
        # For now, we'll keep English titles mapped manually
        title_map = {
            'A': 'Computer Environment',
            'B': 'Programming Concepts',
            'C': 'Software Development',
            'D': 'Computer Science Topics'
        }
        title_en = title_map.get(code, title_fr)
        
        return {
            'code': code,
            'title_fr': title_fr,
            'title_en': title_en
        }

    def parse_expectation(self, text: str) -> Dict:
        """Parse expectation codes and descriptions"""
        # Extract code (e.g., A1.1, B2.3)
        code_match = re.match(r'([A-D][0-9]+(\.[0-9]+)?)', text)
        if not code_match:
            return None
            
        code = code_match.group(1)
        description = text[len(code):].strip()
        
        # For now, English descriptions will be placeholders
        # In a real implementation, these would come from a mapping or translation
        return {
            'code': code,
            'description_fr': description,
            'description_en': f"English translation for: {description}"
        }

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
        
        for line in lines:
            line = line.strip()
            if not line:
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
            elif re.match(r'^[A-D][0-9]+', line):
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
