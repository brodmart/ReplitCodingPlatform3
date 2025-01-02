from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import current_user, login_required
from models import CodingActivity, StudentProgress, CodeSubmission, db
from extensions import limiter, cache
import logging
from datetime import datetime
from sqlalchemy import func

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

@activities.route('/')
@activities.route('/<grade>')
@limiter.limit("30 per minute")
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        # Convert grade parameter to curriculum code and set language
        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Listing activities for curriculum: {curriculum}, language: {language}")

        # Build query with both curriculum and language filters
        query = CodingActivity.query.filter_by(
            curriculum=curriculum,
            language=language
        ).order_by(CodingActivity.sequence)

        activities_list = query.all()
        logger.debug(f"Found {len(activities_list)} activities")

        # Calculate progress if user is authenticated
        student_progress = {}
        completed_count = 0
        total_count = len(activities_list)

        if current_user.is_authenticated:
            for activity in activities_list:
                progress = StudentProgress.query.filter_by(
                    student_id=current_user.id,
                    activity_id=activity.id
                ).first()

                if progress:
                    student_progress[activity.id] = progress
                    if progress.completed:
                        completed_count += 1

        # Calculate completion percentage
        completion_percentage = (completed_count / total_count * 100) if total_count > 0 else 0

        return render_template(
            'activities.html',
            activities=activities_list,
            progress=student_progress,
            completed_count=completed_count,
            total_count=total_count,
            completion_percentage=completion_percentage,
            curriculum=curriculum,
            lang=session.get('lang', 'fr'),
            grade=grade
        )

    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement des activités.", "danger")
        return redirect(url_for('main.index'))

@activities.route('/activity/<int:activity_id>')
@limiter.limit("30 per minute")
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)

        # Get progress for current user if authenticated
        progress = None
        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id,
                activity_id=activity_id
            ).first()

        return render_template(
            'activity.html',
            activity=activity,
            progress=progress,
            initial_code=activity.starter_code,
            lang=session.get('lang', 'fr')
        )
    except Exception as e:
        logger.error(f"Error viewing activity: {str(e)}")
        flash("Une erreur s'est produite.", "danger")
        return redirect(url_for('activities.list_activities'))

@activities.before_request
def before_activities_request():
    """Log activity requests"""
    logger.debug(f"Activity route accessed: {request.endpoint}")