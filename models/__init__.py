"""
Initialize models package and expose models
"""
from app import db
from .student import (
    Student,
    CodeSubmission,
    CodingActivity,
    StudentProgress,
    SharedCode,
    AuditLog,
    Achievement,
    StudentAchievement
)
from .curriculum import (
    Course,
    Strand,
    OverallExpectation,
    SpecificExpectation
)

__all__ = [
    'db',
    'Student',
    'CodeSubmission', 
    'CodingActivity',
    'StudentProgress',
    'SharedCode',
    'AuditLog',
    'Achievement',
    'StudentAchievement',
    'Course',
    'Strand', 
    'OverallExpectation',
    'SpecificExpectation'
]