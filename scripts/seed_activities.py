"""
Script to seed initial coding activities
"""
from app import app, db
from models import CodingActivity
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def seed_activities():
    """Seed initial coding activities"""
    # Activities for Grade 10 (TEJ2O)
    tej2o_activities = [
        {
            'title': 'Introduction to Variables in C++',
            'description': 'Learn about variables and data types in C++',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'beginner',
            'sequence': 1,
            'instructions': 'Create variables of different types and print their values',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Basic Input/Output in C++',
            'description': 'Learn to handle user input and output in C++',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'beginner',
            'sequence': 2,
            'instructions': 'Write a program that asks for user\'s name and age, then displays a greeting',
            'starter_code': '#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None
        },
    ]

    # Activities for Grade 11 (ICS3U)
    ics3u_activities = [
        {
            'title': 'Introduction to C# Variables',
            'description': 'Learn about variables and data types in C#',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'beginner',
            'sequence': 1,
            'instructions': 'Create variables of different types and print their values',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Basic Input/Output in C#',
            'description': 'Learn to handle user input and output in C#',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'beginner',
            'sequence': 2,
            'instructions': 'Write a program that asks for user\'s name and age, then displays a greeting',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None
        },
    ]

    all_activities = tej2o_activities + ics3u_activities

    logger.info("Starting to seed activities...")

    try:
        # Clear existing activities
        logger.info("Clearing existing activities...")
        CodingActivity.query.delete()
        db.session.commit()
        logger.info("Cleared existing activities")

        # Add new activities
        for activity_data in all_activities:
            activity = CodingActivity(**activity_data)
            db.session.add(activity)
            logger.debug(f"Added activity: {activity_data['title']} for curriculum {activity_data['curriculum']}")

        db.session.commit()
        logger.info(f"Successfully seeded {len(all_activities)} activities")

    except Exception as e:
        logger.error(f"Error seeding activities: {str(e)}", exc_info=True)
        db.session.rollback()
        raise

if __name__ == '__main__':
    with app.app_context():
        seed_activities()