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
            'instructions': 'Write a program that asks for user\'s name and age',
            'starter_code': '#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Conditional Statements in C++',
            'description': 'Learn about if-else statements and control flow',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'beginner',
            'sequence': 3,
            'instructions': 'Create a program that uses if-else statements',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Loops in C++',
            'description': 'Learn about for and while loops',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'intermediate',
            'sequence': 4,
            'instructions': 'Create programs using different types of loops',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'Functions in C++',
            'description': 'Learn about functions and parameters',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'intermediate',
            'sequence': 5,
            'instructions': 'Create and use functions with parameters',
            'starter_code': '#include <iostream>\nusing namespace std;\n\n// Write your functions here\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'Arrays in C++',
            'description': 'Learn about arrays and array operations',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'intermediate',
            'sequence': 6,
            'instructions': 'Create and manipulate arrays',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'String Operations in C++',
            'description': 'Learn about string manipulation',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'intermediate',
            'sequence': 7,
            'instructions': 'Work with strings and string functions',
            'starter_code': '#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'File Operations in C++',
            'description': 'Learn about file input and output',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'advanced',
            'sequence': 8,
            'instructions': 'Read from and write to files',
            'starter_code': '#include <iostream>\n#include <fstream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 200,
            'deleted_at': None
        },
        {
            'title': 'Basic Algorithms in C++',
            'description': 'Learn about basic sorting and searching',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'advanced',
            'sequence': 9,
            'instructions': 'Implement basic sorting and searching algorithms',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 200,
            'deleted_at': None
        },
        {
            'title': 'Final Project in C++',
            'description': 'Create a complete program using all learned concepts',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'difficulty': 'advanced',
            'sequence': 10,
            'instructions': 'Create a comprehensive program',
            'starter_code': '#include <iostream>\n#include <string>\n#include <fstream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}',
            'points': 300,
            'deleted_at': None
        }
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
            'instructions': 'Write a program that asks for user\'s name and age',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Conditional Statements in C#',
            'description': 'Learn about if-else statements and control flow',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'beginner',
            'sequence': 3,
            'instructions': 'Create a program that uses if-else statements',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 100,
            'deleted_at': None
        },
        {
            'title': 'Loops in C#',
            'description': 'Learn about for and while loops',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'intermediate',
            'sequence': 4,
            'instructions': 'Create programs using different types of loops',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'Methods in C#',
            'description': 'Learn about methods and parameters',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'intermediate',
            'sequence': 5,
            'instructions': 'Create and use methods with parameters',
            'starter_code': 'using System;\n\nclass Program {\n    // Write your methods here\n    \n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'Arrays in C#',
            'description': 'Learn about arrays and array operations',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'intermediate',
            'sequence': 6,
            'instructions': 'Create and manipulate arrays',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'String Operations in C#',
            'description': 'Learn about string manipulation',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'intermediate',
            'sequence': 7,
            'instructions': 'Work with strings and string methods',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 150,
            'deleted_at': None
        },
        {
            'title': 'File Operations in C#',
            'description': 'Learn about file input and output',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'advanced',
            'sequence': 8,
            'instructions': 'Read from and write to files',
            'starter_code': 'using System;\nusing System.IO;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 200,
            'deleted_at': None
        },
        {
            'title': 'Basic Algorithms in C#',
            'description': 'Learn about basic sorting and searching',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'advanced',
            'sequence': 9,
            'instructions': 'Implement basic sorting and searching algorithms',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 200,
            'deleted_at': None
        },
        {
            'title': 'Final Project in C#',
            'description': 'Create a complete program using all learned concepts',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'difficulty': 'advanced',
            'sequence': 10,
            'instructions': 'Create a comprehensive program',
            'starter_code': 'using System;\nusing System.IO;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}',
            'points': 300,
            'deleted_at': None
        }
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