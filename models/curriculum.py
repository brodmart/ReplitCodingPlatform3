"""
Database models for Ontario Computer Science Curriculum (ICS3U)
Supports bilingual content and hierarchical structure
"""
from datetime import datetime
from sqlalchemy import CheckConstraint, Index
from app import db

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)  # e.g., "ICS3U"
    title_en = db.Column(db.String(255), nullable=False, server_default='')
    title_fr = db.Column(db.String(255), nullable=False, server_default='')
    description_en = db.Column(db.Text, nullable=False, server_default='')
    description_fr = db.Column(db.Text, nullable=False, server_default='')
    prerequisite_en = db.Column(db.String(255), nullable=False, server_default='')
    prerequisite_fr = db.Column(db.String(255), nullable=False, server_default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    strands = db.relationship('Strand', backref='course', lazy=True)

    __table_args__ = (
        CheckConstraint("title_en != '' AND title_fr != ''", name='check_course_titles'),
        Index('idx_course_code', 'code'),
    )

class Strand(db.Model):
    __tablename__ = 'strands'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    code = db.Column(db.String(5), nullable=False)  # e.g., "A", "B", "C"
    title_en = db.Column(db.String(255), nullable=False, server_default='')
    title_fr = db.Column(db.String(255), nullable=False, server_default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    overall_expectations = db.relationship('OverallExpectation', backref='strand', lazy=True)

    __table_args__ = (
        CheckConstraint("title_en != '' AND title_fr != ''", name='check_strand_titles'),
        Index('idx_strand_code', 'code'),
        Index('idx_strand_course', 'course_id', 'code'),
    )

class OverallExpectation(db.Model):
    __tablename__ = 'overall_expectations'
    id = db.Column(db.Integer, primary_key=True)
    strand_id = db.Column(db.Integer, db.ForeignKey('strands.id'), nullable=False)
    code = db.Column(db.String(10), nullable=False)  # e.g., "A1", "B2"
    description_en = db.Column(db.Text, nullable=False, server_default='')
    description_fr = db.Column(db.Text, nullable=False, server_default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    specific_expectations = db.relationship('SpecificExpectation', backref='overall_expectation', lazy=True)

    __table_args__ = (
        CheckConstraint("description_en != '' AND description_fr != ''", 
                       name='check_overall_descriptions'),
        Index('idx_overall_code', 'code'),
        Index('idx_overall_strand', 'strand_id', 'code'),
    )

class SpecificExpectation(db.Model):
    __tablename__ = 'specific_expectations'
    id = db.Column(db.Integer, primary_key=True)
    overall_expectation_id = db.Column(db.Integer, db.ForeignKey('overall_expectations.id'), nullable=False)
    code = db.Column(db.String(10), nullable=False)  # e.g., "A1.1", "B2.3"
    description_en = db.Column(db.Text, nullable=False, server_default='')
    description_fr = db.Column(db.Text, nullable=False, server_default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("description_en != '' AND description_fr != ''", 
                       name='check_specific_descriptions'),
        Index('idx_specific_code', 'code'),
        Index('idx_specific_overall', 'overall_expectation_id', 'code'),
    )