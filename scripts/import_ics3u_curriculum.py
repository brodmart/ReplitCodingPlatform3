"""
Script to import ICS3U curriculum data from the provided French curriculum document
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def get_strand_titles():
    """Get bilingual titles for curriculum strands"""
    return {
        'A': ('Computing Environment and Tools', 'Environnement informatique de travail'),
        'B': ('Programming Concepts', 'Concepts de programmation'),
        'C': ('Software Development', 'Développement de logiciels'),
        'D': ('Computing and Society', 'Enjeux sociétaux et perspectives professionnelles')
    }

def get_overall_descriptions():
    """Get bilingual descriptions for overall expectations"""
    return {
        'A1': ('Computer Hardware Components', 'Composants matériels de l\'ordinateur'),
        'A2': ('Operating System Functions', 'Fonctions du système d\'exploitation'),
        'A3': ('Development Tools', 'Outils de développement'),
        'B1': ('Programming Fundamentals', 'Concepts fondamentaux de la programmation'),
        'B2': ('Data Structures and Control', 'Structures de données et contrôle'),
        'B3': ('Testing and Debugging', 'Test et débogage'),
        'C1': ('Software Development Process', 'Processus de développement de logiciels'),
        'C2': ('Algorithm Design', 'Conception d\'algorithmes'),
        'C3': ('Program Design', 'Conception de programmes'),
        'D1': ('Environmental Impact', 'Impact environnemental'),
        'D2': ('Career Opportunities', 'Perspectives de carrière')
    }

def main():
    """Import ICS3U curriculum data"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        # Get reference data
        strand_titles = get_strand_titles()
        overall_descriptions = get_overall_descriptions()

        with app.app_context():
            # First verify if course exists
            course = Course.query.filter_by(code='ICS3U').first()
            if not course:
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11',
                    description_fr='Ce cours initie les élèves aux concepts et aux pratiques de l\'informatique.',
                    description_en='This course introduces students to computer science concepts and practices.'
                )
                db.session.add(course)
                db.session.commit()
                logger.info("Created new ICS3U course")

            # Update strand titles
            for strand in course.strands:
                if strand.code.upper() in strand_titles:
                    title_en, title_fr = strand_titles[strand.code.upper()]
                    strand.title_en = title_en
                    strand.title_fr = title_fr
                    logger.info(f"Updated strand {strand.code} titles")

            # Update overall expectation descriptions
            for strand in course.strands:
                for overall in strand.overall_expectations:
                    if overall.code.upper() in overall_descriptions:
                        desc_en, desc_fr = overall_descriptions[overall.code.upper()]
                        overall.description_en = desc_en
                        overall.description_fr = desc_fr
                        logger.info(f"Updated overall expectation {overall.code} descriptions")

            db.session.commit()
            logger.info("Successfully updated strand titles and overall descriptions")

    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    main()