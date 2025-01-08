from flask import Blueprint, render_template, request, jsonify, session
from database import db
from models import CodingActivity
import logging
import time
import subprocess
import os
from threading import Lock
from compiler_service import compile_and_run, CompilerError, ExecutionError
from werkzeug.exceptions import RequestTimeout

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}
session_lock = Lock()

@activities.route('/start_session', methods=['POST'])
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

        # Create temp files for the session
        temp_dir = os.path.join(os.getcwd(), 'temp', str(time.time()))
        os.makedirs(temp_dir, exist_ok=True)

        source_file = os.path.join(temp_dir, f'program.{language}')
        with open(source_file, 'w') as f:
            f.write(code)

        # Compile the code
        if language == 'cpp':
            executable = os.path.join(temp_dir, 'program')
            compile_cmd = ['g++', source_file, '-o', executable]
        else:  # C#
            executable = os.path.join(temp_dir, 'program.exe')
            compile_cmd = ['mcs', source_file, '-out:' + executable]

        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compile_result.returncode != 0:
            return jsonify({
                'success': False,
                'error': compile_result.stderr
            }), 400

        # Start the program
        if language == 'cpp':
            process = subprocess.Popen(
                [executable],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        else:  # C#
            process = subprocess.Popen(
                ['mono', executable],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

        session_id = str(time.time())
        with session_lock:
            active_sessions[session_id] = {
                'process': process,
                'temp_dir': temp_dir,
                'output_buffer': [],
                'last_activity': time.time()
            }

        return jsonify({
            'success': True,
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"Error starting session: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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

        # Send input to process
        try:
            process.stdin.write(input_text + '\n')
            process.stdin.flush()
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

        # Check if process has terminated
        if process.poll() is not None:
            # Get any remaining output
            stdout, stderr = process.communicate()
            if stdout:
                output.append(stdout)
            if stderr:
                output.append(stderr)

            # Clean up session
            cleanup_session(session_id)

            return jsonify({
                'success': True,
                'output': ''.join(output),
                'finished': True
            })

        # Read any available output
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                output.append(line)
        except Exception as e:
            logger.error(f"Error reading output: {e}", exc_info=True)

        return jsonify({
            'success': True,
            'output': ''.join(output) if output else '',
            'finished': False
        })

    except Exception as e:
        logger.error(f"Error in get_output: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error ending session: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

def cleanup_session(session_id):
    """Clean up session resources"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        try:
            # Terminate the process if it's still running
            if session['process'].poll() is None:
                session['process'].terminate()
                session['process'].wait(timeout=5)
        except subprocess.TimeoutExpired:
            session['process'].kill()

        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(session['temp_dir'], ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}", exc_info=True)

        # Remove session from active sessions
        with session_lock:
            del active_sessions[session_id]

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, Response
from database import db
from models import CodingActivity
from extensions import limiter, cache
import logging
import time
from compiler_service import compile_and_run, CompilerError, ExecutionError
from werkzeug.exceptions import RequestTimeout

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

# Configure logging for API monitoring
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
)

def log_api_request(start_time, client_ip, endpoint, status_code, error=None):
    """Log API request details"""
    duration = round((time.time() - start_time) * 1000, 2)  # Duration in milliseconds
    logger.info(f"""
    API Request Details:
    - Client IP: {client_ip}
    - Endpoint: {endpoint}
    - Duration: {duration}ms
    - Status: {status_code}
    {f'- Error: {error}' if error else ''}
    """)

@activities.before_request
def before_request():
    """Store request start time for duration calculation"""
    request.start_time = time.time()

@activities.after_request
def after_request(response):
    """Log request details after completion"""
    if request.endpoint:
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
        log_api_request(
            request.start_time,
            client_ip,
            request.endpoint,
            408,
            "Request timeout"
        )
        return jsonify({
            'success': False,
            'error': "La requête a pris trop de temps. Veuillez réessayer."
        }), 408

    log_api_request(
        request.start_time,
        client_ip,
        request.endpoint,
        500,
        error_details
    )
    return jsonify({
        'success': False,
        'error': "Une erreur inattendue s'est produite. Veuillez réessayer."
    }), 500

@activities.route('/test')
def test_template():
    """Test route to verify template rendering"""
    try:
        logger.debug("Testing template rendering")
        return render_template(
            'activities/list.html',
            activities=[],
            curriculum='TEJ2O',
            lang='fr',
            grade='10'
        )
    except Exception as e:
        logger.error(f"Template test error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Template error: {str(e)}"
        }), 500

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
            for activity in activities_list:
                logger.debug(f"Activity: {activity.id} - {activity.title}")

        except Exception as db_error:
            logger.error(f"Database error in list_activities: {str(db_error)}", exc_info=True)
            raise

        # Render the list template
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

@activities.route('/execute', methods=['POST'])
@limiter.limit("10 per minute")
def execute_code():
    """Execute submitted code with enhanced monitoring"""
    start_time = time.time()
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    try:
        # Detailed request logging
        logger.info(f"""
        Code Execution Request:
        - Client IP: {client_ip}
        - Content-Type: {request.headers.get('Content-Type')}
        - User-Agent: {request.headers.get('User-Agent')}
        """)

        if not request.is_json:
            logger.error(f"Invalid request format from {client_ip}: not JSON")
            return jsonify({
                'success': False,
                'error': 'Format de requête invalide. Veuillez rafraîchir la page et réessayer.'
            }), 400

        data = request.get_json()
        if not data:
            logger.error(f"No JSON data in request from {client_ip}")
            return jsonify({
                'success': False,
                'error': 'Données manquantes. Veuillez réessayer.'
            }), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

        # Log execution details
        logger.info(f"""
        Starting Code Execution:
        - Client IP: {client_ip}
        - Language: {language}
        - Code Length: {len(code)}
        """)

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

        # Execute code and measure performance
        execution_start = time.time()
        result = compile_and_run(code, language)
        execution_time = round((time.time() - execution_start) * 1000, 2)

        # Log execution results
        logger.info(f"""
        Code Execution Complete:
        - Client IP: {client_ip}
        - Execution Time: {execution_time}ms
        - Success: {result.get('success', False)}
        - Error: {result.get('error', 'None')}
        """)

        if not result.get('success', False):
            error_msg = result.get('error', 'Une erreur s\'est produite')
            if 'memory' in error_msg.lower():
                error_msg += ". Essayez de réduire la taille des variables ou des tableaux."
            elif 'timeout' in error_msg.lower():
                error_msg += ". Vérifiez s'il y a des boucles infinies."

        return jsonify({
            'success': result.get('success', False),
            'output': result.get('output', ''),
            'error': result.get('error', None)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in execute_code for {client_ip}: {error_msg}", exc_info=True)

        # Log error details
        log_api_request(
            start_time,
            client_ip,
            'execute_code',
            500,
            error_msg
        )

        return jsonify({
            'success': False,
            'error': "Une erreur réseau s'est produite. Veuillez réessayer dans quelques instants."
        }), 500