"""
Activity routes with curriculum compliance integration and enhanced learning features
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

@activities_bp.route('/activities/store_confidence', methods=['POST'])
@login_required
def store_confidence():
    """Store student's confidence level for an activity"""
    try:
        data = request.get_json()
        activity_id = data.get('activity_id')
        confidence_level = data.get('confidence_level')

        if not activity_id or not confidence_level:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        progress = StudentProgress.query.filter_by(
            student_id=current_user.id,
            activity_id=activity_id
        ).first()

        if not progress:
            progress = StudentProgress(
                student_id=current_user.id,
                activity_id=activity_id,
                confidence_level=confidence_level,
                started_at=datetime.utcnow()
            )
            db.session.add(progress)
        else:
            progress.confidence_level = confidence_level

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error storing confidence level: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@activities_bp.route('/activities/get_solutions/<int:activity_id>')
@login_required
def get_solutions(activity_id):
    """Get solution approaches for comparison"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)
        solutions = [
            {
                'approach_description': 'Iterative approach using loops',
                'efficiency_score': '85%',
                'memory_usage': '2.5'
            },
            {
                'approach_description': 'Recursive solution with memoization',
                'efficiency_score': '92%',
                'memory_usage': '3.8'
            }
        ]
        return jsonify(solutions)
    except Exception as e:
        logger.error(f"Error fetching solutions: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to fetch solutions'}), 500

@activities_bp.route('/activities/run_code', methods=['POST'])
@login_required
def run_code():
    """Execute student code submission"""
    try:
        data = request.get_json()
        code = data.get('code')
        activity_id = data.get('activity_id')
        language = data.get('language', 'cpp')

        if not code or not activity_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Store code submission
        submission = CodeSubmission(
            student_id=current_user.id,
            activity_id=activity_id,
            code=code,
            submitted_at=datetime.utcnow()
        )
        db.session.add(submission)
        db.session.commit()

        # Mock execution result for now
        result = {
            'success': True,
            'output': 'Program executed successfully.\nOutput: Hello, World!'
        }
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error running code: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@activities_bp.route('/activities')
@activities_bp.route('/activities/<grade>')
@login_required
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        logger.debug(f"Listing activities for grade: {grade}")
        logger.debug(f"Current user: {current_user.id if current_user.is_authenticated else 'Not authenticated'}")

        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Using curriculum: {curriculum}, language: {language}")

        # Query activities with explicit filters
        activities_list = CodingActivity.query.filter(
            CodingActivity.curriculum == curriculum,
            CodingActivity.language == language,
            CodingActivity.deleted_at.is_(None)  # Explicitly check for null deleted_at
        ).order_by(CodingActivity.sequence).all()

        logger.debug(f"Found {len(activities_list)} active activities")
        for activity in activities_list:
            logger.debug(f"Activity: {activity.id} - {activity.title} - {activity.curriculum}")

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
            'activities/enhanced_learning.html',  # Using the enhanced template
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