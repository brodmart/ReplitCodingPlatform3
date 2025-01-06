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