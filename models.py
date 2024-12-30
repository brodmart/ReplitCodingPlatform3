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

    # Relationships
    achievements = db.relationship('StudentAchievement', back_populates='student')
    submissions = db.relationship('CodeSubmission', back_populates='student')

    @property
    def successful_submissions(self):
        return len([s for s in self.submissions if s.success])

    @property
    def achievements_by_category(self):
        """Group achievements by category"""
        categories = {}
        for sa in self.achievements:
            category = sa.achievement.category
            if category not in categories:
                categories[category] = []
            categories[category].append(sa.achievement)
        return categories

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