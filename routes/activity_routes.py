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

# Initialize scheduler for backups
scheduler = BackgroundScheduler()
scheduler.add_job(DatabaseBackup.schedule_backup, 'interval', hours=6)
scheduler.start()

# Register cleanup on application shutdown
atexit.register(lambda: scheduler.shutdown())

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}
session_lock = Lock()

# Create temp directory
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.chmod(TEMP_DIR, 0o755)

def log_api_request(start_time, client_ip, endpoint, status_code):
    """Log API request details"""
    duration = time.time() - start_time
    logger.info(f"API Request - Client: {client_ip}, Endpoint: {endpoint}, Status: {status_code}, Duration: {duration:.2f}s")

def compile_and_run(code, language, input_data=None):
    """Compile and run code with input support"""
    logger.debug("Starting compile_and_run")
    if not code or not language:
        logger.error("Invalid parameters to compile_and_run")
        return {'success': False, 'error': 'Invalid parameters'}

    try:
        session_id = str(time.time())
        session_dir = os.path.join(TEMP_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        try:
            # Write source code to file
            file_extension = '.cpp' if language == 'cpp' else '.cs'
            source_file = os.path.join(session_dir, f'program{file_extension}')

            with open(source_file, 'w') as f:
                f.write(code)

            # Set up compilation
            executable_name = 'program' if language == 'cpp' else 'program.exe'
            executable_path = os.path.join(session_dir, executable_name)

            if language == 'cpp':
                compile_cmd = ['g++', source_file, '-o', executable_path, '-std=c++11']
            else:
                compile_cmd = ['mcs', source_file, '-out:' + executable_path]

            # Compile code
            compile_process = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if compile_process.returncode != 0:
                logger.error(f"Compilation error: {compile_process.stderr}")
                return {'success': False, 'error': compile_process.stderr}

            os.chmod(executable_path, 0o755)

            # Execute code
            cmd = [executable_path] if language == 'cpp' else ['mono', executable_path]

            # Prepare input data if provided
            input_bytes = None
            if input_data:
                input_bytes = input_data.encode('utf-8')

            # Run the program
            process = subprocess.run(
                cmd,
                input=input_bytes,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=session_dir
            )

            # Prepare response
            return {
                'success': process.returncode == 0,
                'output': process.stdout if process.stdout else '',
                'error': process.stderr if process.returncode != 0 else None
            }

        except subprocess.TimeoutExpired:
            logger.error("Execution timeout")
            return {'success': False, 'error': 'Execution timeout - check for infinite loops'}
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {'success': False, 'error': str(e)}

    except Exception as e:
        logger.error(f"Error in compile_and_run: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
    finally:
        # Cleanup temporary files
        if 'session_dir' in locals():
            shutil.rmtree(session_dir, ignore_errors=True)

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

        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Using curriculum: {curriculum}, language: {language}")

        try:
            # Query activities for the specified grade level, excluding soft-deleted ones
            activities_list = CodingActivity.get_active().filter_by(
                curriculum=curriculum,
                language=language
            ).order_by(CodingActivity.sequence).all()

            logger.debug(f"Found {len(activities_list)} active activities")

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
            lang=session.get('lang', 'fr')
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

        activity = CodingActivity.query.filter_by(id=activity_id).first_or_404()

        if activity.starter_code is None:
            activity.starter_code = ''
        elif not isinstance(activity.starter_code, str):
            activity.starter_code = str(activity.starter_code)

        return render_template(
            'activities/enhanced_learning.html',
            activity=activity,
            lang=session.get('lang', 'fr')
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
    """Start a new interactive coding session"""
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

        session_id = str(time.time())
        session_dir = os.path.join(os.getcwd(), 'temp', session_id)
        os.makedirs(session_dir, exist_ok=True)

        try:
            # Write source code to file
            file_extension = '.cpp' if language == 'cpp' else '.cs'
            source_file = os.path.join(session_dir, f'program{file_extension}')
            code_size = len(code)
            logger.info(f"Code submission size: {code_size} bytes")
            if code_size > 50000:
                logger.warning(f"Large code submission detected: {code_size} bytes")

            logger.debug(f"Writing source to {source_file}")
            logger.info(f"Starting compilation for {language} code ({code_size} bytes)")

            with open(source_file, 'w') as f:
                f.write(code)

            # Compile code
            executable_name = 'program' if language == 'cpp' else 'program.exe'
            executable_path = os.path.join(session_dir, executable_name)

            if language == 'cpp':
                compile_cmd = ['g++', source_file, '-o', executable_path, '-std=c++11']
            else:
                compile_cmd = ['mcs', source_file, '-out:' + executable_path]

            logger.debug(f"Compiling with command: {' '.join(compile_cmd)}")

            compile_start = time.time()
            compile_process = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            compile_time = time.time() - compile_start
            logger.info(f"Compilation completed in {compile_time:.2f} seconds")

            if compile_process.returncode != 0:
                logger.error(f"Compilation failed: {compile_process.stderr}")
                return jsonify({
                    'success': False,
                    'error': compile_process.stderr
                }), 400

            logger.debug("Compilation successful")
            os.chmod(executable_path, 0o755)

            # Start interactive process
            cmd = [executable_path] if language == 'cpp' else ['mono', executable_path]
            logger.debug(f"Starting process with command: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # No buffering for immediate output
                encoding='utf-8',  # Explicitly set encoding
                errors='replace',  # Handle encoding errors gracefully
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

            logger.info(f"Successfully started session {session_id}")
            response = jsonify({
                'success': True,
                'session_id': session_id,
                'message': 'Program started successfully'
            })
            response.headers['Content-Type'] = 'application/json'
            return response

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

@activities.route('/get_output', methods=['GET'])
def get_output():
    """Get output from a running program"""
    session_id = request.args.get('session_id')
    logger.info(f"GET /get_output - Session {session_id}")

    try:
        if not session_id:
            logger.error("No session ID provided")
            return jsonify({'success': False, 'error': 'No session ID'}), 400

        if session_id not in active_sessions:
            logger.error(f"Invalid session ID: {session_id}")
            return jsonify({'success': False, 'error': 'Invalid session'}), 400

        logger.debug(f"Active session found: {session_id}")
        session_data = active_sessions[session_id]
        process = session_data['process']
        output = []
        waiting_for_input = False

        # Check if process has terminated
        if process.poll() is not None:
            logger.debug(f"Process terminated for session {session_id}")
            try:
                # Try to get any remaining output
                stdout, stderr = process.communicate(timeout=1)
                if stdout:
                    # Handle both string and bytes output
                    if isinstance(stdout, bytes):
                        output.append(stdout.decode('utf-8', errors='replace'))
                    else:
                        output.append(str(stdout))
                if stderr:
                    if isinstance(stderr, bytes):
                        output.append(stderr.decode('utf-8', errors='replace'))
                    else:
                        output.append(str(stderr))
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                if stdout:
                    if isinstance(stdout, bytes):
                        output.append(stdout.decode('utf-8', errors='replace'))
                    else:
                        output.append(str(stdout))
                if stderr:
                    if isinstance(stderr, bytes):
                        output.append(stderr.decode('utf-8', errors='replace'))
                    else:
                        output.append(str(stderr))

            cleanup_session(session_id)
            final_output = ''.join(output) if output else ''
            logger.debug(f"Final output before termination: {final_output}")
            return jsonify({
                'success': True,
                'output': final_output,
                'session_ended': True
            })

        # Handle stdout and stderr reading
        try:
            # Set non-blocking mode for stdout if it exists
            if process.stdout and not process.stdout.closed:
                try:
                    fd = process.stdout.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                    try:
                        # Read from stdout
                        data = process.stdout.buffer.read()
                        if data is not None:
                            text = data.decode('utf-8', errors='replace')
                            logger.debug(f"Read stdout: {text}")
                            output.append(text)
                            # Check for input prompts
                            lower_text = text.lower()
                            if any(prompt in lower_text for prompt in [
                                'input', 'enter', 'type', '?', ':', '>',
                                'cin', 'cin >>', 'console.readline', 'console.read'
                            ]):
                                logger.debug("Input prompt detected")
                                waiting_for_input = True
                                session_data['waiting_for_input'] = True
                    except BlockingIOError:
                        logger.debug("No data available from stdout")
                        # Maintain existing input state
                        waiting_for_input = session_data.get('waiting_for_input', False)
                    except Exception as e:
                        logger.error(f"Error reading stdout: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error setting up non-blocking stdout: {e}", exc_info=True)

            # Handle stderr if it exists
            if process.stderr and not process.stderr.closed:
                try:
                    fd = process.stderr.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                    try:
                        # Read from stderr
                        data = process.stderr.buffer.read()
                        if data is not None:
                            text = data.decode('utf-8', errors='replace')
                            logger.debug(f"Read stderr: {text}")
                            output.append(text)
                    except BlockingIOError:
                        logger.debug("No data available from stderr")
                    except Exception as e:
                        logger.error(f"Error reading stderr: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error setting up non-blocking stderr: {e}", exc_info=True)

            session_data['last_activity'] = time.time()
            final_output = ''.join(output) if output else ''
            logger.debug(f"Sending response - Output: {final_output}, Waiting for input: {waiting_for_input}")

            return jsonify({
                'success': True,
                'output': final_output,
                'waiting_for_input': waiting_for_input,
                'session_ended': False
            })

        except Exception as e:
            logger.error(f"Error reading process output: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Error in get_output: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def cleanup_session(session_id):
    """Clean up session resources"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        logger.info(f"Cleaning up session {session_id}")
        try:
            # Terminate process if still running
            process = session['process']
            if process.poll() is None:
                logger.debug(f"Terminating process for session {session_id}")
                process.terminate()
                try:
                    # Give process time to terminate gracefully
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process didn't terminate gracefully, forcing kill for session {session_id}")
                    process.kill()
                    process.wait()

            # Close file descriptors
            logger.debug("Closing file descriptors")
            for fd in [process.stdout, process.stderr, process.stdin]:
                if fd:
                    try:
                        fd.close()
                    except Exception as e:
                        logger.error(f"Error closing file descriptor: {e}", exc_info=True)

            # Clean up temp directory
            temp_dir = session['temp_dir']
            if os.path.exists(temp_dir):
                logger.debug(f"Removing temp directory: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}", exc_info=True)
        finally:
            # Remove session from active sessions
            with session_lock:
                del active_sessions[session_id]
                logger.info(f"Session {session_id} cleanup completed")

def cleanup_old_sessions():
    """Clean up inactive sessions older than 30 minutes"""
    try:
        current_time = time.time()
        cleaned_count = 0
        with session_lock:
            for session_id in list(active_sessions.keys()):
                session = active_sessions[session_id]
                if current_time - session['last_activity'] > 1800:  # 30 minutes
                    logger.info(f"Cleaning up inactive session {session_id}")
                    cleanup_session(session_id)
                    cleaned_count += 1
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} inactive sessions")
    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions: {e}", exc_info=True)

# Register cleanup on application shutdown
atexit.register(cleanup_old_sessions)

@activities.route('/send_input', methods=['POST'])
def send_input():
    """Send input to a running program"""
    try:
        if not request.is_json:
            response = jsonify({'success': False, 'error': 'Invalid request format'})
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        data = request.get_json()
        session_id = data.get('session_id')
        input_text = data.get('input', '')

        if not session_id or session_id not in active_sessions:
            response = jsonify({'success': False, 'error': 'Invalid session'})
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        session = active_sessions[session_id]
        process = session['process']

        if process.poll() is not None:
            cleanup_session(session_id)
            response = jsonify({'success': False, 'error': 'Program has ended'})
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        try:
            # Send input to process with newline
            process.stdin.write(f"{input_text}\n")
            process.stdin.flush()
            session['waiting_for_input'] = False
            session['last_activity'] = time.time()

            # Small delay to allow program to process input
            time.sleep(0.1)
            response = jsonify({'success': True})
            response.headers['Content-Type'] = 'application/json'
            return response

        except Exception as e:
            logger.error(f"Error sending input: {e}", exc_info=True)
            response = jsonify({'success': False, 'error': str(e)})
            response.headers['Content-Type'] = 'application/json'
            return response, 500

    except Exception as e:
        logger.error(f"Error in send_input: {str(e)}", exc_info=True)
        response = jsonify({'success': False, 'error': str(e)})
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@activities.route('/end_session', methods=['POST'])
def end_session():
    """End a coding session and clean up resources"""
    try:
        if not request.is_json:
            response = jsonify({'success': False, 'error': 'Invalid request format'})
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id or session_id not in active_sessions:
            response = jsonify({'success': False, 'error': 'Invalid session'})
            response.headers['Content-Type'] = 'application/json'
            return response, 400

        cleanup_session(session_id)
        response = jsonify({'success': True, 'message': 'Session ended'})
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger.error(f"Error ending session: {e}", exc_info=True)
        response = jsonify({'success': False, 'error': str(e)})
        response.headers['Content-Type'] = 'application/json'
        return response, 500

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

        if not result.get('success', False):
            error_msg = result.get('error', 'An error occurred')
            if 'memory' in error_msg.lower():
                error_msg += ". Try reducing the size of variables or arrays."
            elif 'timeout' in error_msg.lower():
                error_msg += ". Check for infinite loops."
            result['error'] = error_msg

        response = jsonify(result)
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in execute_code for {client_ip}: {error_msg}", exc_info=True)
        response = jsonify({
            'success': False,
            'error': "A network error occurred. Please try again in a few moments."
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500