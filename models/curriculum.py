"""
Database models for Ontario Computer Science Curriculum (ICS3U)
Supports bilingual content and hierarchical structure
"""
from app import db
from datetime import datetime

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)  # e.g., "ICS3U"
    title_en = db.Column(db.String(255), nullable=False)
    title_fr = db.Column(db.String(255), nullable=False)
    description_en = db.Column(db.Text)
    description_fr = db.Column(db.Text)
    prerequisite_en = db.Column(db.String(255))
    prerequisite_fr = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    strands = db.relationship('Strand', backref='course', lazy=True)

class Strand(db.Model):
    __tablename__ = 'strands'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    code = db.Column(db.String(5), nullable=False)  # e.g., "A", "B", "C"
    title_en = db.Column(db.String(255), nullable=False)
    title_fr = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    overall_expectations = db.relationship('OverallExpectation', backref='strand', lazy=True)

class OverallExpectation(db.Model):
    __tablename__ = 'overall_expectations'
    id = db.Column(db.Integer, primary_key=True)
    strand_id = db.Column(db.Integer, db.ForeignKey('strands.id'), nullable=False)
    code = db.Column(db.String(10), nullable=False)  # e.g., "A1", "B2"
    description_en = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    specific_expectations = db.relationship('SpecificExpectation', backref='overall_expectation', lazy=True)

class SpecificExpectation(db.Model):
    __tablename__ = 'specific_expectations'
    id = db.Column(db.Integer, primary_key=True)
    overall_expectation_id = db.Column(db.Integer, db.ForeignKey('overall_expectations.id'), nullable=False)
    code = db.Column(db.String(10), nullable=False)  # e.g., "A1.1", "B2.3"
    description_en = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
