"""
Activity routes with curriculum compliance integration
"""
from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import login_required, current_user
from utils.curriculum_checker import CurriculumChecker
from models import db, CodingActivity, Student, StudentProgress, CodeSubmission
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
activities_bp = Blueprint('activities', __name__)
curriculum_checker = CurriculumChecker()

@activities_bp.route('/activities')
@activities_bp.route('/activities/<grade>')
@login_required
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        logger.debug(f"Listing activities for grade: {grade}")

        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Using curriculum: {curriculum}, language: {language}")

        # Query activities without curriculum filter first to debug
        activities_list = CodingActivity.query.filter(
            CodingActivity.language == language,
            CodingActivity.deleted_at.is_(None)
        ).order_by(CodingActivity.sequence).all()

        logger.debug(f"Found {len(activities_list)} active activities")
        logger.debug(f"Activity details: {[{a.id: a.title} for a in activities_list]}")

        # Get student progress if available
        progress_data = {}
        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id
            ).all()
            progress_data = {p.activity_id: p for p in progress}

        return render_template(
            'activities/list.html',
            activities=activities_list,
            curriculum=curriculum,
            lang=request.args.get('lang', 'fr'),
            grade=grade,
            progress=progress_data
        )

    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading activities"
        }), 500

@activities_bp.route('/activity/<int:activity_id>')
@login_required
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        logger.debug(f"Viewing activity with ID: {activity_id}")

        activity = CodingActivity.query.get_or_404(activity_id)
        logger.debug(f"Found activity: {activity.title}")

        if activity.starter_code is None:
            activity.starter_code = ''

        # Get student progress if available
        progress = None
        if current_user.is_authenticated:
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
                db.session.commit()

        return render_template(
            'activities/view.html',
            activity=activity,
            lang=request.args.get('lang', 'fr'),
            progress=progress
        )

    except Exception as e:
        logger.error(f"Error viewing activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500

@activities_bp.route('/activity/enhanced/<int:activity_id>')
@login_required
def view_enhanced_activity(activity_id):
    """View an activity with enhanced learning features"""
    try:
        logger.debug(f"Viewing enhanced activity with ID: {activity_id}")

        activity = CodingActivity.query.get_or_404(activity_id)
        logger.debug(f"Found activity: {activity.title}")

        if activity.starter_code is None:
            activity.starter_code = ''

        # Get student progress if available
        progress = None
        if current_user.is_authenticated:
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
                db.session.commit()

        return render_template(
            'activity.html',  # This template includes enhanced features
            activity=activity,
            lang=request.args.get('lang', 'fr'),
            progress=progress,
            enhanced=True
        )

    except Exception as e:
        logger.error(f"Error viewing enhanced activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500