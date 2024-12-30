from database import db
from datetime import datetime
from flask_login import UserMixin

class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    shared_codes = db.relationship('SharedCode', back_populates='student')

    # Relationships
    achievements = db.relationship('StudentAchievement', back_populates='student')
    submissions = db.relationship('CodeSubmission', back_populates='student')
    progress = db.relationship('StudentProgress', back_populates='student')

    @property
    def current_activity(self):
        """Get the student's current activity based on their progress"""
        completed_activities = set(p.activity_id for p in self.progress if p.completed)
        next_activity = CodingActivity.query.filter(
            ~CodingActivity.id.in_(completed_activities)
        ).order_by(CodingActivity.sequence).first()
        return next_activity

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    criteria = db.Column(db.String(200), nullable=False)
    badge_icon = db.Column(db.String(200))
    points = db.Column(db.Integer, default=10)
    category = db.Column(db.String(50), nullable=False, default='beginner')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student_achievements = db.relationship('StudentAchievement', back_populates='achievement')

class StudentAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', back_populates='achievements')
    achievement = db.relationship('Achievement', back_populates='student_achievements')

class CodeSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    language = db.Column(db.String(20), nullable=False)
    code = db.Column(db.Text, nullable=False)
    success = db.Column(db.Boolean, default=False)
    output = db.Column(db.Text)
    error = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', back_populates='submissions')

class SharedCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)

    # Relationships
    student = db.relationship('Student', back_populates='shared_codes')

class CodingActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # beginner, intermediate, advanced
    curriculum = db.Column(db.String(20), nullable=False)  # TEJ2O or ICS3U
    language = db.Column(db.String(20), nullable=False)    # cpp or csharp
    sequence = db.Column(db.Integer, nullable=False)       # Order in curriculum
    instructions = db.Column(db.Text, nullable=False)
    starter_code = db.Column(db.Text)
    solution_code = db.Column(db.Text, nullable=False)
    test_cases = db.Column(db.JSON, nullable=False)        # JSON array of input/output pairs
    hints = db.Column(db.JSON)                            # Optional hints for students
    points = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student_progress = db.relationship('StudentProgress', back_populates='activity')

class StudentProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('coding_activity.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)
    last_submission = db.Column(db.Text)

    # Relationships
    student = db.relationship('Student', back_populates='progress')
    activity = db.relationship('CodingActivity', back_populates='student_progress')