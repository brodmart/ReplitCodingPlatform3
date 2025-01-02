from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import current_user
from models import CodingActivity, StudentProgress, CodeSubmission
from database import db
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
        # Convert grade parameter to curriculum code
        curriculum = 'ICS3U' if grade == '11' else 'TEJ2O' if grade == '10' else 'TEJ2O'  # Default to TEJ2O
        logger.debug(f"Listing activities for curriculum: {curriculum}")

        # Build query based on curriculum
        query = CodingActivity.query.filter_by(curriculum=curriculum)

        # For TEJ2O, only show C++ activities
        if curriculum == 'TEJ2O':
            query = query.filter_by(language='cpp')

        # Order activities by sequence
        activities_list = query.order_by(CodingActivity.sequence).all()
        logger.debug(f"Found {len(activities_list)} activities for curriculum {curriculum}")

        # Group activities by curriculum and language
        grouped_activities = {}

        with db.session.no_autoflush:
            for activity in activities_list:
                key = (activity.curriculum, activity.language)
                if key not in grouped_activities:
                    grouped_activities[key] = []

                # Only fetch progress if user is authenticated
                if current_user.is_authenticated:
                    progress = StudentProgress.query.filter_by(
                        student_id=current_user.id,
                        activity_id=activity.id
                    ).first()
                    activity.student_progress = [progress] if progress else []
                else:
                    activity.student_progress = []

                grouped_activities[key].append(activity)

        logger.debug(f"Grouped activities: {len(grouped_activities)} curriculum-language pairs")
        return render_template(
            'activities.html',
            grouped_activities=grouped_activities,
            grade=grade,
            lang=session.get('lang', 'fr')
        )
    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        db.session.rollback()  # Rollback any failed transaction
        flash("Une erreur s'est produite lors du chargement des activités.", "danger")
        return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

@activities.route('/activity/<int:activity_id>')
@limiter.limit("30 per minute")
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)

        # Get progress for current user if authenticated
        progress = None
        if current_user.is_authenticated:
            with db.session.no_autoflush:
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
        db.session.rollback()  # Rollback any failed transaction
        flash("Une erreur s'est produite.", "danger")
        return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

@activities.before_request
def before_activities_request():
    """Log activity requests"""
    logger.debug(f"Activity route accessed: {request.endpoint}")