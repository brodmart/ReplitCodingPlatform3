"""
Script to update English translations for ICS3U specific expectations
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def get_english_translations():
    """
    Define English translations for ICS3U specific expectations
    """
    return {
        'A1.1': 'Explain the functions of internal hardware components of a personal computer.',
        'A1.2': 'Explain the functions of commonly used external peripherals.',
        'A1.3': 'Compare computer hardware performance across different personal computers using objective measurements.',
        'A1.4': 'Explain the functional relationship between a programming language and essential computer components.',
        'A2.1': 'List program files using operating system functions.',
        'A2.2': 'Apply systematic file backup procedures.',
        'A2.3': 'Describe several types of viruses.',
        'A2.4': 'Use local network services to facilitate file management and backup during program development.',
        'A3.1': 'Compare the main functions of operating systems and application software, including development tools.',
        'A3.2': 'Explain the characteristics and benefits of various development environments for developing programs.',
        'A3.3': 'Use the respective functions of a compiler or interpreter.',
        'A3.4': 'Use available help resources for program development.',
        'B1.1': 'Describe primitive data types defined by a given programming language.',
        'B1.2': 'Describe the internal representation of various data types.',
        'B1.3': 'Define the terms: literal value, constant, and variable.',
        'B1.4': 'Define the concepts of variable scope and lifetime.',
        'B1.5': 'Describe different types of functions.',
        'B1.6': 'Apply fundamental syntax rules of a programming language.',
        'B1.7': 'Write expressions using operators.',
        'B2.1': 'Define characteristics of a one-dimensional array such as elements, index, and size.',
        'B2.2': 'Explain algorithms for reading or modifying elements of a one-dimensional array.',
        'B2.3': 'Explain the operation of control structures - sequential, decisional, and iterative - in a program.',
        'B2.4': 'Explain algorithms for processing user input and displaying results on screen.',
        'B3.1': 'Explain the difference between logic errors, syntax errors, and runtime errors in a program.',
        'B3.2': 'Interpret error messages from development and runtime environments.',
        'B3.3': 'Fix logic errors, syntax errors, and runtime errors in a program.',
        'B3.4': 'Determine an appropriate set of values to test program accuracy.',
        'B3.5': 'Debug programs using different methods.',
        'B3.6': 'Apply layout, writing, and naming rules to ensure program maintenance and documentation.',
        'C1.1': 'Describe problems in terms of input data, data processing, and output data.',
        'C1.2': 'Use different approaches to solve problems.',
        'C1.3': 'Describe main software development activities and their deliverables.',
        'C1.4': 'Interpret schedules.',
        'C1.5': 'Apply a test plan.',
        'C1.6': 'Present deliverables orally and in writing using appropriate terminology.',
        'C2.1': 'Design algorithms that solve given mathematical problems.',
        'C2.2': 'Design data processing algorithms.',
        'C2.3': 'Design nested control structures.',
        'C2.4': 'Design algorithms that handle exceptions.',
        'C2.5': 'Compare qualitatively and quantitatively the performance of two algorithms that solve the same problem.',
        'C3.1': 'Design functions that meet given requirements.',
        'C3.2': 'Model a programming problem using various techniques.',
        'C3.3': 'Apply the principle of modularization to program development.',
        'C3.4': 'Design user-friendly interfaces that meet user needs.',
        'C3.5': 'Develop programs that solve given problems using pre-designed modules and predefined functions.',
        'D1.1': 'Analyze the impact of the computer industry on the environment and public health by identifying beneficial and harmful factors.',
        'D1.2': 'Evaluate the impact of measures taken by public and private organizations on the environmental footprint of computing.',
        'D1.3': 'Determine strategies to reduce computer system consumption, and to reuse and recycle computer hardware.',
        'D1.4': 'Describe ways to prevent health problems related to computer use.',
        'D2.1': 'Compare possible career choices in computing, particularly regarding tasks, salary conditions, and advancement opportunities.',
        'D2.2': 'List available computing training programs, identifying prerequisites and educational options available in French.',
        'D2.3': 'Identify opportunities and means to gain experience in computing.',
        'D2.4': 'Describe support services that promote orientation towards non-traditional computing careers.',
        'D2.5': 'Describe essential skills and work habits from the Ontario Skills Passport (OSP) that are indispensable for success in the computing industry.',
        'D2.6': 'Create a portfolio by selecting work or achievements that demonstrate skills, competencies, experiences, and certifications acquired in computing.'
    }

def main():
    """Update English translations for ICS3U specific expectations"""
    translations = get_english_translations()

    try:
        with app.app_context():
            # Get ICS3U course
            course = Course.query.filter_by(code='ICS3U').first()
            if not course:
                print("Error: ICS3U course not found")
                return

            # Get all specific expectations for the course, including for strands C and D
            specifics = SpecificExpectation.query.join(
                OverallExpectation,
                SpecificExpectation.overall_expectation_id == OverallExpectation.id
            ).join(
                Strand,
                OverallExpectation.strand_id == Strand.id
            ).filter(
                Strand.course_id == course.id
            ).all()

            # Update specific expectations
            updated_count = 0
            for specific in specifics:
                if specific.code.upper() in translations:  # Case-insensitive comparison
                    specific.description_en = translations[specific.code.upper()]
                    updated_count += 1
                    print(f"Updated {specific.code}: {specific.description_en[:50]}...")

            db.session.commit()
            print(f"Updated {updated_count} specific expectations with English translations")

    except Exception as e:
        print(f"Error updating translations: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    main()