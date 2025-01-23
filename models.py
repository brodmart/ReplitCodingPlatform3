"""
Initialize models package and expose models
"""
from app import db
from models.student import (
    Student,
    CodeSubmission,
    CodingActivity,
    StudentProgress,
    SharedCode,
    AuditLog,
    Achievement,
    StudentAchievement
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
    'StudentAchievement'
]

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