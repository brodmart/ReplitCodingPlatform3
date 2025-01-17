"""
Script to create curriculum database tables using Flask-Migrate
"""
import os
import sys

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def main():
    # Initialize migrations
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    main()