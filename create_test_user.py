from app import app, db
from models import Student
from werkzeug.security import generate_password_hash
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_test_user():
    with app.app_context():
        try:
            # Check if test user exists
            test_user = Student.query.filter_by(
                username='testuser'
            ).first()

            if test_user:
                # Update existing user's password
                test_user.password_hash = generate_password_hash('testpass123')
                logger.info("Updated existing test user's password")
            else:
                # Create new test user
                test_user = Student(
                    username='testuser',
                    email='testuser@example.com',
                    password_hash=generate_password_hash('testpass123')
                )
                db.session.add(test_user)

            db.session.commit()
            logger.info("Test user setup completed successfully")

        except Exception as e:
            logger.error(f"Error setting up test user: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_test_user()