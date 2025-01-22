"""
Combined verification script for curriculum expectations.
Only loads when explicitly called for verification.
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to path only when running verification
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    logging.basicConfig(level=logging.INFO)

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def verify_expectation(code: str = None):
    """Verify specific expectations in the database"""
    if __name__ != "__main__":
        return  # Only run when explicitly called
        
    logger = logging.getLogger(__name__)
    
    try:
        with app.app_context():
            if code:
                # Verify single expectation
                specific = SpecificExpectation.query.filter(
                    db.func.lower(SpecificExpectation.code) == code.lower()
                ).first()
                if specific:
                    logger.info(f"Found expectation: {specific.code}")
                    return True
            else:
                # Verify all expectations
                expectations = SpecificExpectation.query.all()
                logger.info(f"Found {len(expectations)} expectations")
                return bool(expectations)
                
    except Exception as e:
        logger.error(f"Error verifying expectations: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        verify_expectation(sys.argv[1])
    else:
        verify_expectation()
