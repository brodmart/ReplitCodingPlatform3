from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_wtf.csrf import CSRFProtect
from models import CodingActivity, db
from extensions import limiter, cache
import logging
from compiler_service import compile_and_run, CompilerError, ExecutionError

activities = Blueprint('activities', __name__)
logger = logging.getLogger(__name__)

@activities.route('/')
@activities.route('/<grade>')
@limiter.limit("30 per minute")
def list_activities(grade=None):
    """List all coding activities for a specific grade"""
    try:
        # Convert grade parameter to curriculum code and set language
        if grade == '11':
            curriculum = 'ICS3U'
            language = 'csharp'
        else:  # Default to grade 10
            curriculum = 'TEJ2O'
            language = 'cpp'

        logger.debug(f"Listing activities for curriculum: {curriculum}, language: {language}")

        # Build query with both curriculum and language filters
        query = CodingActivity.query.filter_by(
            curriculum=curriculum,
            language=language
        ).order_by(CodingActivity.sequence)

        activities_list = query.all()
        logger.debug(f"Found {len(activities_list)} activities")

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
        # Get the activity and verify it exists
        activity = CodingActivity.query.get_or_404(activity_id)

        # Log the activity details for debugging
        logger.debug(f"Loading activity {activity_id}: {activity.title}")
        logger.debug(f"Curriculum: {activity.curriculum}, Language: {activity.language}")
        logger.debug(f"Starter code length: {len(activity.starter_code) if activity.starter_code else 0}")
        logger.debug(f"Hints: {activity.hints}")
        logger.debug(f"Common errors: {activity.common_errors}")

        # Use activity's starter code from database
        starter_code = activity.starter_code

        # If no starter code in database, use appropriate template based on language
        if not starter_code:
            if activity.language == 'cpp':
                starter_code = """#include <iostream>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}"""
            else:  # C#
                starter_code = """using System;

class Program {
    static void Main() {
        // Votre code ici
    }
}"""

        return render_template(
            'activity.html',
            activity=activity,
            initial_code=starter_code,
            hints=activity.hints,
            common_errors=activity.common_errors,
            lang=session.get('lang', 'fr')
        )

    except Exception as e:
        logger.error(f"Error viewing activity: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement de l'activité.", "danger")
        return redirect(url_for('activities.list_activities'))

@activities.route('/execute', methods=['POST'])
@limiter.limit("20 per minute")
def execute_code():
    """Execute submitted code and return the results"""
    try:
        if not request.is_json:
            logger.error("Invalid request format - JSON required")
            return jsonify({
                'success': False,
                'error': 'Format de requête invalide'
            }), 400

        data = request.get_json()
        if not data:
            logger.error("No JSON data in request")
            return jsonify({
                'success': False,
                'error': 'Données invalides'
            }), 400

        code = data.get('code', '').strip()
        language = data.get('language', 'cpp').lower()

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

        logger.debug(f"Executing {language} code")
        result = compile_and_run(code, language)

        if not result:
            return jsonify({
                'success': False,
                'error': "Une erreur s'est produite lors de l'exécution"
            }), 500

        return jsonify({
            'success': True,
            'output': result.get('output', ''),
            'error': result.get('error')
        })

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

@activities.before_request
def before_activities_request():
    """Log activity requests"""
    logger.debug(f"Activity route accessed: {request.endpoint}")