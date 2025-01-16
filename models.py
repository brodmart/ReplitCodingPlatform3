from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import text, event
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from database import db

logger = logging.getLogger(__name__)

class SoftDeleteMixin:
    """Mixin to add soft delete functionality"""
    deleted_at = db.Column(db.DateTime, nullable=True)

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    def restore(self):
        self.deleted_at = None
        db.session.commit()

    @classmethod
    def get_active(cls):
        return cls.query.filter_by(deleted_at=None)

class AuditLog(db.Model):
    """Model to track changes to content"""
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # INSERT, UPDATE, DELETE
    changes = db.Column(db.JSON)
    user_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('Student', backref=db.backref('audit_logs', lazy=True))

class Student(UserMixin, db.Model):
    """Student model representing a user in the system"""
    __table_args__ = (
        db.Index('idx_student_username', 'username'),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)  # Made email optional
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Added admin flag
    avatar_path = db.Column(db.String(256))  # Added avatar support

    # Security fields
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)  # Added nullable=False and default=0
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

class Achievement(db.Model):
    """Achievement model for tracking student accomplishments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    criteria = db.Column(db.String(200), nullable=False)
    badge_icon = db.Column(db.String(200))
    points = db.Column(db.Integer, default=10)
    category = db.Column(db.String(50), nullable=False, default='beginner')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_achievements = db.relationship('StudentAchievement', backref=db.backref('achievement', lazy=True))


class StudentAchievement(db.Model):
    """Junction model linking students with their achievements"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)


class CodeSubmission(db.Model):
    """Model for storing student code submissions"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    language = db.Column(db.String(20), nullable=False)
    code = db.Column(db.Text, nullable=False)
    success = db.Column(db.Boolean, default=False)
    output = db.Column(db.Text)
    error = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', back_populates='submissions', lazy=True)


class SharedCode(db.Model):
    """Model for code snippets shared by students"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)

    student = db.relationship('Student', back_populates='shared_codes', lazy=True)


class CodingActivity(SoftDeleteMixin, db.Model):
    """Model for coding exercises and activities"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    curriculum = db.Column(db.String(20), nullable=False)
    language = db.Column(db.String(20), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    starter_code = db.Column(db.Text)
    solution_code = db.Column(db.Text, nullable=False)
    test_cases = db.Column(db.JSON, nullable=False)
    hints = db.Column(db.JSON)
    common_errors = db.Column(db.JSON)
    incorrect_examples = db.Column(db.JSON)
    syntax_help = db.Column(db.Text)
    points = db.Column(db.Integer, default=10)
    max_attempts = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, default=1)  # Add version control

    student_progress = db.relationship('StudentProgress', back_populates='activity', lazy=True)

class StudentProgress(db.Model):
    """Model for tracking student progress through activities"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('coding_activity.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)
    last_submission = db.Column(db.Text)

    activity = db.relationship('CodingActivity', back_populates='student_progress', lazy=True)

def create_audit_log(mapper, connection, target):
    if hasattr(target, '__table__'):
        audit = AuditLog(
            table_name=target.__table__.name,
            record_id=target.id,
            action='INSERT',
            changes={'new_values': {c.name: getattr(target, c.name) for c in target.__table__.columns}},
            created_at=datetime.utcnow()
        )
        db.session.add(audit)

def update_audit_log(mapper, connection, target):
    if hasattr(target, '__table__'):
        audit = AuditLog(
            table_name=target.__table__.name,
            record_id=target.id,
            action='UPDATE',
            changes={
                'changed_fields': {
                    key: getattr(target, key)
                    for key in target.__dict__
                    if not key.startswith('_') and key != 'id'
                }
            },
            created_at=datetime.utcnow()
        )
        db.session.add(audit)

def delete_audit_log(mapper, connection, target):
    if hasattr(target, '__table__'):
        audit = AuditLog(
            table_name=target.__table__.name,
            record_id=target.id,
            action='DELETE',
            created_at=datetime.utcnow()
        )
        db.session.add(audit)

event.listen(CodingActivity, 'after_insert', create_audit_log)
event.listen(CodingActivity, 'after_update', update_audit_log)
event.listen(CodingActivity, 'after_delete', delete_audit_log)