from datetime import datetime
from flask_login import UserMixin
from database import db

class Student(UserMixin, db.Model):
    """Student model representing a user in the system"""
    __table_args__ = (
        db.Index('idx_student_username_email', 'username', 'email'),
    )
    # Basic user information
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))

    # Student progress tracking
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    achievements = db.relationship('StudentAchievement', backref='student')
    submissions = db.relationship('CodeSubmission', backref='student')
    progress = db.relationship('StudentProgress', backref='student')
    shared_codes = db.relationship('SharedCode', backref='student')

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

    student = db.relationship('Student', backref=db.backref('submissions', lazy=True))


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

    student = db.relationship('Student', backref=db.backref('shared_codes', lazy=True))


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

    student_progress = db.relationship('StudentProgress', backref=db.backref('activity', lazy=True))


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

    student = db.relationship('Student', backref=db.backref('progress', lazy=True))
    activity = db.relationship('CodingActivity', backref=db.backref('student_progress', lazy=True))