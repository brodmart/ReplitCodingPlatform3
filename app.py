import os
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import LoginManager, current_user, login_user, login_required
from compiler_service import compile_and_run
from database import db
from models import (
    Student, Achievement, StudentAchievement, CodeSubmission, 
    SharedCode, CodingActivity, StudentProgress
)
from sqlalchemy import desc
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime

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

@app.route('/test-login')
def test_login():
    # Check if test user exists
    test_user = Student.query.filter_by(username='test_user').first()
    if not test_user:
        # Create test user
        test_user = Student(
            username='test_user',
            email='test@example.com',
            password_hash=generate_password_hash('password123')
        )
        db.session.add(test_user)
        db.session.commit()

        # Add some test activities progress
        activities = CodingActivity.query.all()
        for activity in activities[:2]:  # Complete first two activities
            progress = StudentProgress(
                student_id=test_user.id,
                activity_id=activity.id,
                completed=True,
                completed_at=datetime.utcnow()
            )
            db.session.add(progress)

        # Add some test achievements
        achievements = Achievement.query.all()
        for achievement in achievements[:3]:  # Add first 3 achievements
            sa = StudentAchievement(student_id=test_user.id, achievement_id=achievement.id)
            db.session.add(sa)

        db.session.commit()
        update_student_score(test_user)

    # Log in the test user
    login_user(test_user)
    flash('Logged in as test user')
    return redirect(url_for('list_activities'))  # Fixed: using correct endpoint name



@app.route('/share', methods=['POST'])
@login_required
def share_code():
    try:
        code = request.json.get('code', '')
        language = request.json.get('language', 'cpp')
        title = request.json.get('title', 'Untitled')
        description = request.json.get('description', '')
        is_public = request.json.get('is_public', True)

        if not code:
            return jsonify({'error': 'No code provided'}), 400

        shared_code = SharedCode(
            student_id=current_user.id,
            code=code,
            language=language,
            title=title,
            description=description,
            is_public=is_public
        )
        db.session.add(shared_code)
        db.session.commit()

        return jsonify({
            'success': True,
            'share_url': url_for('view_shared_code', code_id=shared_code.id, _external=True)
        })

    except Exception as e:
        logging.error(f"Share code error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/shared/<int:code_id>')
def view_shared_code(code_id):
    shared_code = SharedCode.query.get_or_404(code_id)

    if not shared_code.is_public and (not current_user.is_authenticated or current_user.id != shared_code.student_id):
        abort(403)

    # Increment view counter
    shared_code.views += 1
    db.session.commit()

    return render_template('shared_code.html', shared_code=shared_code)

@app.route('/my-shares')
@login_required
def my_shared_codes():
    shared_codes = SharedCode.query.filter_by(student_id=current_user.id).order_by(SharedCode.created_at.desc()).all()
    return render_template('my_shares.html', shared_codes=shared_codes)


@app.route('/activities')
def list_activities():
    """List all coding activities, grouped by curriculum and language"""
    activities = CodingActivity.query.order_by(
        CodingActivity.curriculum,
        CodingActivity.language,
        CodingActivity.sequence
    ).all()

    # Group activities by curriculum and language
    grouped_activities = {}
    for activity in activities:
        key = (activity.curriculum, activity.language)
        if key not in grouped_activities:
            grouped_activities[key] = []
        grouped_activities[key].append(activity)

    # Get student progress if logged in
    progress = {}
    curriculum_progress = {}

    if current_user.is_authenticated:
        logging.debug(f"User authenticated: {current_user.username}")

        # Get all progress entries
        student_progress = StudentProgress.query.filter_by(student_id=current_user.id).all()
        progress = {p.activity_id: p for p in student_progress}
        logging.debug(f"Student progress: {progress}")

        # Calculate curriculum progress
        for curriculum in ['TEJ2O', 'ICS3U']:
            curriculum_activities = CodingActivity.query.filter_by(curriculum=curriculum).all()
            total = len(curriculum_activities)

            if total > 0:
                completed = StudentProgress.query.filter(
                    StudentProgress.student_id == current_user.id,
                    StudentProgress.activity_id.in_([a.id for a in curriculum_activities]),
                    StudentProgress.completed == True
                ).count()

                curriculum_progress[curriculum] = {
                    'completed': completed,
                    'total': total,
                    'percentage': (completed / total * 100)
                }
                logging.debug(f"Curriculum {curriculum} progress: {curriculum_progress[curriculum]}")

    logging.debug(f"Final curriculum_progress: {curriculum_progress}")
    logging.debug(f"Rendering template with progress data")

    return render_template(
        'activities.html',
        grouped_activities=grouped_activities,
        progress=progress,
        curriculum_progress=curriculum_progress
    )

@app.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    """View a specific coding activity"""
    activity = CodingActivity.query.get_or_404(activity_id)

    # Get student's progress for this activity
    progress = None
    if current_user.is_authenticated:
        progress = StudentProgress.query.filter_by(
            student_id=current_user.id,
            activity_id=activity_id
        ).first()

        # Create progress entry if it doesn't exist
        if not progress:
            progress = StudentProgress(
                student_id=current_user.id,
                activity_id=activity_id
            )
            db.session.add(progress)
            db.session.commit()

    return render_template(
        'activity.html',
        activity=activity,
        progress=progress
    )

@app.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
def submit_activity(activity_id):
    """Submit a solution for a coding activity"""
    activity = CodingActivity.query.get_or_404(activity_id)
    code = request.json.get('code', '')

    if not code:
        return jsonify({'error': 'No code provided'}), 400

    # Get or create progress
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id,
        activity_id=activity_id
    ).first()

    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            activity_id=activity_id
        )
        db.session.add(progress)

    # Update progress
    progress.attempts += 1
    progress.last_submission = code

    # Execute code against test cases
    all_tests_passed = True
    test_results = []

    for test_case in activity.test_cases:
        result = compile_and_run(
            code=code,
            language=activity.language,
            input_data=test_case.get('input')
        )

        test_passed = (
            result.get('success', False) and
            result.get('output', '').strip() == str(test_case.get('output')).strip()
        )

        test_results.append({
            'input': test_case.get('input'),
            'expected': test_case.get('output'),
            'actual': result.get('output'),
            'passed': test_passed,
            'error': result.get('error')
        })

        if not test_passed:
            all_tests_passed = False

    # Update progress if all tests passed
    if all_tests_passed:
        progress.completed = True
        progress.completed_at = datetime.utcnow()

        # Award points to student
        current_user.score += activity.points

        flash(f'Congratulations! You completed "{activity.title}" and earned {activity.points} points!')

    db.session.commit()

    return jsonify({
        'success': all_tests_passed,
        'test_results': test_results,
        'attempts': progress.attempts
    })

