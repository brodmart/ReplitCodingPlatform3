import os
import logging
import time
import subprocess
import shutil
import select
from threading import Lock
import atexit
from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.exceptions import RequestTimeout
from database import db
from models import CodingActivity
from extensions import limiter

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}
session_lock = Lock()

# Create temp directory in the workspace
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.chmod(TEMP_DIR, 0o755)

@activities.route('/start_session', methods=['POST'])
@limiter.limit("30 per minute")
def start_session():
    """Start a new interactive coding session"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

        if not code:
            return jsonify({'success': False, 'error': 'Code cannot be empty'}), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({'success': False, 'error': 'Unsupported language'}), 400

        # Create unique session directory
        session_id = str(time.time())
        session_dir = os.path.join(TEMP_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        try:
            # Write source code to file
            file_extension = '.cpp' if language == 'cpp' else '.cs'
            source_file = os.path.join(session_dir, f'program{file_extension}')
            with open(source_file, 'w') as f:
                f.write(code)

            # Compile code
            executable_name = 'program' if language == 'cpp' else 'program.exe'
            executable_path = os.path.join(session_dir, executable_name)

            if language == 'cpp':
                compile_cmd = ['g++', source_file, '-o', executable_path, '-std=c++11']
            else:
                compile_cmd = ['mcs', source_file, '-out:' + executable_path]

            compile_process = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            if compile_process.returncode != 0:
                logger.error(f"Compilation failed: {compile_process.stderr}")
                return jsonify({
                    'success': False,
                    'error': compile_process.stderr
                }), 400

            # Make executable
            os.chmod(executable_path, 0o755)

            # Start interactive process
            cmd = [executable_path] if language == 'cpp' else ['mono', executable_path]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=session_dir
            )

            with session_lock:
                active_sessions[session_id] = {
                    'process': process,
                    'temp_dir': session_dir,
                    'last_activity': time.time(),
                    'output_buffer': [],
                    'language': language,
                    'waiting_for_input': False
                }

            logger.info(f"Started session {session_id} successfully")
            return jsonify({
                'success': True,
                'session_id': session_id,
                'message': 'Program started successfully'
            })

        except subprocess.TimeoutExpired:
            logger.error("Compilation timeout")
            shutil.rmtree(session_dir, ignore_errors=True)
            return jsonify({
                'success': False,
                'error': 'Compilation timeout'
            }), 400

        except Exception as e:
            logger.error(f"Failed to start process: {str(e)}", exc_info=True)
            shutil.rmtree(session_dir, ignore_errors=True)
            return jsonify({
                'success': False,
                'error': f'Failed to start program: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Error in start_session: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def cleanup_old_sessions():
    """Clean up inactive sessions older than 30 minutes"""
    try:
        current_time = time.time()
        with session_lock:
            for session_id in list(active_sessions.keys()):
                session = active_sessions[session_id]
                if current_time - session['last_activity'] > 1800:  # 30 minutes
                    cleanup_session(session_id)
    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions: {e}", exc_info=True)

# Register cleanup on application shutdown
atexit.register(cleanup_old_sessions)

@activities.route('/send_input', methods=['POST'])
def send_input():
    """Send input to a running program"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        session_id = data.get('session_id')
        input_text = data.get('input', '')

        if not session_id or session_id not in active_sessions:
            return jsonify({'success': False, 'error': 'Invalid session'}), 400

        session = active_sessions[session_id]
        process = session['process']

        if process.poll() is not None:
            cleanup_session(session_id)
            return jsonify({'success': False, 'error': 'Program has ended'}), 400

        try:
            # Send input to process with newline
            process.stdin.write(f"{input_text}\n")
            process.stdin.flush()
            session['waiting_for_input'] = False
            session['last_activity'] = time.time()

            # Small delay to allow program to process input
            time.sleep(0.1)
            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Error sending input: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error in send_input: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@activities.route('/get_output')
