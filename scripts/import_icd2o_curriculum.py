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
            # Clear existing ICD2O data if any
            Course.query.filter_by(code='ICD2O').delete()
            db.session.commit()

            # Create course
            course = Course(
                code='ICD2O',
                title_en='Digital Technology and Innovations in the Changing World',
                title_fr='Technologies numériques et innovations dans un monde en évolution'
            )
            db.session.add(course)
            db.session.commit()
            logger.info(f"Created course: {course.code}")

            # Create strands
            strands = {
                'A': {
                    'title_en': 'Computational Thinking and Making Connections',
                    'title_fr': 'Pensée computationnelle et établissement de liens'
                },
                'B': {
                    'title_en': 'Hardware, Software, and Innovations',
                    'title_fr': 'Matériel, logiciels et innovations'
                },
                'C': {
                    'title_en': 'Programming',
                    'title_fr': 'Programmation'
                }
            }

            # Overall expectations
            overall_expectations = {
                'A1': 'Computational Thinking, Planning, and Purpose',
                'A2': 'Digital Technology and Society',
                'A3': 'Applications, Careers, and Connections',
                'B1': 'Understanding Hardware and Software',
                'B2': 'Using Hardware and Software',
                'B3': 'Cybersecurity and Data',
                'B4': 'Innovations in Digital Technology',
                'C1': 'Programming Concepts and Algorithms',
                'C2': 'Writing Programs',
                'C3': 'Modularity and Modification'
            }

            # Specific expectations from chat history
            specific_expectations = {
                'A1.1': 'apply computational thinking concepts and practices when planning and designing computational artifacts',
                'A1.2': 'use a variety of tools and processes to plan, design, and share algorithms and computational artifacts',
                'A1.3': 'develop computational artifacts for a variety of contexts and purposes that support the needs of diverse users and audiences',
                'A2.1': 'investigate current social, cultural, economic, environmental, and ethical issues related to digital technology that have personal, local, and global impacts, taking various perspectives into account',
                'A2.2': 'analyze personal and societal safety and cybersecurity issues related to digital technology, and identify measures and technologies that can help mitigate related concerns for individuals and communities',
                'A2.3': 'investigate contributions to innovations in digital technology and computing by people from diverse local, Canadian, and global communities, including Indigenous communities in Canada and around the world',
                'A2.4': 'investigate how to identify and address bias involving digital technology',
                'A2.5': 'analyze accessibility issues involving digital technology, and identify measures that can improve accessibility',
                'A3.1': 'investigate how digital technology and programming skills can be used within a variety of disciplines in real-world applications',
                'A3.2': 'investigate ways in which various industries, including those that involve skilled trades, are changing as a result of digital technology and programming innovations',
                'A3.3': 'investigate various career options related to digital technology and programming, and ways to continue their learning in these areas',
                'B1.1': 'describe the functions and features of various core components of hardware associated with digital technologies they encounter in their everyday life',
                'B1.2': 'describe the functions and features of various connected devices associated with digital technologies they encounter in their everyday life',
                'B1.3': 'describe the functions of various types of software they encounter in their everyday life',
                'B2.1': 'use file management techniques, including those related to local and cloud storage, to organize, edit, and share files',
                'B2.2': 'identify and use effective research practices and supports when learning to use new hardware or software',
                'B2.3': 'assess the hardware and software requirements for various users, contexts, and purposes in order to make recommendations for devices and programs',
                'B3.1': 'apply safe and effective data practices when using digital technology in various contexts',
                'B3.2': 'apply safe and effective security practices, including practices to protect their privacy, when using digital technology in various contexts',
                'B4.1': 'investigate current innovations, including automation and artificial intelligence systems, and assess the impacts of these technologies on everyday life',
                'B4.2': 'investigate hardware and methods used to establish networks and connectivity, and assess the benefits and limitations of increased connectivity with reference to everyday life',
                'B4.3': 'investigate emerging innovations related to hardware and software and their possible benefits and limitations with reference to everyday life in the future',
                'C1.1': 'use appropriate terminology to describe programming concepts and algorithms',
                'C1.2': 'describe simple algorithms that are encountered in everyday situations',
                'C1.3': 'identify various types of data and explain how they are used within programs',
                'C1.4': 'determine the appropriate expressions and instructions to use in a programming statement, taking into account the order of operations',
                'C1.5': 'identify and explain situations in which conditional and repeating structures are required',
                'C2.1': 'use variables, constants, expressions, and assignment statements to store and manipulate numbers and text in a program',
                'C2.2': 'write programs that use and generate data involving various sources and formats',
                'C2.3': 'write programs that include single and nested conditional statements',
                'C2.4': 'write programs that include sequential, selection, and repeating events',
                'C2.5': 'write programs that include the use of Boolean operators, comparison operators, text operators, and arithmetic operators',
                'C2.6': 'interpret program errors and implement strategies to resolve them',
                'C2.7': 'write clear internal documentation and use coding standards to improve code readability',
                'C3.1': 'analyze existing code to understand the components and outcomes of the code',
                'C3.2': 'modify an existing program, or components of a program, to enable it to complete a different task',
                'C3.3': 'write subprograms, and use existing subprograms, to complete program components',
                'C3.4': 'write programs that make use of external or add-on modules or libraries',
                'C3.5': 'explain the components of a computational artifact they have created, including considerations for reuse by others'
            }

            # Create strands and expectations
            strand_objects = {}
            overall_objects = {}

            for code, info in strands.items():
                strand = Strand(
                    course_id=course.id,
                    code=code,
                    title_en=info['title_en'],
                    title_fr=info['title_fr']
                )
                db.session.add(strand)
                db.session.flush()
                strand_objects[code] = strand
                logger.info(f"Created strand: {code}")

            # Create overall expectations
            for code, description in overall_expectations.items():
                strand_code = code[0]  # 'A' from 'A1'
                overall = OverallExpectation(
                    strand_id=strand_objects[strand_code].id,
                    code=code,
                    description_en=description,
                    description_fr=''  # To be filled later
                )
                db.session.add(overall)
                db.session.flush()
                overall_objects[code] = overall
                logger.info(f"Created overall expectation: {code}")

            # Create specific expectations
            for code, description in specific_expectations.items():
                overall_code = code.split('.')[0]  # 'A1' from 'A1.1'
                specific = SpecificExpectation(
                    overall_expectation_id=overall_objects[overall_code].id,
                    code=code,
                    description_en=description,
                    description_fr=''  # To be filled later
                )
                db.session.add(specific)
                logger.info(f"Created specific expectation: {code}")

            db.session.commit()
            logger.info("Curriculum import completed successfully")

            # Verify import results
            course_check = Course.query.filter_by(code='ICD2O').first()
            if course_check:
                strand_count = len(strands)
                overall_count = len(overall_expectations)
                specific_count = len(specific_expectations)

                logger.info("Import statistics:")
                logger.info(f"- Strands: {strand_count}")
                logger.info(f"- Overall Expectations: {overall_count}")
                logger.info(f"- Specific Expectations: {specific_count}")
            else:
                logger.error("Failed to verify course after import")

    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    main()