# Initialize database with some example activities
def create_initial_activities():
    # Only create if no activities exist
    if CodingActivity.query.first():
        return

    activities = [
        # TEJ2O C++ Activities (Grade 10)
        {
            'title': 'Bonjour, le monde!',
            'description': 'Introduction à la programmation C++ et sortie de base.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 1,
            'instructions': 'Écrivez votre premier programme C++ qui affiche "Bonjour, le monde!" dans la console. Cela introduit la structure de base du programme et la sortie.',
            'starter_code': '#include <iostream>\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    std::cout << "Bonjour, le monde!" << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '', 'output': 'Bonjour, le monde!'}],
            'hints': ['N\'oubliez pas d\'inclure iostream', 'Utilisez std::cout pour la sortie', 'Terminez avec return 0'],
            'points': 10
        },
        {
            'title': 'Saisie de Base',
            'description': 'Apprenez à recevoir les entrées utilisateur en C++',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 2,
            'instructions': 'Créez un programme qui demande le nom de l\'utilisateur et le salue personnellement.',
            'starter_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string nom;\n    // Ajoutez votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string nom;\n    std::cout << "Entrez votre nom: ";\n    std::getline(std::cin, nom);\n    std::cout << "Bonjour, " << nom << "!" << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': 'Alice\n', 'output': 'Entrez votre nom: Bonjour, Alice!'},
                {'input': 'Bob\n', 'output': 'Entrez votre nom: Bonjour, Bob!'}
            ],
            'hints': ['Utilisez std::string pour le texte', 'std::cin >> nom ne lira qu\'un mot', 'std::getline est préférable pour les noms complets'],
            'points': 15
        },
        {
            'title': 'Calculatrice Simple',
            'description': 'Créez une calculatrice de base utilisant les opérateurs arithmétiques',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 3,
            'instructions': 'Écrivez un programme qui additionne deux nombres saisis par l\'utilisateur.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int num1, num2;\n    // Ajoutez votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int num1, num2;\n    std::cout << "Entrez le premier nombre: ";\n    std::cin >> num1;\n    std::cout << "Entrez le deuxième nombre: ";\n    std::cin >> num2;\n    std::cout << "Somme: " << num1 + num2 << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '5\n3\n', 'output': 'Entrez le premier nombre: Entrez le deuxième nombre: Somme: 8'},
                {'input': '10\n20\n', 'output': 'Entrez le premier nombre: Entrez le deuxième nombre: Somme: 30'}
            ],
            'hints': ['Utilisez int pour les nombres entiers', 'N\'oubliez pas de demander chaque entrée', 'Utilisez l\'opérateur + pour l\'addition'],
            'points': 20
        },
        # ICS3U/3C C# Activities (Grade 11)
        {
            'title': 'Introduction à C#',
            'description': 'Premiers pas en programmation C# avec les conventions de nommage appropriées',
            'difficulty': 'beginner',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 1,
            'instructions': 'Créez votre premier programme C# en utilisant la convention de nommage Pascal Case.',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}',
            'solution_code': 'using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Bonjour, le monde!");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Bonjour, le monde!'}],
            'hints': ['Les noms de classe utilisent PascalCase', 'Les noms de méthodes utilisent PascalCase', 'Utilisez Console.WriteLine() pour la sortie'],
            'points': 10
        },
        {
            'title': 'Manipulation de Chaînes',
            'description': 'Travailler avec les chaînes et les méthodes de chaîne en C#',
            'difficulty': 'beginner',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 2,
            'instructions': 'Créez un programme qui prend le nom complet d\'un utilisateur et l\'affiche en majuscules.',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        string nomComplet;\n        // Votre code ici\n    }\n}',
            'solution_code': 'using System;\n\nclass Program {\n    static void Main() {\n        string nomComplet;\n        Console.Write("Entrez votre nom complet: ");\n        nomComplet = Console.ReadLine();\n        Console.WriteLine($"Votre nom en majuscules: {nomComplet.ToUpper()}");\n    }\n}',
            'test_cases': [
                {'input': 'John Doe\n', 'output': 'Entrez votre nom complet: Votre nom en majuscules: JOHN DOE'},
                {'input': 'Jane Smith\n', 'output': 'Entrez votre nom complet: Votre nom en majuscules: JANE SMITH'}
            ],
            'hints': ['Utilisez Console.ReadLine() pour l\'entrée', 'Les méthodes de chaîne comme ToUpper() sont utiles', 'Essayez l\'interpolation de chaîne avec $'],
            'points': 15
        },
        {
            'title': 'Méthodes de Base',
            'description': 'Introduction aux méthodes et paramètres',
            'difficulty': 'beginner',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 3,
            'instructions': 'Créez une méthode qui calcule l\'aire d\'un rectangle.',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Appelez votre méthode CalculerAire ici\n    }\n\n    // Créez votre méthode CalculerAire ici\n}',
            'solution_code': 'using System;\n\nclass Program {\n    static void Main() {\n        Console.Write("Entrez la largeur: ");\n        double largeur = Convert.ToDouble(Console.ReadLine());\n        Console.Write("Entrez la hauteur: ");\n        double hauteur = Convert.ToDouble(Console.ReadLine());\n        \n        double aire = CalculerAire(largeur, hauteur);\n        Console.WriteLine($"L\'aire est: {aire}");\n    }\n\n    static double CalculerAire(double largeur, double hauteur) {\n        return largeur * hauteur;\n    }\n}',
            'test_cases': [
                {'input': '5\n3\n', 'output': 'Entrez la largeur: Entrez la hauteur: L\'aire est: 15'},
                {'input': '4\n4\n', 'output': 'Entrez la largeur: Entrez la hauteur: L\'aire est: 16'}
            ],
            'hints': ['Les méthodes doivent faire une tâche spécifique', 'Utilisez des noms de paramètres significatifs', 'N\'oubliez pas de convertir l\'entrée string en double'],
            'points': 20
        }
    ]

    for activity_data in activities:
        activity = CodingActivity(**activity_data)
        db.session.add(activity)

    db.session.commit()

# Initialize activities in app context
with app.app_context():
    create_initial_activities()