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
from sqlalchemy import func
import time

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

@activities.before_request
@limiter.limit("60 per minute")
def limit_activities():
    """Rate limit all activity routes"""
    pass

@activities.route('/activities')
@activities.route('/activities/<int:grade>')
@activities.route('/activities/activities/<int:grade>')  # Add support for the duplicate 'activities' in URL
@cache.cached(timeout=300, unless=lambda: current_user.is_authenticated)
def list_activities(grade=None):
    """
    List all coding activities, grouped by curriculum and language.
    Includes progress tracking for authenticated users.
    """
    try:
        start_time = time.time()

        # Ensure grade is converted to integer and validate
        try:
            grade = int(grade) if grade is not None else 10  # Default to grade 10 if not specified
            if grade not in [10, 11]:
                logger.warning(f"Invalid grade provided: {grade}, defaulting to 10")
                grade = 10
        except (ValueError, TypeError):
            logger.warning(f"Invalid grade format: {grade}, defaulting to 10")
            grade = 10

        # Create a unique cache key for each user
        cache_key = f'activities_list_{current_user.id if current_user.is_authenticated else "anon"}_{grade}'
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Cache hit for activities list. Response time: {time.time() - start_time:.2f}s")
            return cached_data

        # Optimize query with load_only for required fields
        base_query = CodingActivity.query.options(
            db.load_only(
                CodingActivity.id, 
                CodingActivity.title,
                CodingActivity.description,
                CodingActivity.curriculum,
                CodingActivity.language,
                CodingActivity.difficulty,
                CodingActivity.points,
                CodingActivity.sequence
            )
        )

        if current_user.is_authenticated:
            # Use a single join with contains_eager for progress data
            base_query = base_query.outerjoin(
                StudentProgress,
                db.and_(
                    StudentProgress.activity_id == CodingActivity.id,
                    StudentProgress.student_id == current_user.id
                )
            ).options(
                db.contains_eager(CodingActivity.student_progress)
            )

        # Execute single optimized query with all needed data
        query_start = time.time()
        curriculum = 'ICS3U' if grade == 11 else 'TEJ2O'
        logger.debug(f"Filtering activities for curriculum: {curriculum} (grade {grade})")

        activities = base_query.filter(CodingActivity.curriculum == curriculum).order_by(
            CodingActivity.curriculum,
            CodingActivity.language,
            CodingActivity.sequence
        ).all()

        logger.debug(f"Found {len(activities)} activities for curriculum {curriculum}")
        logger.info(f"Database query time: {time.time() - query_start:.2f}s")

        # Process results in memory to avoid additional queries
        processing_start = time.time()
        grouped_activities = {}
        curriculum_progress = {}

        for activity in activities:
            key = (activity.curriculum, activity.language)
            logger.debug(f"Processing activity: {activity.title} for {key}")
            if key not in grouped_activities:
                grouped_activities[key] = []
            grouped_activities[key].append(activity)

            if current_user.is_authenticated:
                curriculum = activity.curriculum
                if curriculum not in curriculum_progress:
                    curriculum_progress[curriculum] = {
                        'completed': 0,
                        'total': 0,
                        'percentage': 0
                    }
                curriculum_progress[curriculum]['total'] += 1
                if activity.student_progress and activity.student_progress[0].completed:
                    curriculum_progress[curriculum]['completed'] += 1

        # Log grouped activities for debugging
        for key, activities_list in grouped_activities.items():
            logger.debug(f"Group {key}: {len(activities_list)} activities")

        # Calculate percentages after counting
        for stats in curriculum_progress.values():
            if stats['total'] > 0:
                stats['percentage'] = (stats['completed'] / stats['total'] * 100)

        logger.info(f"Data processing time: {time.time() - processing_start:.2f}s")

        # Render template
        render_start = time.time()
        rendered_template = render_template(
            'activities.html',
            grouped_activities=grouped_activities,
            curriculum_progress=curriculum_progress,
            grade=grade  # Make sure grade is passed to template
        )
        logger.info(f"Template rendering time: {time.time() - render_start:.2f}s")

        # Cache the result
        cache.set(cache_key, rendered_template, timeout=300)

        total_time = time.time() - start_time
        logger.info(f"Total response time: {total_time:.2f}s")

        return rendered_template

    except Exception as e:
        logger.error(f"Error in list_activities: {str(e)}")
        flash("Une erreur s'est produite lors du chargement des activités.", "error")
        return render_template('errors/500.html'), 500

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
        language = request.json.get('language', 'cpp').strip()
        logger.debug(f"Processing {language} code submission for activity {activity_id}")

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
                    language=language,
                    input_data=test_case.get('input')
                )

                if not result.get('success', False):
                    logger.warning(f"Test case failed: {result.get('error')}")
                    return jsonify({'error': result.get('error', 'Compilation or execution failed')}), 400

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
            with transaction_context():
                submission = save_code_submission(
                    student_id=current_user.id,
                    code=code,
                    language=language,
                    success=all_tests_passed,
                    output=str(test_results),
                    error=None if all_tests_passed else "Some tests failed"
                )
                logger.info(f"Saved submission {submission.id} for activity {activity_id}")

                # Update progress
                progress.attempts += 1
                progress.last_submission = code

                if all_tests_passed:
                    progress.completed = True
                    progress.completed_at = datetime.utcnow()
                    current_user.score += activity.points
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
        logger.error(f"Error in submit_activity {activity_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500