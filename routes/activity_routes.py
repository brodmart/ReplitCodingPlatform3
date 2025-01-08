from flask import Blueprint, render_template, request, jsonify, session
from database import db
from models import CodingActivity
from extensions import limiter
from werkzeug.exceptions import RequestTimeout
import logging
import time
import subprocess
import os
import shutil
from threading import Lock, Timer
from compiler_service import compile_and_run
from utils.api_logger import log_api_request

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}
session_lock = Lock()

# Ensure temp directory exists and has proper permissions
TEMP_DIR = os.path.join(os.getcwd(), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)
os.chmod(TEMP_DIR, 0o755)  # Set proper permissions

@activities.route('/start_session', methods=['POST'])
def start_session():
    """Start a new interactive coding session"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Format de requête invalide'}), 400

        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

        if not code:
            return jsonify({'success': False, 'error': 'Le code ne peut pas être vide'}), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({'success': False, 'error': 'Langage non supporté'}), 400

        # Create unique temp directory for this session
        session_dir = os.path.join(TEMP_DIR, str(time.time()))
        os.makedirs(session_dir, exist_ok=True)

        # Write source code to file
        source_file = os.path.join(session_dir, f'program.{language}')
        with open(source_file, 'w') as f:
            f.write(code)

        # Compile and run initial test
        result = compile_and_run(code, language)
        if not result.get('success', False):
            shutil.rmtree(session_dir, ignore_errors=True)
            return jsonify(result), 400

        # Start interactive process
        try:
            executable = os.path.join(session_dir, 'program' if language == 'cpp' else 'program.exe')
            cmd = [executable] if language == 'cpp' else ['mono', executable]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=session_dir
            )

            session_id = str(time.time())
            with session_lock:
                active_sessions[session_id] = {
                    'process': process,
                    'temp_dir': session_dir,
                    'last_activity': time.time(),
                    'output_buffer': [],
                    'language': language,
                    'waiting_for_input': False
                }

            return jsonify({
                'success': True,
                'session_id': session_id,
                'message': 'Programme démarré'
            })

        except Exception as e:
            logger.error(f"Failed to start process: {e}")
            shutil.rmtree(session_dir, ignore_errors=True)
            return jsonify({
                'success': False,
                'error': f'Échec du démarrage du programme: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Error in start_session: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@activities.route('/send_input', methods=['POST'])
def send_input():
    """Send input to a running program"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Format de requête invalide'}), 400

        data = request.get_json()
        session_id = data.get('session_id')
        input_text = data.get('input', '')

        if not session_id or session_id not in active_sessions:
            return jsonify({'success': False, 'error': 'Session invalide'}), 400

        session = active_sessions[session_id]
        process = session['process']

        # Check if process is still running
        if process.poll() is not None:
            cleanup_session(session_id)
            return jsonify({'success': False, 'error': 'Le programme est terminé'}), 400

        try:
            # Send input to process
            process.stdin.write(input_text)
            process.stdin.flush()
            session['waiting_for_input'] = False
            session['last_activity'] = time.time()
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
            return jsonify({'success': False, 'error': 'Session invalide'}), 400

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
            # Get any remaining output
            try:
                stdout, stderr = process.communicate(timeout=1)
                if stdout:
                    output.append(stdout)
                if stderr:
                    output.append(stderr)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

            cleanup_session(session_id)
            return jsonify({
                'success': True,
                'output': ''.join(output),
                'session_ended': True
            })

        # Read any available output
        try:
            # Read stdout without blocking
            while True:
                # Use select to check if there's data to read
                import select
                rlist, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

                if not rlist:
                    # No more data to read right now
                    break

                for pipe in rlist:
                    line = pipe.readline()
                    if line:
                        output.append(line)
                        # Check if program is waiting for input
                        if ('cin' in line.lower() or 'console.read' in line.lower() or 
                            'enter' in line.lower() or 'input' in line.lower()):
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

@activities.route('/end_session', methods=['POST'])
def end_session():
    """End a coding session and clean up resources"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Format de requête invalide'}), 400

        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id or session_id not in active_sessions:
            return jsonify({'success': False, 'error': 'Session invalide'}), 400

        cleanup_session(session_id)
        return jsonify({'success': True, 'message': 'Session terminée'})

    except Exception as e:
        logger.error(f"Error ending session: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def cleanup_session(session_id):
    """Clean up session resources"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        try:
            # Terminate the process if it's still running
            process = session['process']
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

        except Exception as e:
            logger.error(f"Error terminating process: {e}", exc_info=True)

        # Clean up temporary directory
        try:
            shutil.rmtree(session['temp_dir'], ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}", exc_info=True)

        # Remove session from active sessions
        with session_lock:
            del active_sessions[session_id]

# Session cleanup background task
def cleanup_old_sessions():
    """Clean up inactive sessions older than 30 minutes"""
    current_time = time.time()
    with session_lock:
        for session_id in list(active_sessions.keys()):
            session = active_sessions[session_id]
            if current_time - session['last_activity'] > 1800:  # 30 minutes
                cleanup_session(session_id)
    Timer(1800, cleanup_old_sessions).start()

# Start the cleanup task
cleanup_old_sessions()

# Route handlers
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
                'error': 'Format de requête invalide. Veuillez rafraîchir la page et réessayer.'
            }), 400

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Données manquantes. Veuillez réessayer.'
            }), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()
        input_data = data.get('input', '')  # Get optional input data

        if not code:
            return jsonify({
                'success': False,
                'error': 'Le code ne peut pas être vide'
            }), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({
                'success': False,
                'error': 'Langage non supporté'
            }), 400

        # Pass input data to compiler service
        result = compile_and_run(code, language, input_data)

        if not result.get('success', False):
            error_msg = result.get('error', 'Une erreur s\'est produite')
            if 'memory' in error_msg.lower():
                error_msg += ". Essayez de réduire la taille des variables ou des tableaux."
            elif 'timeout' in error_msg.lower():
                error_msg += ". Vérifiez s'il y a des boucles infinies."
            result['error'] = error_msg

        return jsonify(result)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in execute_code for {client_ip}: {error_msg}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "Une erreur réseau s'est produite. Veuillez réessayer dans quelques instants."
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
            'error': "La requête a pris trop de temps. Veuillez réessayer."
        }), 408

    return jsonify({
        'success': False,
        'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
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
            'error': "Une erreur inattendue s'est produite lors du chargement des activités"
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
            'error': "Une erreur inattendue s'est produite lors du chargement de l'activité"
        }), 500