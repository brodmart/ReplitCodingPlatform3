"""
Script to import ICS3U curriculum data into the database from the provided French curriculum document
"""
import os
import sys

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from utils.curriculum_importer import CurriculumImporter

def main():
    # Initialize database connection within app context
    with app.app_context():
        # Read ICS3U curriculum content from file
        with open('attached_assets/Pasted--Introduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initie-1737142253494.txt', 'r', encoding='utf-8') as f:
            content = f.read()

        # Import curriculum data
        importer = CurriculumImporter()
        importer.import_curriculum(content)

        print("ICS3U curriculum import completed successfully!")

if __name__ == '__main__':
    main()