from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import CodingActivity, StudentProgress
from database import db
from datetime import datetime
from extensions import limiter
from app import cache

activities = Blueprint('activities', __name__)

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    pass
from compiler_service import compile_and_run
import logging
import json

activities = Blueprint('activities', __name__)

@activities.route('/activities')
@cache.memoize(timeout=300)  # Cache for 5 minutes
def list_activities():
    """List all coding activities, grouped by curriculum and language"""
    activities = CodingActivity.query.order_by(
        CodingActivity.curriculum,
        CodingActivity.language,
        CodingActivity.sequence
    ).all()

    # Group activities by curriculum and language
    grouped_activities = {}
    for activity in activities:
        key = (activity.curriculum, activity.language)
        if key not in grouped_activities:
            grouped_activities[key] = []
        grouped_activities[key].append(activity)

    # Get student progress if logged in
    progress = {}
    curriculum_progress = {}

    if current_user.is_authenticated:
        # Get all progress entries
        student_progress = StudentProgress.query.filter_by(student_id=current_user.id).all()
        progress = {p.activity_id: p for p in student_progress}

        # Calculate curriculum progress
        for curriculum in ['TEJ2O', 'ICS3U']:
            curriculum_activities = CodingActivity.query.filter_by(curriculum=curriculum).all()
            total = len(curriculum_activities)

            if total > 0:
                completed = StudentProgress.query.filter(
                    StudentProgress.student_id == current_user.id,
                    StudentProgress.activity_id.in_([a.id for a in curriculum_activities]),
                    StudentProgress.completed == True
                ).count()

                curriculum_progress[curriculum] = {
                    'completed': completed,
                    'total': total,
                    'percentage': (completed / total * 100)
                }

    return render_template(
        'activities.html',
        grouped_activities=grouped_activities,
        progress=progress,
        curriculum_progress=curriculum_progress
    )

@activities.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)

        # Add debug logging for initial data
        logging.debug(f"Activity {activity_id} data:")
        logging.debug(f"Raw hints: {activity.hints}")
        logging.debug(f"Raw common_errors: {activity.common_errors}")
        logging.debug(f"Type of common_errors: {type(activity.common_errors)}")

        # Get student's progress for this activity
        progress = None
        initial_code = activity.starter_code

        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id,
                activity_id=activity_id
            ).first()

            # If there's a last submission, use that as initial code
            if progress and progress.last_submission:
                initial_code = progress.last_submission

            # Create progress entry if it doesn't exist
            if not progress:
                progress = StudentProgress(
                    student_id=current_user.id,
                    activity_id=activity_id
                )
                db.session.add(progress)
                db.session.commit()

        # If no initial code is set, use the starter code or empty string
        if not initial_code:
            initial_code = activity.starter_code or ''

        # Parse JSON fields if they exist
        try:
            # Handle hints
            if activity.hints:
                if isinstance(activity.hints, str):
                    activity.hints = json.loads(activity.hints)
                elif not isinstance(activity.hints, list):
                    activity.hints = []
            else:
                activity.hints = []

            logging.debug(f"Parsed hints: {activity.hints}")

            # Handle common errors
            if activity.common_errors is None:
                # Load from JSON file if exists
                try:
                    with open(f'activity/{activity.id}.json') as f:
                        data = json.load(f)
                        activity.common_errors = data.get('common_errors', [])
                except (FileNotFoundError, json.JSONDecodeError):
                    activity.common_errors = []
            elif isinstance(activity.common_errors, str):
                activity.common_errors = json.loads(activity.common_errors)
            elif not isinstance(activity.common_errors, list):
                activity.common_errors = []

            logging.debug(f"Parsed common_errors: {activity.common_errors}")
            logging.debug(f"Final type of common_errors: {type(activity.common_errors)}")

        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"JSON parsing error: {str(e)}")
            activity.hints = []
            activity.common_errors = []

        return render_template(
            'activity.html',
            activity=activity,
            progress=progress,
            initial_code=initial_code
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in view_activity: {str(e)}")
        return render_template('errors/500.html'), 500

@activities.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def submit_activity(activity_id):
    if request.method != 'POST':
        return redirect(url_for('activities.view_activity', activity_id=activity_id))
    """Submit a solution for a coding activity"""
    activity = CodingActivity.query.get_or_404(activity_id)
    code = request.json.get('code', '')

    if not code:
        return jsonify({'error': 'Aucun code fourni'}), 400

    # Get or create progress
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id,
        activity_id=activity_id
    ).first()

    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            activity_id=activity_id
        )
        db.session.add(progress)

    # Update progress
    progress.attempts += 1
    progress.last_submission = code

    # Execute code against test cases
    all_tests_passed = True
    test_results = []

    for test_case in activity.test_cases:
        result = compile_and_run(
            code=code,
            language=activity.language,
            input_data=test_case.get('input')
        )

        test_passed = (
            result.get('success', False) and
            result.get('output', '').strip() == str(test_case.get('output')).strip()
        )

        test_results.append({
            'input': test_case.get('input'),
            'expected': test_case.get('output'),
            'actual': result.get('output'),
            'passed': test_passed,
            'error': result.get('error')
        })

        if not test_passed:
            all_tests_passed = False

    # Update progress if all tests passed
    if all_tests_passed:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
        
        # Update user score
        current_user.score += activity.points
        
        # Track completion time
        time_taken = (datetime.utcnow() - progress.started_at).total_seconds()
        progress.completion_time = time_taken
        
        flash(f'Félicitations! Vous avez terminé "{activity.title}"! (+{activity.points} points)')

    db.session.commit()

    return jsonify({
        'success': all_tests_passed,
        'test_results': test_results,
        'attempts': progress.attempts
    })