from datetime import datetime, timedelta
from flask_login import UserMixin
from database import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
import secrets

class Student(UserMixin, db.Model):
    """Student model representing a user in the system"""
    __table_args__ = (
        db.Index('idx_student_username_email', 'username', 'email'),
    )

    # Basic user information
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Security fields
    failed_login_attempts = db.Column(db.Integer, default=0)
    last_failed_login = db.Column(db.DateTime)
    account_locked_until = db.Column(db.DateTime)
    last_password_change = db.Column(db.DateTime, default=datetime.utcnow)
    session_token = db.Column(db.String(64), unique=True)

    # Student progress tracking
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    achievements = db.relationship('StudentAchievement', backref='student')
    submissions = db.relationship('CodeSubmission', back_populates='student')
    progress = db.relationship('StudentProgress', backref='student')
    shared_codes = db.relationship('SharedCode', back_populates='student')

    @property
    def successful_submissions(self):
        """Get the count of successful code submissions"""
        return CodeSubmission.query.filter_by(
            student_id=self.id,
            success=True
        ).count()

    @property
    def current_activity(self):
        """Get the student's current activity based on their progress"""
        completed_activities = set(p.activity_id for p in self.progress if p.completed)
        return CodingActivity.query.filter(
            ~CodingActivity.id.in_(completed_activities)
        ).order_by(CodingActivity.sequence).first()

    def set_password(self, password):
        """Hash password using Werkzeug's implementation"""
        self.password_hash = generate_password_hash(password)
        self.last_password_change = datetime.utcnow()

    def check_password(self, password):
        """Verify password hash"""
        return check_password_hash(self.password_hash, password)

    def increment_failed_login(self):
        """Track failed login attempts"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()
        if self.failed_login_attempts >= 5:
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

    def reset_failed_login(self):
        """Reset failed login counter"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.account_locked_until = None

    def generate_session_token(self):
        """Generate a new session token"""
        self.session_token = secrets.token_urlsafe(48)
        return self.session_token

    def is_account_locked(self):
        """Check if account is temporarily locked"""
        if self.account_locked_until and self.account_locked_until > datetime.utcnow():
            return True
        return False

    @staticmethod
    def get_by_email(email):
        """Safely get user by email using parameterized query"""
        return Student.query.filter(Student.email == email).first()


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

    student = db.relationship('Student', back_populates='submissions')


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

    student = db.relationship('Student', back_populates='shared_codes')


class CodingActivity(db.Model):
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

    student_progress = db.relationship('StudentProgress', back_populates='activity')


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

    activity = db.relationship('CodingActivity', back_populates='student_progress')