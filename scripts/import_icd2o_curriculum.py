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
        ] if strand_ids else []

        # Delete in reverse order (child to parent)
        if overall_ids:
            SpecificExpectation.query.filter(
                SpecificExpectation.overall_expectation_id.in_(overall_ids)
            ).delete(synchronize_session='fetch')

        if strand_ids:
            OverallExpectation.query.filter(
                OverallExpectation.strand_id.in_(strand_ids)
            ).delete(synchronize_session='fetch')

        Strand.query.filter(
            Strand.course_id == course.id
        ).delete(synchronize_session='fetch')

        Course.query.filter_by(code=course_code).delete(synchronize_session='fetch')

        db.session.commit()
        logger.info(f"Successfully cleared existing data for course {course_code}")

    except Exception as e:
        logger.error(f"Error clearing existing data: {str(e)}")
        db.session.rollback()
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

        db.session.commit()

        # Verify strands were created
        for code, strand in created_strands.items():
            if not strand.id:
                raise ValueError(f"Strand {code} was not properly created (no ID assigned)")

    except Exception as e:
        logger.error(f"Error creating strands: {str(e)}")
        db.session.rollback()
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
            },
            'A3': {
                'description_en': 'Applications, Careers, and Connections',
                'description_fr': 'Applications, carrières et connexions',
                'specifics': {
                    'A3.1': {
                        'description_en': 'Investigate various careers related to computer technology and digital applications',
                        'description_fr': 'Explorer diverses carrières liées à la technologie informatique et aux applications numériques'
                    },
                    'A3.2': {
                        'description_en': 'Identify connections between computer science skills and various career opportunities',
                        'description_fr': 'Identifier les liens entre les compétences en informatique et diverses opportunités de carrière'
                    }
                }
            }
        },
        'B': {
            'B1': {
                'description_en': 'Understanding Hardware and Software',
                'description_fr': 'Comprendre le matériel et les logiciels',
                'specifics': {
                    'B1.1': {
                        'description_en': 'Identify and describe the functions of various computer hardware components',
                        'description_fr': 'Identifier et décrire les fonctions de divers composants matériels informatiques'
                    },
                    'B1.2': {
                        'description_en': 'Explain the role of different types of software in computer systems',
                        'description_fr': 'Expliquer le rôle des différents types de logiciels dans les systèmes informatiques'
                    }
                }
            },
            'B2': {
                'description_en': 'Using Hardware and Software',
                'description_fr': 'Utiliser le matériel et les logiciels',
                'specifics': {
                    'B2.1': {
                        'description_en': 'Use various hardware devices effectively and safely',
                        'description_fr': 'Utiliser efficacement et en toute sécurité divers périphériques'
                    },
                    'B2.2': {
                        'description_en': 'Apply appropriate software tools for specific tasks',
                        'description_fr': 'Appliquer les outils logiciels appropriés pour des tâches spécifiques'
                    }
                }
            },
            'B3': {
                'description_en': 'Cybersecurity and Data',
                'description_fr': 'Cybersécurité et données',
                'specifics': {
                    'B3.1': {
                        'description_en': 'Apply cybersecurity best practices to protect digital information',
                        'description_fr': 'Appliquer les meilleures pratiques de cybersécurité pour protéger les informations numériques'
                    },
                    'B3.2': {
                        'description_en': 'Manage and protect personal data in digital environments',
                        'description_fr': 'Gérer et protéger les données personnelles dans les environnements numériques'
                    }
                }
            },
            'B4': {
                'description_en': 'Innovations in Digital Technology',
                'description_fr': 'Innovations en technologie numérique',
                'specifics': {
                    'B4.1': {
                        'description_en': 'Explore emerging trends in digital technology',
                        'description_fr': 'Explorer les tendances émergentes en technologie numérique'
                    },
                    'B4.2': {
                        'description_en': 'Analyze the impact of technological innovations on society',
                        'description_fr': 'Analyser l\'impact des innovations technologiques sur la société'
                    }
                }
            }
        },
        'C': {
            'C1': {
                'description_en': 'Programming Concepts and Algorithms',
                'description_fr': 'Concepts de programmation et algorithmes',
                'specifics': {
                    'C1.1': {
                        'description_en': 'Use fundamental programming concepts and constructs',
                        'description_fr': 'Utiliser des concepts et des constructions de programmation fondamentaux'
                    },
                    'C1.2': {
                        'description_en': 'Create and use algorithms to solve problems',
                        'description_fr': 'Créer et utiliser des algorithmes pour résoudre des problèmes'
                    },
                    'C1.3': {
                        'description_en': 'Apply computational thinking concepts in algorithm development',
                        'description_fr': 'Appliquer les concepts de pensée computationnelle dans le développement d\'algorithmes'
                    }
                }
            },
            'C2': {
                'description_en': 'Writing',
                'description_fr': 'Écriture',
                'specifics': {
                    'C2.1': {
                        'description_en': 'Write clear and maintainable code using proper conventions',
                        'description_fr': 'Écrire du code clair et maintenable en utilisant les conventions appropriées'
                    },
                    'C2.2': {
                        'description_en': 'Document code effectively using comments and documentation',
                        'description_fr': 'Documenter efficacement le code en utilisant des commentaires et de la documentation'
                    }
                }
            },
            'C3': {
                'description_en': 'Modularity and Modification',
                'description_fr': 'Modularité et modification',
                'specifics': {
                    'C3.1': {
                        'description_en': 'Create modular code using functions and procedures',
                        'description_fr': 'Créer du code modulaire en utilisant des fonctions et des procédures'
                    },
                    'C3.2': {
                        'description_en': 'Modify existing code to improve functionality and efficiency',
                        'description_fr': 'Modifier le code existant pour améliorer la fonctionnalité et l\'efficacité'
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
                db.session.flush()  # Flush to get the ID

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

                db.session.flush()  # Flush after each set of specific expectations
                logger.info(f"Created overall expectation {overall_code} with its specific expectations")

            logger.info(f"Completed processing expectations for strand {strand_code}")
            db.session.commit()  # Commit after each strand's expectations

    except Exception as e:
        logger.error(f"Error creating expectations: {str(e)}")
        db.session.rollback()
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
            db.session.commit()  # Commit course creation immediately

            if not course.id:
                raise ValueError("Course was not properly created (no ID assigned)")

            logger.info(f"Created course: {course.code}")

            # Create strands
            strands = create_strands(course.id)

            # Create expectations
            create_expectations(strands)

            # Final verification
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