from app import app, db
from models import Student
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_admin_user():
    with app.app_context():
        try:
            # Create admin user
            admin = Student(
                username='admin',
                is_admin=True,
                failed_login_attempts=0
            )
            success, message = admin.set_password('admin123')

            if not success:
                logger.error(f"Failed to set admin password: {message}")
                return

            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully")

            # Verify the user was created
            admin_check = Student.query.filter_by(username='admin').first()
            if admin_check and admin_check.is_admin:
                logger.info("Admin user verified successfully")
                # Verify password hash
                if admin_check.password_hash:
                    logger.info("Password hash verified")
                    logger.debug(f"Password hash: {admin_check.password_hash[:20]}...")
                else:
                    logger.error("Password hash is empty")
            else:
                logger.error("Failed to verify admin user")

        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    create_admin_user()