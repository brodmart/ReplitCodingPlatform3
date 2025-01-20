"""
Initialize models package and expose models
"""
from database import db
from .student import (
    Student,
    CodeSubmission,
    CodingActivity,
    StudentProgress,
    SharedCode,
    AuditLog
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
    'Course',
    'Strand', 
    'OverallExpectation',
    'SpecificExpectation'
]