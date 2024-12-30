import os
import logging
from flask import Flask, render_template, request, jsonify, flash
from flask_login import LoginManager, current_user
from compiler_service import compile_and_run
from database import db
from models import Student, Achievement, StudentAchievement, CodeSubmission
from sqlalchemy import desc

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

def update_student_score(student):
    """Update student's score based on achievements and successful submissions"""
    achievement_points = sum(sa.achievement.points for sa in student.achievements)
    submission_points = student.successful_submissions * 5  # 5 points per successful submission
    student.score = achievement_points + submission_points
    db.session.commit()

def check_achievements(student, submission):
    """Check and award achievements based on student's progress"""
    # Get all achievements
    achievements = Achievement.query.all()
    awarded = False

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
                    awarded = True
                    flash(f'Achievement Unlocked: {achievement.name}!')
            elif criterion == 'error_fixes': #Added for new achievement criteria
                error_fixes = CodeSubmission.query.filter_by(student_id=student.id, success=False).count()
                if error_fixes >= value:
                    new_achievement = StudentAchievement(student_id=student.id, achievement_id=achievement.id)
                    db.session.add(new_achievement)
                    awarded = True
                    flash(f'Achievement Unlocked: {achievement.name}!')
            elif criterion == 'languages': #Added for new achievement criteria
                languages = set(s.language for s in CodeSubmission.query.filter_by(student_id=student.id))
                if len(languages) >= value:
                    new_achievement = StudentAchievement(student_id=student.id, achievement_id=achievement.id)
                    db.session.add(new_achievement)
                    awarded = True
                    flash(f'Achievement Unlocked: {achievement.name}!')

    if awarded:
        db.session.commit()
        update_student_score(student)

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

            # Update student score
            update_student_score(current_user)

            # Check for new achievements
            check_achievements(current_user, submission)

        return jsonify(result)

    except Exception as e:
        logging.error(f"Execution error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/leaderboard')
def leaderboard():
    # Get top 10 students by score
    top_students = Student.query.order_by(desc(Student.score)).limit(10).all()

    # Get current user's rank if authenticated
    current_user_rank = None
    if current_user.is_authenticated:
        current_user_rank = Student.query.filter(Student.score > current_user.score).count() + 1

    return render_template('leaderboard.html', 
                         top_students=top_students,
                         current_user_rank=current_user_rank)


# Create initial achievements
def create_initial_achievements():
    achievements = [
        # Beginner Tier
        {
            'name': 'First Steps',
            'description': 'Write and execute your first program',
            'criteria': 'submit_count:1',
            'badge_icon': 'bi-1-circle-fill text-success',
            'points': 10,
            'category': 'beginner'
        },
        {
            'name': 'Quick Learner',
            'description': 'Submit 5 successful programs',
            'criteria': 'submit_count:5',
            'badge_icon': 'bi-lightning-fill text-warning',
            'points': 25,
            'category': 'beginner'
        },
        # Intermediate Tier
        {
            'name': 'Code Warrior',
            'description': 'Submit 10 successful programs',
            'criteria': 'submit_count:10',
            'badge_icon': 'bi-trophy-fill text-info',
            'points': 50,
            'category': 'intermediate'
        },
        {
            'name': 'Bug Hunter',
            'description': 'Fix and resubmit 5 programs that had errors',
            'criteria': 'error_fixes:5',
            'badge_icon': 'bi-bug-fill text-danger',
            'points': 75,
            'category': 'intermediate'
        },
        # Advanced Tier
        {
            'name': 'Code Master',
            'description': 'Submit 50 successful programs',
            'criteria': 'submit_count:50',
            'badge_icon': 'bi-star-fill text-warning',
            'points': 100,
            'category': 'advanced'
        },
        {
            'name': 'Polyglot',
            'description': 'Successfully write programs in both C++ and C#',
            'criteria': 'languages:2',
            'badge_icon': 'bi-code-square text-primary',
            'points': 150,
            'category': 'advanced'
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