import os
import logging
from flask import Flask, render_template, request, jsonify, flash
from flask_login import LoginManager, current_user
from compiler_service import compile_and_run
from database import db
from models import Student, Achievement, StudentAchievement, CodeSubmission

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    return Student.query.get(int(id))

def check_achievements(student, submission):
    """Check and award achievements based on student's progress"""
    # Get all achievements
    achievements = Achievement.query.all()

    for achievement in achievements:
        # Parse criteria
        criterion, value = achievement.criteria.split(':')
        value = int(value)

        # Check if student already has this achievement
        if not StudentAchievement.query.filter_by(
            student_id=student.id, 
            achievement_id=achievement.id
        ).first():
            # Check different types of criteria
            if criterion == 'submit_count':
                submit_count = CodeSubmission.query.filter_by(
                    student_id=student.id
                ).count()
                if submit_count >= value:
                    # Award achievement
                    new_achievement = StudentAchievement(
                        student_id=student.id,
                        achievement_id=achievement.id
                    )
                    db.session.add(new_achievement)
                    db.session.commit()
                    flash(f'Achievement Unlocked: {achievement.name}!')

@app.route('/')
def index():
    # Get student's achievements if logged in
    achievements = []
    if current_user.is_authenticated:
        achievements = [sa.achievement for sa in current_user.achievements]
    return render_template('index.html', achievements=achievements)

@app.route('/execute', methods=['POST'])
def execute():
    try:
        code = request.json.get('code', '')
        language = request.json.get('language', 'cpp')

        if not code:
            return jsonify({'error': 'No code provided'}), 400

        # Execute code
        result = compile_and_run(code, language)

        # If user is authenticated, track submission
        if current_user.is_authenticated:
            submission = CodeSubmission(
                student_id=current_user.id,
                language=language,
                code=code,
                success=result.get('success', False),
                output=result.get('output', ''),
                error=result.get('error', '')
            )
            db.session.add(submission)
            db.session.commit()

            # Check for new achievements
            check_achievements(current_user, submission)

        return jsonify(result)

    except Exception as e:
        logging.error(f"Execution error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Create initial achievements
def create_initial_achievements():
    achievements = [
        {
            'name': 'First Code',
            'description': 'Submit your first code',
            'criteria': 'submit_count:1',
            'badge_icon': 'bi-1-circle'
        },
        {
            'name': 'Code Warrior',
            'description': 'Submit 10 code snippets',
            'criteria': 'submit_count:10',
            'badge_icon': 'bi-trophy'
        },
        {
            'name': 'Code Master',
            'description': 'Submit 50 code snippets',
            'criteria': 'submit_count:50',
            'badge_icon': 'bi-star-fill'
        }
    ]

    for achievement_data in achievements:
        if not Achievement.query.filter_by(name=achievement_data['name']).first():
            achievement = Achievement(**achievement_data)
            db.session.add(achievement)

    db.session.commit()

# Initialize database and achievements
with app.app_context():
    db.create_all()
    create_initial_achievements()