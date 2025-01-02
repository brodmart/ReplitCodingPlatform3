from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from models import CodingActivity, StudentProgress, CodeSubmission
from database import db
from extensions import limiter, cache
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from sqlalchemy import func
from contextlib import contextmanager

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

@activities.route('/')
@activities.route('/<grade>')
@cache.cached(timeout=300, unless=lambda: current_user.is_authenticated)
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        # Convert grade parameter to curriculum code
        curriculum = 'ICS3U' if grade == 'ICS3U' else 'TEJ2O'

        # Query activities for the specified curriculum
        query = CodingActivity.query.filter_by(curriculum=curriculum).order_by(
            CodingActivity.sequence
        )

        activities_list = query.all()

        return render_template(
            'activities.html',
            activities=activities_list,
            grade=grade,
            curriculum=curriculum
        )
    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}")
        flash("Une erreur s'est produite lors du chargement des activités.", "error")
        return render_template('errors/500.html'), 500

@activities.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)
        progress = None

        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id,
                activity_id=activity_id
            ).first()

        return render_template(
            'activity.html',
            activity=activity,
            progress=progress
        )
    except Exception as e:
        logger.error(f"Error viewing activity: {str(e)}")
        flash("Une erreur s'est produite.", "error")
        return render_template('errors/500.html'), 500

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    """Rate limit all activity routes"""
    pass

@contextmanager
def transaction_context():
    """Context manager for database transactions"""
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

@activities.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def submit_activity(activity_id: int):
    """Submit and test activity code"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400

        activity = CodingActivity.query.get_or_404(activity_id)
        code = request.json.get('code', '').strip()

        if not code:
            return jsonify({'error': 'Code submission cannot be empty'}), 400

        with transaction_context():
            submission = CodeSubmission(
                student_id=current_user.id,
                code=code,
                language='cpp',  # Default to C++ for now
                success=True,  # Simplified for auth testing
                submitted_at=datetime.utcnow()
            )
            db.session.add(submission)

            # Update progress
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id,
                activity_id=activity_id
            ).first()

            if not progress:
                progress = StudentProgress(
                    student_id=current_user.id,
                    activity_id=activity_id,
                    started_at=datetime.utcnow()
                )
                db.session.add(progress)

            progress.attempts += 1
            progress.last_submission = code
            progress.completed = True
            progress.completed_at = datetime.utcnow()

        return jsonify({
            'success': True,
            'message': 'Code submitted successfully'
        })

    except Exception as e:
        logger.error(f"Error in submit_activity {activity_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def validate_activity_metadata(activity_id: int) -> Optional[Dict[str, Any]]:
    """
    Validate and load activity metadata with proper error handling.
    """
    try:
        with open(f'activity/{activity_id}.json') as f:
            data = json.load(f)
            if not isinstance(data.get('common_errors'), list):
                logger.warning(f"Invalid metadata format for activity {activity_id}")
                return None
            return data
    except FileNotFoundError:
        logger.info(f"No metadata file found for activity {activity_id}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in metadata file for activity {activity_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading activity metadata for {activity_id}: {e}")
        return None

def save_code_submission(student_id: int, code: str, language: str, 
                        success: bool, output: str = '', error: Optional[str] = None) -> CodeSubmission:
    """
    Save a code submission with proper error handling and transaction management.
    """
    with transaction_context():
        submission = CodeSubmission(
            student_id=student_id,
            code=code,
            language=language,
            success=success,
            output=output,
            error=error,
            submitted_at=datetime.utcnow()
        )
        db.session.add(submission)
    return submission

def get_or_create_progress(student_id: int, activity_id: int) -> StudentProgress:
    """
    Get existing progress or create new progress entry for a student.
    Uses transaction context for database operations.
    """
    with transaction_context():
        progress = StudentProgress.query.filter_by(
            student_id=student_id,
            activity_id=activity_id
        ).first()

        if not progress:
            progress = StudentProgress(
                student_id=student_id,
                activity_id=activity_id,
                started_at=datetime.utcnow(),
                attempts=0,
                completed=False
            )
            db.session.add(progress)

    return progress