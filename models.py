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

from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import text, event
from werkzeug.security import generate_password_hash, check_password_hash
import logging

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