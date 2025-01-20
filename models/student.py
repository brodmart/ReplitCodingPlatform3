"""
Student model and related models for the curriculum platform
"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import text, event
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from app import db

logger = logging.getLogger(__name__)

class Student(UserMixin, db.Model):
    """Student model representing a user in the system"""
    __table_args__ = (
        db.Index('idx_student_username', 'username'),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_path = db.Column(db.String(256))

    # Security fields
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    last_failed_login = db.Column(db.DateTime)
    account_locked_until = db.Column(db.DateTime)

    # Password reset fields
    reset_password_token = db.Column(db.String(100), unique=True)
    reset_password_token_expiration = db.Column(db.DateTime)

    # Progress tracking
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    submissions = db.relationship('CodeSubmission', back_populates='student', lazy=True)
    progress = db.relationship('StudentProgress', backref='student', lazy=True)
    shared_codes = db.relationship('SharedCode', back_populates='student', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

    def set_password(self, password):
        """Hash password using werkzeug's built-in method"""
        if len(password) < 6:
            return False, "Password must be at least 6 characters long."
        try:
            self.password_hash = generate_password_hash(password)
            return True, None
        except Exception as e:
            logger.error(f"Password hashing error: {str(e)}")
            return False, "An error occurred while setting the password."

    def check_password(self, password):
        """Verify password using werkzeug's built-in method"""
        try:
            if not self.password_hash:
                logger.error("Password hash is empty")
                return False
            logger.debug(f"Attempting password verification for user: {self.username}")
            result = check_password_hash(self.password_hash, password)
            logger.debug(f"Password verification result for {self.username}: {result}")
            return result
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False

    def increment_failed_login(self):
        """Track failed login attempts"""
        if self.failed_login_attempts is None:  # Add safety check
            self.failed_login_attempts = 0
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

        if self.failed_login_attempts >= 5:  # Lock after 5 attempts
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_failed_login(self):
        """Reset failed login counter"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.account_locked_until = None

    def is_account_locked(self):
        """Check if account is temporarily locked"""
        if self.account_locked_until and self.account_locked_until > datetime.utcnow():
            return True
        return False

    @staticmethod
    def get_by_username(username):
        """Safely get user by username"""
        return Student.query.filter(Student.username == username).first()

    def __repr__(self):
        return f'<Student {self.username}>'

class CodeSubmission(db.Model):
    """Model for storing student code submissions"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Add relationships
    student = db.relationship('Student', back_populates='submissions')

class CodingActivity(db.Model):
    """Model for coding exercises and activities"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudentProgress(db.Model):
    """Model for tracking student progress"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('coding_activity.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SharedCode(db.Model):
    """Model for sharing code snippets"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', back_populates='shared_codes')

class AuditLog(db.Model):
    """Model for tracking changes to student records"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)