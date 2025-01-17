"""
Activity routes with curriculum compliance integration
"""
from flask import Blueprint, jsonify, request, render_template, abort
from utils.curriculum_checker import CurriculumChecker
from models import db, Activity, Student
import logging

logger = logging.getLogger(__name__)
activities_bp = Blueprint('activities', __name__)
curriculum_checker = CurriculumChecker()

@activities_bp.route('/activities/enhanced/<int:activity_id>')
def enhanced_learning(activity_id):
    """
    Enhanced learning interface with curriculum alignment
    """
    try:
        activity = Activity.query.get_or_404(activity_id)
        # Default to English, can be made dynamic based on user preferences
        lang = request.args.get('lang', 'en')
        # Default to ICS4U, can be made dynamic based on student's grade level
        curriculum = request.args.get('curriculum', 'ICS4U')

        if activity.starter_code is None:
            activity.starter_code = ''
        elif not isinstance(activity.starter_code, str):
            activity.starter_code = str(activity.starter_code)

        return render_template(
            'activities/view.html',  # Use existing view template
            activity=activity,
            lang=lang,
            curriculum=curriculum
        )
    except Exception as e:
        logger.error(f"Error loading enhanced learning interface: {str(e)}")
        abort(404)

@activities_bp.route('/activities/validate', methods=['POST'])
def validate_activity():
    """
    Validate an activity against curriculum expectations
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    validation_result = curriculum_checker.validate_activity(data)
    return jsonify(validation_result)

@activities_bp.route('/activities/student-progress/<int:student_id>')
def get_student_progress(student_id):
    """
    Get student's progress against curriculum expectations
    """
    student = Student.query.get_or_404(student_id)
    progress = curriculum_checker.get_student_progress(student_id)
    return jsonify(progress)

@activities_bp.route('/activities/suggest/<int:student_id>')
def suggest_activities(student_id):
    """
    Get activity suggestions based on curriculum progress
    """
    suggestions = curriculum_checker.suggest_next_activities(student_id)
    return jsonify({"suggestions": suggestions})