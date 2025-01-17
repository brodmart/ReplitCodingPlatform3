"""
Script to import ICS3U curriculum data into the database
"""
from app import app, db
from utils.curriculum_importer import CurriculumImporter

def main():
    # Ensure all tables exist
    with app.app_context():
        db.create_all()

        # Read ICS3U curriculum content from file
        with open('curriculum/ICS3U_curriculum.txt', 'r') as f:
            content = f.read()

        # Import curriculum data
        importer = CurriculumImporter()
        importer.import_curriculum(content)

        print("ICS3U curriculum import completed successfully!")

if __name__ == '__main__':
    main()