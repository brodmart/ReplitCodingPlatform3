from flask import Blueprint, render_template, jsonify, session, request
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

curriculum_bp = Blueprint('curriculum', __name__)

@curriculum_bp.route('/')
def view_curriculum():
    """Display the curriculum visualization page"""
    # Get the current language from session or default to English
    lang = session.get('lang', request.args.get('lang', 'en'))
    # Get all courses
    courses = Course.query.all()
    return render_template('curriculum/view.html', courses=courses, lang=lang)

@curriculum_bp.route('/get_course_data/<course_code>')
def get_course_data(course_code):
    """Get curriculum data for a specific course"""
    course = Course.query.filter_by(code=course_code).first_or_404()
    # Get the current language from session or default to English
    lang = session.get('lang', request.args.get('lang', 'en'))

    # Build curriculum structure
    curriculum_data = {
        'code': course.code,
        'title': course.title_fr if lang == 'fr' else course.title_en,
        'description': course.description_fr if lang == 'fr' else course.description_en,
        'strands': []
    }

    # Sort strands by code to ensure consistent order
    sorted_strands = sorted(course.strands, key=lambda x: x.code.upper())

    for strand in sorted_strands:
        # Fix strand title casing and formatting
        strand_code = strand.code.upper()
        strand_data = {
            'code': strand_code,
            'title': strand.title_fr if lang == 'fr' else strand.title_en,
            'overall_expectations': []
        }

        # Sort overall expectations by code
        sorted_overall = sorted(strand.overall_expectations, 
                              key=lambda x: x.code.upper())

        for overall in sorted_overall:
            overall_data = {
                'code': overall.code,
                'description': overall.description_fr if lang == 'fr' else overall.description_en,
                'specific_expectations': []
            }

            # Sort specific expectations by code
            sorted_specific = sorted(overall.specific_expectations, 
                                   key=lambda x: x.code.upper())

            for specific in sorted_specific:
                specific_data = {
                    'code': specific.code,
                    'description': specific.description_fr if lang == 'fr' else specific.description_en
                }
                overall_data['specific_expectations'].append(specific_data)

            strand_data['overall_expectations'].append(overall_data)

        curriculum_data['strands'].append(strand_data)

    return jsonify(curriculum_data)