def get_output():
    """Get output from a running program"""
    try:
        session_id = request.args.get('session_id')
        if not session_id or session_id not in active_sessions:
            return jsonify({'success': False, 'error': 'Invalid session'}), 400

        session = active_sessions[session_id]
        process = session['process']
        output = []
        waiting_for_input = False

        # Add any buffered output
        if session['output_buffer']:
            output.extend(session['output_buffer'])
            session['output_buffer'] = []

        # Check if process has terminated
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            if stdout:
                output.append(stdout)
            if stderr:
                output.append(stderr)
            cleanup_session(session_id)
            return jsonify({
                'success': True,
                'output': ''.join(output),
                'session_ended': True
            })

        # Read available output with non-blocking
        try:
            # Use select with a short timeout to check for available output
            reads = [process.stdout, process.stderr]
            readable, _, _ = select.select(reads, [], [], 0.1)

            for pipe in readable:
                line = pipe.readline()
                if line:
                    output.append(line)
                    # Enhanced input prompt detection
                    lower_line = line.lower()
                    if any(prompt in lower_line for prompt in [
                        'input', 'enter', 'type', '?', ':', '>',
                        'cin', 'cin >>', 'console.readline', 'console.read',
                        'please', 'getline', 'input:', 'enter:', 'name:'
                    ]):
                        waiting_for_input = True
                        session['waiting_for_input'] = True

            # If no output is available and process is still running,
            # check if we're waiting for input
            if not output and not readable and process.poll() is None:
                # If the process is not terminated and we don't have output,
                # it's likely waiting for input
                waiting_for_input = True
                session['waiting_for_input'] = True

            session['last_activity'] = time.time()
            return jsonify({
                'success': True,
                'output': ''.join(output) if output else '',
                'waiting_for_input': waiting_for_input,
                'session_ended': False
            })

        except Exception as e:
            logger.error(f"Error reading output: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error in get_output: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def cleanup_session(session_id):
    """Clean up session resources"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        try:
            # Terminate process if still running
            process = session['process']
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            # Clean up temp directory
            shutil.rmtree(session['temp_dir'], ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up session: {e}", exc_info=True)

        # Remove session from active sessions
        with session_lock:
            del active_sessions[session_id]

@activities.route('/end_session', methods=['POST'])
def end_session():
    """End a coding session and clean up resources"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400

        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id or session_id not in active_sessions:
            return jsonify({'success': False, 'error': 'Invalid session'}), 400

        cleanup_session(session_id)
        return jsonify({'success': True, 'message': 'Session ended'})

    except Exception as e:
        logger.error(f"Error ending session: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@activities.route('/execute', methods=['POST'])
@limiter.limit("10 per minute")
def execute_code():
    """Execute submitted code with input support"""
    start_time = time.time()
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Invalid request format. Please refresh the page and try again.'
            }), 400

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing data. Please try again.'
            }), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()
        input_data = data.get('input', '')  # Get optional input data

        if not code:
            return jsonify({
                'success': False,
                'error': 'Code cannot be empty'
            }), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({
                'success': False,
                'error': 'Unsupported language'
            }), 400

        # Pass input data to compiler service
        result = compile_and_run(code, language, input_data)

        if not result.get('success', False):
            error_msg = result.get('error', 'An error occurred')
            if 'memory' in error_msg.lower():
                error_msg += ". Try reducing the size of variables or arrays."
            elif 'timeout' in error_msg.lower():
                error_msg += ". Check for infinite loops."
            result['error'] = error_msg

        return jsonify(result)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in execute_code for {client_ip}: {error_msg}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "A network error occurred. Please try again in a few moments."
        }), 500

# Request logging and error handling
@activities.before_request
def before_request():
    """Store request start time for duration calculation"""
    request.start_time = time.time()

@activities.after_request
def after_request(response):
    """Log request details after completion"""
    if hasattr(request, 'start_time') and request.endpoint:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        log_api_request(
            request.start_time,
            client_ip,
            request.endpoint,
            response.status_code
        )
    return response

@activities.errorhandler(Exception)
def handle_error(error):
    """Global error handler for the blueprint with enhanced logging"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    error_details = f"{type(error).__name__}: {str(error)}"
    logger.error(f"Error for client {client_ip}: {error_details}", exc_info=True)

    if isinstance(error, RequestTimeout):
        return jsonify({
            'success': False,
            'error': "The request took too long. Please try again."
        }), 408

    return jsonify({
        'success': False,
        'error': "An unexpected error occurred. Please try again."
    }), 500

# Activity list and view routes
@activities.route('/')
@activities.route('/<grade>')
@limiter.limit("30 per minute")
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

        try:
            # Query activities for the specified grade level
            activities_list = CodingActivity.query.filter_by(
                curriculum=curriculum,
                language=language
            ).order_by(CodingActivity.sequence).all()

            logger.debug(f"Found {len(activities_list)} activities")

        except Exception as db_error:
            logger.error(f"Database error in list_activities: {str(db_error)}", exc_info=True)
            raise
        try:
            return render_template(
                'activities/list.html',
                activities=activities_list,
                curriculum=curriculum,
                lang=session.get('lang', 'fr'),
                grade=grade
            )
        except Exception as template_error:
            logger.error(f"Template rendering error: {str(template_error)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading activities"
        }), 500

@activities.route('/activity/<int:activity_id>')
@limiter.limit("30 per minute")
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        logger.debug(f"Viewing activity with ID: {activity_id}")

        try:
            activity = CodingActivity.query.get_or_404(activity_id)
            logger.debug(f"Found activity: {activity.title}")
        except Exception as db_error:
            logger.error(f"Database error in view_activity: {str(db_error)}", exc_info=True)
            raise

        try:
            return render_template(
                'activity.html',
                activity=activity,
                lang=session.get('lang', 'fr')
            )
        except Exception as template_error:
            logger.error(f"Template rendering error in view_activity: {str(template_error)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error viewing activity {activity_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "An unexpected error occurred while loading the activity"
        }), 500

def log_api_request(start_time, client_ip, endpoint, status_code):
    """Log API request details"""
    duration = time.time() - start_time
    logger.info(f"API Request - Client: {client_ip}, Endpoint: {endpoint}, Status: {status_code}, Duration: {duration:.2f}s")