"""
Script to seed initial coding activities
"""
from app import app, db
from models.student import CodingActivity
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def seed_activities():
    """Seed initial coding activities"""
    activities = [
        {
            'title': 'Introduction to Variables',
            'description': 'Learn about variables and how to use them in programming',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'beginner',
            'sequence': 1,
            'instructions': 'Create variables of different types and print their values',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None  # Explicitly set deleted_at to None
        },
        {
            'title': 'Basic Input/Output',
            'description': 'Learn how to get input from users and display output',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'beginner',
            'sequence': 2,
            'instructions': 'Write a program that asks for user\'s name and age, then displays a greeting',
            'starter_code': '#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None  # Explicitly set deleted_at to None
        },
        {
            'title': 'C# Variables and Types',
            'description': 'Introduction to C# variables and basic data types',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'beginner',
            'sequence': 1,
            'instructions': 'Create variables of different types and print their values',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None  # Explicitly set deleted_at to None
        },
        {
            'title': 'C# Console Input/Output',
            'description': 'Learn to handle user input and output in C#',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'beginner',
            'sequence': 2,
            'instructions': 'Write a program that asks for user\'s name and age, then displays a greeting',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None  # Explicitly set deleted_at to None
        }
    ]

    logger.info("Starting to seed activities...")

    try:
        # Clear existing activities
        logger.info("Clearing existing activities...")
        CodingActivity.query.delete()
        db.session.commit()
        logger.info("Cleared existing activities")

        # Add new activities
        for activity_data in activities:
            activity = CodingActivity(**activity_data)
            db.session.add(activity)
            logger.debug(f"Added activity: {activity_data['title']}")

        db.session.commit()
        logger.info(f"Successfully seeded {len(activities)} activities")

    except Exception as e:
        logger.error(f"Error seeding activities: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    with app.app_context():
        seed_activities()