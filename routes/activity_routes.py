from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, Response
from flask_wtf.csrf import CSRFProtect
from models import CodingActivity, db
from extensions import limiter, cache
import logging
from compiler_service import compile_and_run, CompilerError, ExecutionError

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

@activities.errorhandler(Exception)
def handle_error(error):
    """Global error handler for the blueprint"""
    logger.error(f"Uncaught exception in activities blueprint: {str(error)}", exc_info=True)
    return jsonify({
        'success': False,
        'error': "Une erreur inattendue s'est produite"
    }), 500

@activities.before_request
def before_activities_request():
    """Log activity requests"""
    logger.debug(f"Activity route accessed: {request.endpoint}")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    if request.is_json:
        logger.debug(f"Request JSON data: {request.get_json(silent=True)}")

@activities.after_request
def after_activities_request(response):
    """Log activity responses"""
    logger.debug(f"Response status: {response.status}")
    logger.debug(f"Response headers: {dict(response.headers)}")
    return response

@activities.route('/execute', methods=['POST'])
@limiter.limit("20 per minute")
def execute_code():
    """Execute submitted code and return the results"""
    try:
        # Log the incoming request
        logger.debug("Received code execution request")
        logger.debug(f"Content-Type: {request.headers.get('Content-Type')}")
        logger.debug(f"CSRF Token Header: {request.headers.get('X-CSRF-Token')}")

        if not request.is_json:
            logger.error("Invalid request format: not JSON")
            return jsonify({
                'success': False,
                'error': 'Format de requête invalide'
            }), 400

        data = request.get_json()
        if not data:
            logger.error("No JSON data in request")
            return jsonify({
                'success': False,
                'error': 'Données manquantes'
            }), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

        logger.debug(f"Executing code in {language}")
        logger.debug(f"Request data: {data}")

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

        result = compile_and_run(code, language)
        logger.debug(f"Execution result: {result}")

        if not result:
            return jsonify({
                'success': False,
                'error': "Une erreur s'est produite lors de l'exécution"
            }), 500

        response = jsonify({
            'success': True,
            'output': result.get('output', ''),
            'error': result.get('error')
        })
        response.headers['Content-Type'] = 'application/json'
        logger.debug(f"Sending response: {response.get_data(as_text=True)}")
        return response

    except CompilerError as e:
        logger.error(f"Compilation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except ExecutionError as e:
        logger.error(f"Execution error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Erreur d'exécution: {str(e)}"
        }), 400

    except Exception as e:
        logger.error(f"Unexpected error in execute_code: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': "Une erreur inattendue s'est produite"
        }), 500

@activities.route('/')
@activities.route('/<grade>')
@limiter.limit("30 per minute")
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Listing activities for curriculum: {curriculum}, language: {language}")
        activities_list = CodingActivity.query.filter_by(
            curriculum=curriculum,
            language=language
        ).order_by(CodingActivity.sequence).all()

        return render_template(
            'activities/list.html',
            activities=activities_list,
            curriculum=curriculum,
            lang=session.get('lang', 'fr'),
            grade=grade
        )

    except Exception as e:
        logger.error(f"Error listing activities: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement des activités.", "danger")
        return redirect(url_for('main.index'))

@activities.route('/activity/<int:activity_id>')
@limiter.limit("30 per minute")
def view_activity(activity_id):
    """View a specific coding activity"""
    try:
        activity = CodingActivity.query.get_or_404(activity_id)
        starter_code = activity.starter_code or TEMPLATES.get(activity.language)

        return render_template(
            'activity.html',
            activity=activity,
            initial_code=starter_code,
            lang=session.get('lang', 'fr')
        )

    except Exception as e:
        logger.error(f"Error viewing activity: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement de l'activité.", "danger")
        return redirect(url_for('activities.list_activities'))

# Default templates for each language
TEMPLATES = {
    'cpp': """#include <iostream>
#include <string>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}""",
    'csharp': """using System;

class Program {
    static void Main() {
        // Votre code ici
    }
}"""
}

@activities.before_request
def before_activities_request():
    """Log activity requests"""
    logger.debug(f"Activity route accessed: {request.endpoint}")