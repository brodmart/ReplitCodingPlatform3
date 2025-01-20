import os
import logging
import time
import subprocess
import shutil
from threading import Lock
import atexit
import fcntl
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from werkzeug.exceptions import RequestTimeout
from database import db
from models import CodingActivity, StudentProgress, CodeSubmission
from extensions import limiter
from sqlalchemy import text
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from utils.backup import DatabaseBackup
from routes.static_routes import get_user_language  # Import the centralized language function
from compiler_service import (
    compile_and_run,
    cleanup_session,
    send_input,
    get_output,
    active_sessions,
    session_lock,
    CompilerSession # Assuming this is defined in compiler_service
)

# Initialize scheduler for backups
scheduler = BackgroundScheduler()
scheduler.add_job(DatabaseBackup.schedule_backup, 'interval', hours=6)
scheduler.start()

# Register cleanup on application shutdown
atexit.register(lambda: scheduler.shutdown())

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Store active sessions (Now managed by compiler_service)
# active_sessions = {}
# session_lock = Lock()

# Create temp directory
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.chmod(TEMP_DIR, 0o755)

def log_api_request(start_time, client_ip, endpoint, status_code):
    """Log API request details"""
    duration = time.time() - start_time
    logger.info(f"API Request - Client: {client_ip}, Endpoint: {endpoint}, Status: {status_code}, Duration: {duration:.2f}s")

# compile_and_run function is now in compiler_service

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

@activities.route('/activities/submit_code', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def submit_code():
    """Execute code submitted from the enhanced learning view"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        code = data.get('code', '').strip()
        activity_id = data.get('activity_id')
        language = data.get('language', 'cpp').lower()

        if not code:
            return jsonify({'success': False, 'error': 'Code cannot be empty'}), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({'success': False, 'error': 'Unsupported language'}), 400

        # Record start time for performance tracking
        start_time = time.time()

        # Compile and run the code
        result = compile_and_run(code, language)
        execution_success = result.get('success', False)

        # Calculate completion time
        completion_time = time.time() - start_time

        # Update student progress with new metrics
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

        # Update difficulty and performance metrics
        progress.update_difficulty(execution_success, completion_time)

        # Generate personalized feedback
        feedback = progress.generate_personalized_feedback(
            submission_error=result.get('error') if not execution_success else None
        )

        # If successful, mark as completed
        if execution_success and not progress.completed:
            progress.completed = True
            progress.completed_at = datetime.utcnow()

        progress.attempts += 1
        progress.last_submission = code

        db.session.commit()

        # Add learning analytics to response
        result['difficulty_level'] = progress.difficulty_level
        result['success_rate'] = progress.success_rate
        result['personalized_feedback'] = feedback
        result['learning_patterns'] = progress.analyze_performance()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error running code: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An error occurred while running your code."
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


@activities.route('/start_session', methods=['POST'])
@limiter.limit("30 per minute")
def start_session():
    """Start a new interactive coding session with enhanced resource management"""
    logger.info("start_session endpoint called")

    if not request.is_json:
        logger.error("Invalid request format - not JSON")
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400

    try:
        data = request.get_json()
        logger.info(f"Received request data: {data}")

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

        if not code:
            logger.error("Empty code submitted")
            return jsonify({'success': False, 'error': 'Code cannot be empty'}), 400

        # Start interactive compilation and execution
        result = compile_and_run(
            code,
            language,
            interactive=True,
            compile_timeout=15,  # Increased compilation timeout
            execution_timeout=60  # Increased execution timeout
        )

        if not result.get('success'):
            logger.error(f"Compilation failed: {result.get('error')}")
            return jsonify(result), 400

        # Create new session
        session_id = str(time.time())
        with session_lock:
            active_sessions[session_id] = CompilerSession(
                session_id=session_id,
                temp_dir=result['temp_dir']
            )
            session = active_sessions[session_id]
            session.process = result['process']
            session.last_activity = time.time()

        logger.info(f"Successfully started session {session_id}")
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Interactive program started successfully'
        })

    except Exception as e:
        logger.error(f"Error in start_session: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/get_output', methods=['GET'])
@limiter.limit("60 per minute")
def get_session_output():
    """Get output from a running interactive program with improved error handling"""
    session_id = request.args.get('session_id')
    logger.debug(f"GET /get_output - Session {session_id}")

    if not session_id:
        return jsonify({'success': False, 'error': 'No session ID provided'}), 400

    try:
        result = get_output(session_id)
        if not result['success']:
            cleanup_session(session_id)
            return jsonify(result), 400

        if result.get('session_ended', False):
            cleanup_session(session_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting output: {str(e)}", exc_info=True)
        cleanup_session(session_id)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/send_input', methods=['POST'])
@limiter.limit("60 per minute")
def send_session_input():
    """Send input to a running interactive program with improved error handling"""
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

@activities.route('/end_session', methods=['POST'])
@limiter.limit("30 per minute")
def end_session():
    """End an interactive coding session and clean up resources"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'error': 'No session ID provided'}), 400

        cleanup_session(session_id)
        return jsonify({
            'success': True,
            'message': 'Session ended and resources cleaned up'
        })

    except Exception as e:
        logger.error(f"Error ending session: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/execute', methods=['POST'])
@limiter.limit("10 per minute")
def execute_code():
    """Execute submitted code with input support"""
    start_time = time.time()
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    try:
        if not request.is_json:
            response = jsonify({
                'success': False,
                'error': 'Invalid request format. Please refresh the page and try again.'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        data = request.get_json()
        if not data:
            response = jsonify({
                'success': False,
                'error': 'Missing data. Please try again.'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()
        input_data = data.get('input', '')  # Get optional input data

        if not code:
            response = jsonify({
                'success': False,
                'error': 'Code cannot be empty'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        if language not in ['cpp', 'csharp']:
            response = jsonify({
                'success': False,
                'error': 'Unsupported language'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        # Pass input data to compiler service
        result = compile_and_run(code, language, input_data)
        log_api_request(start_time, client_ip, '/execute', 200)

        if result.get('success', False):
            logger.info(f"Code execution successful for {language}")
        else:
            logger.warning(f"Code execution failed for {language}: {result.get('error', 'Unknown error')}")

        response = jsonify(result)
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger.error(f"Error executing code: {str(e)}", exc_info=True)
        log_api_request(start_time, client_ip, '/execute', 500)
        response = jsonify({
            'success': False,
            'error': "An error occurred while executing your code."
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

# Initialize cleanup of old sessions
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