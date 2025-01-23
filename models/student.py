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
    achievements = db.relationship('StudentAchievement', backref='student', lazy=True)
    submissions = db.relationship('CodeSubmission', back_populates='student', lazy=True)
    progress = db.relationship('StudentProgress', backref='student', lazy=True)
    shared_codes = db.relationship('SharedCode', back_populates='student', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

    # Constants for account locking
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def is_account_locked(self):
        """Check if the account is currently locked"""
        if self.account_locked_until and self.account_locked_until > datetime.utcnow():
            return True
        return False

    def record_failed_login(self):
        """Record a failed login attempt and lock account if necessary"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

        if self.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
            self.account_locked_until = datetime.utcnow() + self.LOCKOUT_DURATION
            logger.warning(f"Account locked for user {self.username} due to too many failed attempts")

        db.session.commit()

    def reset_failed_login_attempts(self):
        """Reset the failed login attempts counter after successful login"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.account_locked_until = None
        db.session.commit()

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

    def __repr__(self):
        return f'<Student {self.username}>'

class Achievement(db.Model):
    """Achievement model for tracking student accomplishments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    criteria = db.Column(db.String(200), nullable=False)
    badge_icon = db.Column(db.String(200))
    points = db.Column(db.Integer)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Achievement {self.name}>'

class StudentAchievement(db.Model):
    """Junction model linking students with their achievements"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    achievement = db.relationship('Achievement', backref=db.backref('student_achievements', lazy=True))

    def __repr__(self):
        return f'<StudentAchievement student_id={self.student_id} achievement_id={self.achievement_id}>'

class CodingActivity(db.Model):
    """Model for coding exercises and activities"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    title_fr = db.Column(db.String(255), nullable=True)  # Added French title
    description_fr = db.Column(db.Text, nullable=True)   # Added French description
    curriculum = db.Column(db.String(255), nullable=False, default='ICS3U')
    language = db.Column(db.String(50), nullable=True)
    difficulty = db.Column(db.String(50), nullable=True)
    sequence = db.Column(db.Integer, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    starter_code = db.Column(db.Text, nullable=True)
    solution_code = db.Column(db.Text, nullable=True)
    test_cases = db.Column(db.JSON, nullable=True)
    hints = db.Column(db.JSON, nullable=True)
    common_errors = db.Column(db.JSON, nullable=True)
    points = db.Column(db.Integer, nullable=True)
    max_attempts = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    submissions = db.relationship('CodeSubmission', back_populates='activity', lazy=True)
    progress_records = db.relationship('StudentProgress', back_populates='activity', lazy=True)

    def __repr__(self):
        return f'<CodingActivity {self.title}>'

class StudentProgress(db.Model):
    """Model for tracking student progress"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('coding_activity.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, default=0)
    last_submission = db.Column(db.Text)

    # Relationship
    activity = db.relationship('CodingActivity', back_populates='progress_records')

    def __repr__(self):
        return f'<StudentProgress student_id={self.student_id} activity_id={self.activity_id}>'

class CodeSubmission(db.Model):
    """Model for storing student code submissions"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('coding_activity.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False)
    success = db.Column(db.Boolean, default=False)
    output = db.Column(db.Text)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', back_populates='submissions')
    activity = db.relationship('CodingActivity', back_populates='submissions')

    def __repr__(self):
        return f'<CodeSubmission student_id={self.student_id} activity_id={self.activity_id}>'

class SharedCode(db.Model):
    """Model for sharing code snippets"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    language = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)

    student = db.relationship('Student', back_populates='shared_codes')

    def __repr__(self):
        return f'<SharedCode {self.title}>'

class AuditLog(db.Model):
    """Model for tracking changes to student records"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AuditLog user_id={self.user_id} action={self.action}>'