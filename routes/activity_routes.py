"""
Activity routes with curriculum compliance integration and enhanced learning features
"""
import os
import logging
import time
from flask import Blueprint, render_template, request, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import RequestTimeout
from database import db
from models import CodingActivity, StudentProgress, CodeSubmission
from extensions import limiter
from datetime import datetime
from routes.static_routes import get_user_language
from compiler import compile_and_run
from flask import make_response

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Create temp directory
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.chmod(TEMP_DIR, 0o755)

def json_login_required(f):
    """Decorator to require login and return JSON response"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'auth_required': True
            }), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@activities.route('/activities/submit_confidence', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def submit_confidence():
    """Store student's confidence prediction for an activity"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        activity_id = data.get('activity_id')
        confidence_level = data.get('confidence_level')

        if not activity_id or not confidence_level:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Store confidence prediction in student progress
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
        logger.error(f"Error storing confidence: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@activities.route('/activities/fetch_solutions/<int:activity_id>')
@login_required
@limiter.limit("30 per minute")
def fetch_solutions(activity_id):
    """Get different solution approaches for comparison"""
    try:
        # Get successful submissions for this activity
        submissions = CodeSubmission.query.filter_by(
            activity_id=activity_id,
            success=True
        ).distinct(CodeSubmission.solution_pattern).limit(3).all()

        solutions = []
        for submission in submissions:
            solutions.append({
                'code': submission.code,
                'efficiency_score': submission.efficiency_score,
                'memory_usage': submission.memory_usage,
                'approach_description': submission.approach_description
            })

        return jsonify(solutions)

    except Exception as e:
        logger.error(f"Error getting solutions: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@activities.route('/activities/run_code', methods=['POST'])
@json_login_required
def run_code():
    """Execute student code submission with activity tracking"""
    try:
        if not request.is_json:
            logger.error("Invalid request format - not JSON")
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        if not data:
            logger.error("Empty request data")
            return jsonify({'success': False, 'error': 'Missing request data'}), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()
        activity_id = data.get('activity_id')

        if not code:
            logger.error("No code provided in request")
            return jsonify({'success': False, 'error': 'Code cannot be empty'}), 400

        # Normalize language name
        if language in ['c#', 'csharp', 'cs']:
            language = 'csharp'
        elif language in ['c++', 'cpp']:
            language = 'cpp'

        logger.debug(f"Executing {language} code, length: {len(code)}")
        logger.debug(f"Code preview: {code[:200]}...")

        # Execute the code using the compiler implementation
        result = compile_and_run(
            code=code,
            language=language,
            input_data=None
        )

        # Ensure result is properly formatted
        if not isinstance(result, dict):
            logger.error(f"Invalid result type from compile_and_run: {type(result)}")
            return jsonify({
                'success': False,
                'error': 'Internal server error: Invalid compiler response'
            }), 500

        response = jsonify(result)
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger.error(f"Error running code: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/get_output', methods=['GET'])
def get_session_output():
    """Get output from a running interactive program"""
    session_id = request.args.get('session_id')
    logger.debug(f"Getting output for session {session_id}")

    if not session_id:
        return jsonify({'success': False, 'error': 'No session ID provided'}), 400

    try:
        result = get_output(session_id)
        if not result['success']:
            cleanup_session(session_id)
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting output: {str(e)}", exc_info=True)
        cleanup_session(session_id)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/send_input', methods=['POST'])
def send_session_input():
    """Send input to a running interactive program"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        session_id = data.get('session_id')
        input_text = data.get('input', '')

        if not session_id:
            return jsonify({'success': False, 'error': 'No session ID provided'}), 400

        result = send_input(session_id, input_text)
        if not result['success']:
            cleanup_session(session_id)
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error sending input: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/activities')
@activities.route('/activities/<grade>')
@login_required
@limiter.limit("30 per minute")
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        logger.debug(f"Listing activities for grade: {grade}")
        logger.debug(f"Current user: {current_user.id}")

        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Using curriculum: {curriculum}, language: {language}")

        try:
            # Query activities with proper filters
            activities_list = CodingActivity.query.filter(
                CodingActivity.curriculum == curriculum,
                CodingActivity.language == language,
                CodingActivity.deleted_at == None  # Using == None for SQLAlchemy
            ).order_by(CodingActivity.sequence).all()

            logger.debug(f"Found {len(activities_list)} active activities")
            for activity in activities_list:
                logger.debug(f"Activity: {activity.id} - {activity.title} - {activity.curriculum}")

            return render_template(
                'activities/list.html',
                activities=activities_list,
                curriculum=curriculum,
                lang=get_user_language(),  # Use the centralized function
                grade=grade
            )

        except Exception as db_error:
            logger.error(f"Database error in list_activities: {str(db_error)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        response = jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading activities"
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@activities.route('/activity/<int:activity_id>')
@login_required
@limiter.limit("30 per minute")
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        logger.debug(f"Viewing activity with ID: {activity_id}")

        # Get activity with explicit loading of starter_code
        activity = CodingActivity.query.filter_by(id=activity_id).first_or_404()
        logger.debug(f"Found activity: {activity.title}")
        logger.debug(f"Activity language: {activity.language}")
        logger.debug(f"Activity starter code type: {type(activity.starter_code)}")
        logger.debug(f"Raw starter code from database: {repr(activity.starter_code)}")

        if activity.starter_code is None:
            logger.error(f"Activity {activity_id} has no starter code")
            activity.starter_code = ''  # Provide empty default
        elif not isinstance(activity.starter_code, str):
            logger.error(f"Activity {activity_id} has invalid starter code type: {type(activity.starter_code)}")
            activity.starter_code = str(activity.starter_code)  # Convert to string

        return render_template(
            'activities/view.html',
            activity=activity,
            lang=get_user_language()  # Use the centralized function
        )

    except Exception as e:
        logger.error(f"Error viewing activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500


@activities.route('/activity/enhanced/<int:activity_id>')
@login_required
@limiter.limit("30 per minute")
def view_enhanced_activity(activity_id):
    """View an activity with enhanced learning features"""
    try:
        logger.debug(f"Viewing enhanced activity with ID: {activity_id}")
        logger.debug(f"Current language: {get_user_language()}")

        activity = CodingActivity.query.filter_by(id=activity_id).first_or_404()

        if activity.starter_code is None:
            activity.starter_code = ''
        elif not isinstance(activity.starter_code, str):
            activity.starter_code = str(activity.starter_code)

        # Ensure session has language set
        if 'lang' not in session:
            session['lang'] = current_app.config['DEFAULT_LANGUAGE']
            session.modified = True

        return render_template(
            'activity.html',
            activity=activity,
            lang=get_user_language(),  # Use the centralized function
            enhanced=True
        )
    except Exception as e:
        logger.error(f"Error viewing enhanced activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500


# Cleanup inactive sessions periodically
def cleanup_old_sessions():
    """Clean up inactive sessions older than 15 minutes"""
    try:
        current_time = time.time()
        threshold = 900  # 15 minutes
        with session_lock:
            for session_id in list(active_sessions.keys()):
                session = active_sessions[session_id]
                if current_time - session.last_activity > threshold:
                    logger.info(f"Cleaning up inactive session {session_id}")
                    cleanup_session(session_id)
    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions: {e}", exc_info=True)

# Register cleanup on application shutdown
atexit.register(cleanup_old_sessions)

# Add periodic cleanup
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_sessions, 'interval', minutes=5)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())