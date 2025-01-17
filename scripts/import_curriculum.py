"""
Script to import curriculum data into the database
"""
from app import app, db
from utils.curriculum_importer import CurriculumImporter

def main():
    # Ensure all tables exist
    with app.app_context():
        db.create_all()
        
        # Read curriculum content from file
        with open('attached_assets/Pasted--Introduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initie-1737142253494.txt', 'r') as f:
            content = f.read()
            
        # Import curriculum data
        importer = CurriculumImporter()
        importer.import_curriculum(content)
        
        print("Curriculum import completed successfully!")

if __name__ == '__main__':
    main()
