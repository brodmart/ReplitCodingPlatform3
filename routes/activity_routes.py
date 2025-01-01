from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import CodingActivity, StudentProgress
from database import db
from datetime import datetime
from extensions import limiter, cache
from compiler_service import compile_and_run
import logging
import json

activities = Blueprint('activities', __name__)

def load_activity_metadata(activity_id: int) -> tuple[dict, dict]:
    """
    Load and parse hints and common errors for an activity.
    Returns a tuple of (hints, common_errors)
    """
    try:
        # Load common errors from JSON file if exists
        common_errors = []
        try:
            with open(f'activity/{activity_id}.json') as f:
                data = json.load(f)
                common_errors = data.get('common_errors', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        return common_errors
    except Exception as e:
        logging.error(f"Error loading activity metadata: {str(e)}")
        return []

def get_or_create_progress(student_id: int, activity_id: int) -> StudentProgress:
    """
    Get existing progress or create new progress entry for a student.
    """
    progress = StudentProgress.query.filter_by(
        student_id=student_id,
        activity_id=activity_id
    ).first()

    if not progress:
        progress = StudentProgress(
            student_id=student_id,
            activity_id=activity_id
        )
        db.session.add(progress)
        db.session.commit()

    return progress

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    pass

@activities.route('/activities')
@cache.memoize(timeout=300)  # Cache for 5 minutes
def list_activities():
    """
    List all coding activities, grouped by curriculum and language.
    Includes progress tracking for authenticated users.
    """
    try:
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
    except Exception as e:
        logging.error(f"Error in list_activities: {str(e)}")
        flash("Une erreur s'est produite lors du chargement des activités.", "error")
        return render_template('errors/500.html'), 500

@activities.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    """
    View a specific coding activity with student progress tracking.
    Handles loading activity metadata and user progress.
    """
    try:
        activity = CodingActivity.query.get_or_404(activity_id)

        # Load activity metadata
        activity.common_errors = load_activity_metadata(activity_id)

        # Get or initialize progress
        progress = None
        initial_code = activity.starter_code

        if current_user.is_authenticated:
            progress = get_or_create_progress(current_user.id, activity_id)

            # Use last submission if available
            if progress and progress.last_submission:
                initial_code = progress.last_submission

        # Ensure initial code is never None
        initial_code = initial_code or ''

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
    """
    Handle activity submission and testing.
    Updates progress and returns test results.
    """
    if request.method != 'POST':
        return redirect(url_for('activities.view_activity', activity_id=activity_id))

    activity = CodingActivity.query.get_or_404(activity_id)
    code = request.json.get('code', '')

    if not code:
        return jsonify({'error': 'Aucun code fourni'}), 400

    # Get or create progress
    progress = get_or_create_progress(current_user.id, activity_id)

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