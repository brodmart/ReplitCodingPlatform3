"""
Initialize database tables for curriculum
"""
from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Verify tables exist
        tables = db.engine.table_names()
        print("Created tables:", tables)

if __name__ == "__main__":
    init_database()
