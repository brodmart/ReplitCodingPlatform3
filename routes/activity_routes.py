from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import CodingActivity, StudentProgress, CodeSubmission
from database import db, transaction_context
from datetime import datetime
from extensions import limiter, cache
from compiler_service import compile_and_run, CompilerError, ExecutionError
import logging
import json
from typing import Optional, Dict, Any

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

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

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    """Rate limit all activity routes"""
    pass

@activities.route('/activities')
@cache.memoize(timeout=300)
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

        grouped_activities = {}
        for activity in activities:
            key = (activity.curriculum, activity.language)
            if key not in grouped_activities:
                grouped_activities[key] = []
            grouped_activities[key].append(activity)

        progress = {}
        curriculum_progress = {}

        if current_user.is_authenticated:
            with transaction_context():
                student_progress = StudentProgress.query.filter_by(
                    student_id=current_user.id
                ).all()
                progress = {p.activity_id: p for p in student_progress}

                for curriculum in ['TEJ2O', 'ICS3U']:
                    curriculum_activities = CodingActivity.query.filter_by(
                        curriculum=curriculum
                    ).all()
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
        logger.error(f"Error in list_activities: {str(e)}")
        flash("Une erreur s'est produite lors du chargement des activités.", "error")
        return render_template('errors/500.html'), 500

@activities.route('/activity/<int:activity_id>')
def view_activity(activity_id: int):
    """
    View a specific coding activity with student progress tracking.
    Handles loading activity metadata and user progress.
    """
    try:
        activity = CodingActivity.query.get_or_404(activity_id)
        metadata = validate_activity_metadata(activity_id)

        if metadata:
            activity.common_errors = metadata.get('common_errors', [])
        else:
            activity.common_errors = []

        progress = None
        initial_code = activity.starter_code

        if current_user.is_authenticated:
            progress = get_or_create_progress(current_user.id, activity_id)
            if progress and progress.last_submission:
                initial_code = progress.last_submission

        initial_code = initial_code or ''

        return render_template(
            'activity.html',
            activity=activity,
            progress=progress,
            initial_code=initial_code
        )
    except Exception as e:
        logger.error(f"Error in view_activity: {str(e)}")
        return render_template('errors/500.html'), 500

@activities.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def submit_activity(activity_id: int):
    """
    Handle activity submission and testing with proper error handling
    and transaction management.
    """
    try:
        logger.info(f"Received submission for activity {activity_id}")
        if not request.is_json:
            logger.warning("Invalid request: Content-Type must be application/json")
            return jsonify({'error': 'Content-Type must be application/json'}), 400

        activity = CodingActivity.query.get_or_404(activity_id)
        code = request.json.get('code', '').strip()
        logger.debug(f"Processing code submission for activity {activity_id}")

        if not code:
            logger.warning("Empty code submission")
            return jsonify({'error': 'Code submission cannot be empty'}), 400

        progress = get_or_create_progress(current_user.id, activity_id)
        all_tests_passed = True
        test_results = []

        try:
            for test_case in activity.test_cases:
                logger.debug(f"Running test case for activity {activity_id}")
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

            # Save submission
            submission = save_code_submission(
                student_id=current_user.id,
                code=code,
                language=activity.language,
                success=all_tests_passed,
                output=str(test_results),
                error=None if all_tests_passed else "Some tests failed"
            )
            logger.info(f"Saved submission {submission.id} for activity {activity_id}")

            # Update progress
            with transaction_context():
                progress.attempts += 1
                progress.last_submission = code

                if all_tests_passed:
                    progress.completed = True
                    progress.completed_at = datetime.utcnow()
                    current_user.score += activity.points

                    time_taken = (datetime.utcnow() - progress.started_at).total_seconds()
                    progress.completion_time = time_taken

                    flash(f'Félicitations! Vous avez terminé "{activity.title}"! (+{activity.points} points)')

            response_data = {
                'success': all_tests_passed,
                'test_results': test_results,
                'attempts': progress.attempts
            }
            logger.info(f"Successfully processed submission for activity {activity_id}")
            return jsonify(response_data)

        except (CompilerError, ExecutionError) as e:
            error_msg = str(e)
            logger.warning(f"Code execution error in activity {activity_id}: {error_msg}")
            return jsonify({'error': error_msg}), 400

        except Exception as e:
            logger.error(f"Error executing code in activity {activity_id}: {str(e)}")
            return jsonify({'error': 'Error executing code'}), 500

    except Exception as e:
        logger.error(f"Error in submit_activity {activity_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500