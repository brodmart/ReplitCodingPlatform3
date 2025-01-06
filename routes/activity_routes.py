from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, Response
from database import db
from models import CodingActivity
from extensions import limiter, cache
import logging
from compiler_service import compile_and_run, CompilerError, ExecutionError
from werkzeug.exceptions import RequestTimeout

activities = Blueprint('activities', __name__, template_folder='../templates')
logger = logging.getLogger(__name__)

@activities.errorhandler(Exception)
def handle_error(error):
    """Global error handler for the blueprint"""
    logger.error(f"Uncaught exception in activities blueprint: {str(error)}", exc_info=True)
    if isinstance(error, RequestTimeout):
        return jsonify({
            'success': False,
            'error': "La requête a pris trop de temps. Veuillez réessayer."
        }), 408
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
@limiter.limit("10 per minute")  # Reduced rate limit to prevent overload
def execute_code():
    """Execute submitted code and return the results with improved error handling"""
    try:
        # Log the incoming request with client info
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        logger.debug(f"Received code execution request from {client_ip}")
        logger.debug(f"Content-Type: {request.headers.get('Content-Type')}")

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

        logger.debug(f"Executing {language} code for {client_ip}")
        logger.debug(f"Code length: {len(code)}")

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

        # Set a timeout for the compilation and execution
        result = compile_and_run(code, language)
        logger.debug(f"Execution result for {client_ip}: {result}")

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

    except CompilerError as e:
        logger.error(f"Compilation error for {client_ip}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except ExecutionError as e:
        logger.error(f"Execution error for {client_ip}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Erreur d'exécution: {str(e)}"
        }), 400

    except Exception as e:
        logger.error(f"Unexpected error in execute_code for {client_ip}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "Une erreur réseau s'est produite. Veuillez réessayer dans quelques instants."
        }), 500