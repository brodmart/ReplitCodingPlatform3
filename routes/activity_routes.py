from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
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
@login_required
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        # Convert grade parameter to curriculum code
        curriculum = 'ICS3U' if grade == '11' else 'TEJ2O'
        logger.debug(f"Listing activities for curriculum: {curriculum}")

        # Query activities for the specified curriculum
        query = CodingActivity.query.filter_by(curriculum=curriculum).order_by(
            CodingActivity.sequence
        )

        activities_list = query.all()
        logger.debug(f"Found {len(activities_list)} activities")

        # Get progress for current user if authenticated
        progress = {}
        if current_user.is_authenticated:
            progress_records = StudentProgress.query.filter_by(
                student_id=current_user.id
            ).all()
            progress = {p.activity_id: p for p in progress_records}

        return render_template(
            'activities/list.html',
            activities=activities_list,
            progress=progress,
            curriculum=curriculum,
            grade=grade,
            lang=session.get('lang', 'fr')
        )
    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement des activités.", "danger")
        return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

@activities.route('/activity/<int:activity_id>')
@login_required
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)

        # Get progress for current user
        progress = None
        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id,
                activity_id=activity_id
            ).first()

        return render_template(
            'activities/view.html',
            activity=activity,
            progress=progress,
            lang=session.get('lang', 'fr')
        )
    except Exception as e:
        logger.error(f"Error viewing activity: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite.", "danger")
        return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    """Rate limit all activity routes"""
    pass