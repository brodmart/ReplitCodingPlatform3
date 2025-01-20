from flask import Blueprint, render_template, jsonify
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

curriculum_bp = Blueprint('curriculum', __name__)

@curriculum_bp.route('/')
def view_curriculum():
    """Display the curriculum visualization page"""
    # Get all courses
    courses = Course.query.all()
    return render_template('curriculum/view.html', courses=courses)

@curriculum_bp.route('/get_course_data/<course_code>')
def get_course_data(course_code):
    """Get curriculum data for a specific course"""
    course = Course.query.filter_by(code=course_code).first_or_404()
    
    # Build curriculum structure
    curriculum_data = {
        'code': course.code,
        'title_en': course.title_en,
        'title_fr': course.title_fr,
        'strands': []
    }
    
    for strand in course.strands:
        strand_data = {
            'code': strand.code,
            'title_en': strand.title_en,
            'title_fr': strand.title_fr,
            'overall_expectations': []
        }
        
        for overall in strand.overall_expectations:
            overall_data = {
                'code': overall.code,
                'description_en': overall.description_en,
                'description_fr': overall.description_fr,
                'specific_expectations': []
            }
            
            for specific in overall.specific_expectations:
                specific_data = {
                    'code': specific.code,
                    'description_en': specific.description_en,
                    'description_fr': specific.description_fr
                }
                overall_data['specific_expectations'].append(specific_data)
            
            strand_data['overall_expectations'].append(overall_data)
        
        curriculum_data['strands'].append(strand_data)
    
    return jsonify(curriculum_data)
