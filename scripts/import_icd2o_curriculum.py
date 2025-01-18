"""
Script to import ICD2O curriculum data into the database
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def clear_existing_data(course_code: str):
    """Clear existing curriculum data for a given course code"""
    logger = logging.getLogger(__name__)

    try:
        with db.session.begin():
            # Get course ID first
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                logger.info(f"No existing data found for course {course_code}")
                return

            # Get strand IDs for this course
            strand_ids = [row[0] for row in db.session.query(Strand.id).filter_by(course_id=course.id).all()]

            # Get overall expectation IDs for these strands
            overall_ids = [
                row[0] for row in 
                db.session.query(OverallExpectation.id)
                .filter(OverallExpectation.strand_id.in_(strand_ids))
                .all()
            ]

            # Delete in reverse order (child to parent)
            if overall_ids:
                db.session.query(SpecificExpectation).filter(
                    SpecificExpectation.overall_expectation_id.in_(overall_ids)
                ).delete(synchronize_session=False)

            if strand_ids:
                db.session.query(OverallExpectation).filter(
                    OverallExpectation.strand_id.in_(strand_ids)
                ).delete(synchronize_session=False)

            db.session.query(Strand).filter(
                Strand.course_id == course.id
            ).delete(synchronize_session=False)

            db.session.query(Course).filter_by(code=course_code).delete()

            logger.info(f"Successfully cleared existing data for course {course_code}")

    except Exception as e:
        logger.error(f"Error clearing existing data: {str(e)}")
        raise

def create_strands(course_id: int):
    """Create strands for ICD2O course"""
    logger = logging.getLogger(__name__)
    strands_data = [
        {
            'code': 'A',
            'title_en': 'Computational Thinking and Making Connections',
            'title_fr': 'Pensée computationnelle et établissement de liens'
        },
        {
            'code': 'B',
            'title_en': 'Hardware, Software, and Innovations',
            'title_fr': 'Matériel, logiciels et innovations'
        },
        {
            'code': 'C',
            'title_en': 'Programming',
            'title_fr': 'Programmation'
        }
    ]

    created_strands = {}
    try:
        for strand_data in strands_data:
            logger.info(f"Creating strand {strand_data['code']}")
            strand = Strand(
                course_id=course_id,
                code=strand_data['code'],
                title_en=strand_data['title_en'],
                title_fr=strand_data['title_fr']
            )
            db.session.add(strand)
            db.session.flush()
            created_strands[strand.code] = strand
            logger.info(f"Created strand {strand_data['code']}: {strand_data['title_en']}")

        # Verify strands were created
        for code, strand in created_strands.items():
            if not strand.id:
                raise ValueError(f"Strand {code} was not properly created (no ID assigned)")

    except Exception as e:
        logger.error(f"Error creating strands: {str(e)}")
        raise

    return created_strands

def create_expectations(strands: dict):
    """Create overall and specific expectations for ICD2O course"""
    logger = logging.getLogger(__name__)

    # Define expectations data
    expectations_data = {
        'A': {
            'A1': {
                'description_en': 'Computational Thinking, Planning, and Purpose',
                'description_fr': 'Pensée computationnelle, planification et objectif',
                'specifics': {
                    'A1.1': {
                        'description_en': 'Use computational thinking strategies to decompose problems into smaller, more manageable subproblems',
                        'description_fr': 'Utiliser des stratégies de pensée computationnelle pour décomposer des problèmes en sous-problèmes plus petits et plus gérables'
                    },
                    'A1.2': {
                        'description_en': 'Create computational representations of mathematical and other real-world problems',
                        'description_fr': 'Créer des représentations computationnelles de problèmes mathématiques et autres problèmes réels'
                    },
                    'A1.3': {
                        'description_en': 'Develop algorithms to solve problems using sequence, selection, and repetition',
                        'description_fr': 'Développer des algorithmes pour résoudre des problèmes en utilisant la séquence, la sélection et la répétition'
                    }
                }
            },
            'A2': {
                'description_en': 'Digital Technology and Society',
                'description_fr': 'Technologie numérique et société',
                'specifics': {
                    'A2.1': {
                        'description_en': 'Identify computer science concepts in various fields and contexts',
                        'description_fr': 'Identifier les concepts informatiques dans divers domaines et contextes'
                    },
                    'A2.2': {
                        'description_en': 'Apply computer science concepts to solve problems in other subject areas',
                        'description_fr': 'Appliquer les concepts informatiques pour résoudre des problèmes dans d\'autres domaines'
                    }
                }
            }
        },
        'B': {
            'B1': {
                'description_en': 'Analyze and manage various types of data using appropriate tools and strategies',
                'description_fr': "Analyser et gérer différents types de données à l'aide d'outils et de stratégies appropriés",
                'specifics': {
                    'B1.1': {
                        'description_en': 'Use appropriate tools to collect and organize data from various sources',
                        'description_fr': "Utiliser des outils appropriés pour collecter et organiser des données de diverses sources"
                    },
                    'B1.2': {
                        'description_en': 'Process and analyze data to draw meaningful conclusions',
                        'description_fr': "Traiter et analyser des données pour tirer des conclusions significatives"
                    },
                    'B1.3': {
                        'description_en': 'Present data effectively using various visualization techniques',
                        'description_fr': "Présenter efficacement des données en utilisant diverses techniques de visualisation"
                    }
                }
            },
            'B2': {
                'description_en': 'Apply critical thinking skills to evaluate information and media content',
                'description_fr': "Appliquer des compétences de pensée critique pour évaluer l'information et le contenu médiatique",
                'specifics': {
                    'B2.1': {
                        'description_en': 'Assess the reliability and credibility of digital information sources',
                        'description_fr': "Évaluer la fiabilité et la crédibilité des sources d'information numérique"
                    },
                    'B2.2': {
                        'description_en': 'Identify bias and perspective in digital media content',
                        'description_fr': "Identifier les préjugés et les perspectives dans le contenu des médias numériques"
                    }
                }
            }
        },
        'C': {
            'C1': {
                'description_en': 'Apply computational thinking concepts and practices to solve problems',
                'description_fr': "Appliquer les concepts et les pratiques de la pensée informatique pour résoudre des problèmes",
                'specifics': {
                    'C1.1': {
                        'description_en': 'Decompose complex problems into smaller, manageable parts',
                        'description_fr': "Décomposer des problèmes complexes en parties plus petites et gérables"
                    },
                    'C1.2': {
                        'description_en': 'Develop algorithms to solve computational problems',
                        'description_fr': "Développer des algorithmes pour résoudre des problèmes informatiques"
                    },
                    'C1.3': {
                        'description_en': 'Test and debug algorithms and programs systematically',
                        'description_fr': "Tester et déboguer systématiquement les algorithmes et les programmes"
                    }
                }
            },
            'C2': {
                'description_en': 'Create and modify computer programs to solve problems',
                'description_fr': "Créer et modifier des programmes informatiques pour résoudre des problèmes",
                'specifics': {
                    'C2.1': {
                        'description_en': 'Write and modify program code using fundamental programming concepts',
                        'description_fr': "Écrire et modifier du code de programme en utilisant des concepts de programmation fondamentaux"
                    },
                    'C2.2': {
                        'description_en': 'Create programs that respond to user input and produce desired output',
                        'description_fr': "Créer des programmes qui répondent aux entrées utilisateur et produisent la sortie souhaitée"
                    }
                }
            }
        }
    }

    try:
        created_overall_expectations = {}

        for strand_code, overall_exps in expectations_data.items():
            if strand_code not in strands:
                raise ValueError(f"Strand {strand_code} not found in provided strands dictionary")

            strand = strands[strand_code]
            logger.info(f"Processing expectations for strand {strand_code}")

            for overall_code, overall_data in overall_exps.items():
                logger.info(f"Creating overall expectation {overall_code}")

                # Create overall expectation
                overall = OverallExpectation(
                    strand_id=strand.id,
                    code=overall_code,
                    description_en=overall_data['description_en'],
                    description_fr=overall_data['description_fr']
                )
                db.session.add(overall)
                db.session.flush()

                if not overall.id:
                    raise ValueError(f"Overall expectation {overall_code} was not properly created (no ID assigned)")

                created_overall_expectations[overall_code] = overall

                # Create specific expectations
                for specific_code, specific_data in overall_data['specifics'].items():
                    logger.debug(f"Creating specific expectation {specific_code}")
                    specific = SpecificExpectation(
                        overall_expectation_id=overall.id,
                        code=specific_code,
                        description_en=specific_data['description_en'],
                        description_fr=specific_data['description_fr']
                    )
                    db.session.add(specific)
                    db.session.flush()

                    if not specific.id:
                        raise ValueError(f"Specific expectation {specific_code} was not properly created (no ID assigned)")

                logger.info(f"Created overall expectation {overall_code} with its specific expectations")

            logger.info(f"Completed processing expectations for strand {strand_code}")

    except Exception as e:
        logger.error(f"Error creating expectations: {str(e)}")
        raise

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICD2O curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # Clear existing data
            clear_existing_data('ICD2O')

            # Create new course entry
            course = Course(
                code='ICD2O',
                title_en='Digital Technology and Innovations in the Changing World',
                title_fr='Technologies numériques et innovations dans un monde en évolution',
                description_en='This course helps students develop digital literacy and computational thinking skills while exploring computer science concepts.',
                description_fr='Ce cours aide les élèves à développer leurs compétences en littératie numérique et en pensée computationnelle tout en explorant les concepts de l\'informatique.',
            )
            db.session.add(course)
            db.session.flush()

            if not course.id:
                raise ValueError("Course was not properly created (no ID assigned)")

            logger.info(f"Created course: {course.code}")

            # Create strands
            strands = create_strands(course.id)

            # Create expectations
            create_expectations(strands)

            # Commit all changes
            db.session.commit()
            logger.info("All changes committed successfully")

            # Verify the complete data structure
            course_check = Course.query.filter_by(code='ICD2O').first()
            if course_check:
                strand_count = Strand.query.filter_by(course_id=course_check.id).count()
                overall_count = OverallExpectation.query.join(Strand).filter(
                    Strand.course_id == course_check.id
                ).count()
                specific_count = SpecificExpectation.query.join(
                    OverallExpectation
                ).join(
                    Strand
                ).filter(
                    Strand.course_id == course_check.id
                ).count()

                logger.info("Final verification:")
                logger.info(f"- Course: {course_check.code}")
                logger.info(f"- Strands: {strand_count}")
                logger.info(f"- Overall Expectations: {overall_count}")
                logger.info(f"- Specific Expectations: {specific_count}")
            else:
                logger.error("Verification failed: Course not found after creation")
                raise ValueError("Course verification failed")

    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    main()