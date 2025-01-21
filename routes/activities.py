"""
Activity routes with curriculum compliance integration and enhanced learning features
"""
from flask import Blueprint, jsonify, request, render_template, abort, session, current_app
from flask_login import login_required, current_user
from utils.curriculum_checker import CurriculumChecker
from models import db, CodingActivity, Student, StudentProgress, CodeSubmission
import logging
from datetime import datetime
from compiler import compile_and_run

logger = logging.getLogger(__name__)
activities_bp = Blueprint('activities', __name__)
curriculum_checker = CurriculumChecker()

@activities_bp.route('/activities/execute', methods=['POST'])
@login_required
def execute_code():
    """Execute submitted code with enhanced error handling"""
    try:
        if not request.is_json:
            logger.error("Invalid request format - not JSON")
            return jsonify({
                'success': False,
                'error': 'Invalid request format'
            }), 400

        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()
        input_data = data.get('input')  # Add support for input data

        if not code:
            logger.error("Empty code submitted")
            return jsonify({
                'success': False,
                'error': 'Code cannot be empty'
            }), 400

        if language not in ['cpp', 'csharp']:
            logger.error(f"Unsupported language: {language}")
            return jsonify({
                'success': False,
                'error': 'Unsupported language'
            }), 400

        logger.debug(f"Executing {language} code of length {len(code)}")
        logger.debug(f"Code content:\n{code}")

        # Execute the code using the compiler service with input data
        result = compile_and_run(code, language, input_data)
        logger.debug(f"Execution result: {result}")

        if not result.get('success', False):
            error_msg = result.get('error', 'An error occurred')
            if 'memory' in error_msg.lower():
                error_msg += ". Try reducing the size of variables or arrays."
            elif 'timeout' in error_msg.lower():
                error_msg += ". Check for infinite loops."
            result['error'] = error_msg
            logger.error(f"Execution failed: {error_msg}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error executing code: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"An error occurred while executing your code: {str(e)}"
        }), 500

@activities_bp.route('/activities/run_code', methods=['POST'])
@login_required
def run_code():
    """Execute student code submission with activity tracking"""
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data in request")
            return jsonify({'success': False, 'error': 'Missing request data'}), 400

        code = data.get('code')
        activity_id = data.get('activity_id')
        language = data.get('language', 'cpp')

        if not code:
            logger.error("No code provided in request")
            return jsonify({'success': False, 'error': 'Code cannot be empty'}), 400

        # Execute the code
        logger.debug(f"Executing {language} code for activity {activity_id}")
        result = compile_and_run(code, language)
        logger.debug(f"Execution result: {result}")

        # Only store submission if activity_id is provided
        if activity_id:
            try:
                submission = CodeSubmission(
                    student_id=current_user.id,
                    activity_id=activity_id,
                    code=code,
                    language=language,
                    success=result.get('success', False),
                    output=result.get('output', ''),
                    error=result.get('error', ''),
                    submitted_at=datetime.utcnow()
                )
                db.session.add(submission)
                db.session.commit()
                logger.info(f"Stored submission for activity {activity_id}")
            except Exception as e:
                logger.error(f"Failed to store submission: {str(e)}")
                # Continue with execution result even if storage fails
                pass

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error running code: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_user_language():
    """Get user's current language preference"""
    current_lang = session.get('lang', current_app.config.get('DEFAULT_LANGUAGE', 'fr'))
    logger.debug(f"Activities - get_user_language called - current_lang: {current_lang}, session id: {id(session)}")
    return current_lang

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


@activities_bp.route('/activities')
@activities_bp.route('/activities/<grade>')
@login_required
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        logger.debug(f"Listing activities for grade: {grade}")
        logger.debug(f"Current user: {current_user.id if current_user.is_authenticated else 'Not authenticated'}")
        logger.debug(f"Current session lang: {session.get('lang')}")

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

        # Get student progress if available
        progress_data = {}
        if current_user.is_authenticated:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id
            ).all()
            progress_data = {p.activity_id: p for p in progress}

        current_lang = get_user_language()
        logger.debug(f"Rendering activities list with language: {current_lang}")

        return render_template(
            'activities/list.html',
            activities=activities_list,
            curriculum=curriculum,
            lang=current_lang,
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
        current_lang = get_user_language()
        logger.debug(f"Current language for activity view: {current_lang}")

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
            lang=current_lang,
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
        current_lang = get_user_language()
        logger.debug(f"Current language for enhanced activity view: {current_lang}")

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
            'activities/enhanced_learning.html',
            activity=activity,
            lang=current_lang,
            progress=progress,
            enhanced=True
        )

    except Exception as e:
        logger.error(f"Error viewing enhanced activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500