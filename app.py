import os
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import LoginManager, current_user, login_user, login_required, logout_user
from flask_migrate import Migrate
from compiler_service import compile_and_run
from database import db
from models import (
    Student, Achievement, StudentAchievement, CodeSubmission, 
    SharedCode, CodingActivity, StudentProgress, TutorialStep, TutorialProgress
)
from sqlalchemy import desc
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
from forms import LoginForm, RegisterForm, ProfileForm
from werkzeug.utils import secure_filename
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
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
            elif criterion == 'error_fixes':
                error_fixes = CodeSubmission.query.filter_by(student_id=student.id, success=False).count()
                if error_fixes >= value:
                    new_achievement = StudentAchievement(student_id=student.id, achievement_id=achievement.id)
                    db.session.add(new_achievement)
                    awarded = True
                    flash(f'Achievement Unlocked: {achievement.name}!')
            elif criterion == 'languages':
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

    return render_template(
        'activities.html',
        grouped_activities=grouped_activities,
        progress=progress,
        curriculum_progress=curriculum_progress
    )

@app.route('/activity/<int:activity_id>')
@login_required
def activity(activity_id):
    activity = CodingActivity.query.get_or_404(activity_id)
    return redirect(url_for('tutorial', activity_id=activity_id, step=1))


@app.route('/activity/<int:activity_id>/submit', methods=['POST'])
@login_required
def submit_activity(activity_id):
    """Submit a solution for a coding activity"""
    activity = CodingActivity.query.get_or_404(activity_id)
    code = request.json.get('code', '')

    if not code:
        return jsonify({'error': 'Aucun code fourni'}), 400

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

        flash(f'Félicitations! Vous avez terminé "{activity.title}" et gagné {activity.points} points!')

    db.session.commit()

    return jsonify({
        'success': all_tests_passed,
        'test_results': test_results,
        'attempts': progress.attempts
    })

@app.route('/tutorial/<int:activity_id>/<int:step>', methods=['GET'])
def tutorial(activity_id, step):
    activity = CodingActivity.query.get_or_404(activity_id)
    # tutorial_steps are now automatically ordered by step_number
    tutorial_steps = activity.tutorial_steps
    total_steps = len(tutorial_steps)

    if step < 1 or step > total_steps:
        return redirect(url_for('tutorial', activity_id=activity_id, step=1))

    current_step = step
    current_tutorial_step = tutorial_steps[step - 1]

    show_hint = request.args.get('hint', 'false').lower() == 'true'

    # Check if user has completed this step
    if current_user.is_authenticated:
        progress = TutorialProgress.query.filter_by(
            student_id=current_user.id,
            step_id=current_tutorial_step.id
        ).first()
        step_completed = progress and progress.completed
    else:
        step_completed = False

    prev_step = current_step > 1
    next_step = current_step < total_steps

    return render_template('tutorial.html',
                     activity=activity,
                     current_step=current_step,
                     total_steps=total_steps,
                     current_tutorial_step=current_tutorial_step,
                     prev_step=prev_step,
                     next_step=next_step,
                     show_hint=show_hint,
                     step_completed=step_completed)

@app.route('/verify_tutorial_step/<int:activity_id>/<int:step>', methods=['POST'])
@login_required
def verify_tutorial_step(activity_id, step):
    activity = CodingActivity.query.get_or_404(activity_id)
    # Get all tutorial steps, they are already ordered by step_number
    tutorial_steps = activity.tutorial_steps
    current_tutorial_step = tutorial_steps[step - 1]

    code = request.json.get('code', '')

    # Verify the code matches the solution for this step
    success = False
    if step == len(tutorial_steps):  # Final step
        # For the final step, verify against the full solution
        success = code.strip() == activity.solution_code.strip()
    else:
        # For intermediate steps, you might want to implement partial solution checking
        success = True  # Simplified for now

    if success:
        # Update progress
        progress = TutorialProgress.query.filter_by(
            student_id=current_user.id,
            step_id=current_tutorial_step.id
        ).first()

        if not progress:
            progress = TutorialProgress(
                student=current_user,
                step=current_tutorial_step
            )
            db.session.add(progress)

        progress.completed = True
        progress.completed_at = datetime.utcnow()
        db.session.commit()

    return jsonify({'success': success})


# Create initial achievements
def create_initial_achievements():
    achievements = [
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

def create_initial_activities():
    # First, remove all existing activities and related records
    TutorialProgress.query.delete()
    TutorialStep.query.delete()
    StudentProgress.query.delete()
    CodingActivity.query.delete()

    # C++ Activities (10 activities)
    cpp_activities = [
        {
            'title': 'Bonjour le monde!',
            'description': 'Introduction à la programmation C++ avec une sortie simple.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 1,
            'instructions': 'Écrivez votre premier programme C++ qui affiche "Bonjour le monde!" dans la console.',
            'starter_code': '#include <iostream>\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    std::cout << "Bonjour le monde!" << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '', 'output': 'Bonjour le monde!'}],
            'points': 10,
            'complexity_analysis': {
                'cognitive_load': 'low',
                'concepts': ['basic syntax', 'iostream', 'main function'],
                'common_mistakes': ['forgetting semicolon', 'misspelling cout']
            },
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Comprendre la structure de base',
                    'content': 'Dans C++, chaque programme commence par des *includes* et une fonction principale appelée `main`.',
                    'code_snippet': '#include <iostream>\n\nint main() {\n    return 0;\n}',
                    'hint': 'Regardez la syntaxe de base'
                },
                {
                    'step_number': 2,
                    'title': 'Ajouter l\'instruction d\'affichage',
                    'content': 'Utilisez std::cout pour afficher du texte',
                    'code_snippet': 'std::cout << "Bonjour le monde!" << std::endl;',
                    'hint': 'N\'oubliez pas le point-virgule'
                }
            ]
        },
        {
            'title': 'Calculatrice Simple',
            'description': 'Créer une calculatrice simple qui effectue des opérations de base.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 2,
            'instructions': 'Créez une calculatrice qui peut additionner, soustraire, multiplier et diviser deux nombres.',
            'starter_code': '#include <iostream>\n\nint main() {\n    double a, b;\n    char operation;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    double a, b;\n    char operation;\n    std::cout << "Entrez deux nombres et une opération (+,-,*,/): ";\n    std::cin >> a >> operation >> b;\n    \n    switch(operation) {\n        case \'+\': std::cout << a + b; break;\n        case \'-\': std::cout << a - b; break;\n        case \'*\': std::cout << a * b; break;\n        case \'/\': if(b != 0) std::cout << a / b;\n                  else std::cout << "Division par zéro!";\n                  break;\n        default: std::cout << "Opération invalide!";\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '5 + 3', 'output': '8'},
                {'input': '10 - 4', 'output': '6'},
                {'input': '3 * 5', 'output': '15'},
                {'input': '15 / 3', 'output': '5'}
            ],
            'points': 15,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['user input', 'switch statement', 'arithmetic operations'],
                'common_mistakes': ['division by zero', 'incorrect operator handling']
            }
        },
        {
            'title': 'Structures de Contrôle',
            'description': 'Apprendre à utiliser les instructions if/else en C++.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 3,
            'instructions': 'Créez un programme qui utilise des structures conditionnelles pour classer des notes.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int note;\n    std::cout << "Entrez une note: ";\n    std::cin >> note;\n    \n    // Ajoutez vos conditions ici\n    \n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int note;\n    std::cout << "Entrez une note: ";\n    std::cin >> note;\n    \n    if (note >= 90) {\n        std::cout << "Excellent!" << std::endl;\n    } else if (note >= 75) {\n        std::cout << "Très bien!" << std::endl;\n    } else if (note >= 60) {\n        std::cout << "Passable" << std::endl;\n    } else {\n        std::cout << "Échec" << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '95', 'output': 'Excellent!'},
                {'input': '80', 'output': 'Très bien!'},
                {'input': '65', 'output': 'Passable'},
                {'input': '55', 'output': 'Échec'}
            ],
            'points': 20,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['conditional statements', 'user input', 'comparison operators'],
                'common_mistakes': ['wrong comparison operator', 'incorrect order of conditions']
            },
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Structure if/else',
                    'content': 'Les structures conditionnelles permettent de prendre des décisions dans le code.',
                    'code_snippet': 'if (condition) {\n    // code si vrai\n} else {\n    // code si faux\n}',
                    'hint': 'Commencez par la note la plus élevée'
                },
                {
                    'step_number': 2,
                    'title': 'Conditions multiples',
                    'content': 'Utilisez else if pour tester plusieurs conditions.',
                    'code_snippet': 'if (note >= 90) {\n    // excellent\n} else if (note >= 75) {\n    // très bien\n}',
                    'hint': 'Vérifiez que vos conditions sont dans le bon ordre'
                }
            ]
        },
        {
            'title': 'Boucles en C++',
            'description': 'Maîtriser les boucles for et while en C++.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 4,
            'instructions': 'Créez un programme qui calcule la somme des nombres de 1 à n.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> n;\n    // Calculez la somme ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> n;\n    \n    int somme = 0;\n    for(int i = 1; i <= n; i++) {\n        somme += i;\n    }\n    std::cout << "La somme est: " << somme << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '5', 'output': 'La somme est: 15'},
                {'input': '10', 'output': 'La somme est: 55'}
            ],
            'points': 25,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['loops', 'accumulator pattern', 'arithmetic'],
                'common_mistakes': ['off-by-one errors', 'incorrect loop bounds']
            },
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Structure de la boucle',
                    'content': 'La boucle for est parfaite pour répéter une action un nombre connu de fois.',
                    'code_snippet': 'for(int i = 1; i <= n; i++) {\n    // Code répété\n}',
                    'hint': 'Initialisez un compteur pour la somme avant la boucle'
                }
            ]
        },
        {
            'title': 'Tableaux en C++',
            'description': 'Manipulation des tableaux et calculs statistiques.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 5,
            'instructions': 'Créez un programme qui trouve le maximum et le minimum dans un tableau.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int nombres[] = {12, 5, 23, 9, 30};\n    // Trouvez min et max\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int nombres[] = {12, 5, 23, 9, 30};\n    int min = nombres[0];\n    int max = nombres[0];\n    \n    for(int i = 1; i < 5; i++) {\n        if(nombres[i] < min) min = nombres[i];\n        if(nombres[i] > max) max = nombres[i];\n    }\n    \n    std::cout << "Min: " << min << ", Max: " << max << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '', 'output': 'Min: 5, Max: 30'}],
            'points': 30,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['arrays', 'loops', 'conditional logic'],
                'common_mistakes': ['array bounds', 'initialization errors']
            }
        },
        {
            'title': 'Fonctions en C++',
            'description': 'Création et utilisation de fonctions.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 6,
            'instructions': 'Créez des fonctions pour calculer le périmètre et l\'aire d\'un rectangle.',
            'starter_code': '#include <iostream>\n\n// Définissez vos fonctions ici\n\nint main() {\n    double longueur, largeur;\n    std::cin >> longueur >> largeur;\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\ndouble perimetre(double l, double w) {\n    return 2 * (l + w);\n}\n\ndouble aire(double l, double w) {\n    return l * w;\n}\n\nint main() {\n    double longueur, largeur;\n    std::cin >> longueur >> largeur;\n    std::cout << "Périmètre: " << perimetre(longueur, largeur) << std::endl;\n    std::cout << "Aire: " << aire(longueur, largeur) << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '5 3', 'output': 'Périmètre: 16\nAire: 15'}],
            'points': 35,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['functions', 'parameters', 'return values'],
                'common_mistakes': ['missing return statement', 'parameter order']
            }
        },
        {
            'title': 'Chaînes de caractères',
            'description': 'Manipulation des chaînes en C++.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 7,
            'instructions': 'Créez un programme qui inverse une chaîne de caractères.',
            'starter_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string texte;\n    std::getline(std::cin, texte);\n    // Inversez la chaîne ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string texte;\n    std::getline(std::cin, texte);\n    std::string inverse;\n    for(int i = texte.length() - 1; i >= 0; i--) {\n        inverse += texte[i];\n    }\n    std::cout << inverse << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': 'Bonjour', 'output': 'ruojnoB'}],
            'points': 35,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['strings', 'loops', 'concatenation'],
                'common_mistakes': ['string bounds', 'off-by-one errors']
            }
        },
        {
            'title': 'Structures de données',
            'description': 'Utilisation des structures en C++.',
            'difficulty': 'advanced',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 8,
            'instructions': 'Créez une structure pour représenter un point 2D et calculez la distance entre deux points.',
            'starter_code': '#include <iostream>\n#include <cmath>\n\nstruct Point {\n    double x, y;\n};\n\n// Ajoutez votre fonction ici\n\nint main() {\n    Point p1, p2;\n    std::cin >> p1.x >> p1.y >> p2.x >> p2.y;\n    return 0;\n}',
            'solution_code': '#include <iostream>\n#include <cmath>\n\nstruct Point {\n    double x, y;\n};\n\ndouble distance(Point p1, Point p2) {\n    return sqrt(pow(p2.x - p1.x, 2) + pow(p2.y - p1.y, 2));\n}\n\nint main() {\n    Point p1, p2;\n    std::cin >> p1.x >> p1.y >> p2.x >> p2.y;\n    std::cout << "Distance: " << distance(p1, p2) << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '0 0 3 4', 'output': 'Distance: 5'}],
            'points': 40,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['structures', 'functions', 'math operations'],
                'common_mistakes': ['incorrect math formula', 'parameter passing']
            }
        },
        {
            'title': 'Pointeurs et Références',
            'description': 'Comprendre les pointeurs et références en C++.',
            'difficulty': 'advanced',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 9,
            'instructions': 'Créezun programme qui échange deux valeurs en utilisant des pointeurs.',
            'starter_code': '#include <iostream>\n\nvoid echange(int* a, int* b) {\n    // Implémentez l\'échange ici\n}\n\nint main() {\n    int x, y;\n    std::cin >> x >> y;\n    echange(&x, &y);\n    std::cout << x << " " << y << std::endl;\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nvoid echange(int* a, int* b) {\n    int temp = *a;\n    *a = *b;\n    *b = temp;\n}\n\nint main() {\n    int x, y;\n    std::cin >> x >> y;\n    echange(&x, &y);\n    std::cout << x << " " << y << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '5 10', 'output': '10 5'}],
            'points': 45,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['pointers', 'memory management', 'parameter passing'],
                'common_mistakes': ['dereferencing errors', 'memory leaks']
            }
        },
        {
            'title': 'Fichiers et Flux',
            'description': 'Manipulation des fichiers en C++.',
            'difficulty': 'advanced',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 10,
            'instructions': 'Créez un programme qui lit des nombres d\'un fichier et calcule leur moyenne.',
            'starter_code': '#include <iostream>\n#include <fstream>\n\nint main() {\n    std::ifstream fichier("nombres.txt");\n    // Calculez la moyenne ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n#include <fstream>\n\nint main() {\n    std::ifstream fichier("nombres.txt");\n    int nombre, somme = 0, compte = 0;\n    while(fichier >> nombre) {\n        somme += nombre;\n        compte++;\n    }\n    if(compte > 0) {\n        double moyenne = static_cast<double>(somme) / compte;\n        std::cout << "Moyenne: " << moyenne << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [{'input': '', 'output': 'Moyenne: 7.5'}],
            'points': 50,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['file i/o', 'error handling', 'type casting'],
                'common_mistakes': ['file not found', 'division by zero']
            }
        }
    ]

    # C# Activities (10 activities)
    csharp_activities = [
        {
            'title': 'Hello C#',
            'description': 'Introduction à la programmation C# avec une application console simple.',
            'difficulty': 'beginner',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 1,
            'instructions': 'Créez votre première application console C# qui affiche un message de bienvenue.',
            'starter_code': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}',
            'solution_code': 'using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Bienvenue en C#!");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Bienvenue en C#!'}],
            'points': 10,
            'complexity_analysis': {
                'cognitive_load': 'low',
                'concepts': ['basic syntax', 'console output', 'main method'],
                'common_mistakes': ['forgetting semicolon', 'case sensitivity']
            },
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Structure de base C#',
                    'content': 'Comprendre la structure de base d\'un programme C#',
                    'code_snippet': 'using System;\n\nclass Program {\n    static void Main() {\n    }\n}',
                    'hint': 'La méthode Main est le point d\'entrée'
                },
                {
                    'step_number': 2,
                    'title': 'Affichage Console',
                    'content': 'Utiliser Console.WriteLine pour afficher du texte',
                    'code_snippet': 'Console.WriteLine("Votre message");',
                    'hint': 'N\'oubliez pas les guillemets et le point-virgule'
                }
            ]
        },
        {
            'title': 'Gestionnaire de Tâches',
            'description': 'Créer un gestionnaire de tâches simple en C#',
            'difficulty': 'intermediate',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 2,
            'instructions': 'Implémentez un gestionnaire de tâches qui permet d\'ajouter, supprimer et lister des tâches.',
            'starter_code': 'using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        List<string> tasks = new List<string>();\n        // Votre code ici\n    }\n}',
            'solution_code': 'using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        List<string> tasks = new List<string>();\n        string input;\n        \n        do {\n            Console.WriteLine("1. Ajouter tâche");\n            Console.WriteLine("2. Supprimer tâche");\n            Console.WriteLine("3. Lister tâches");\n            Console.WriteLine("4. Quitter");\n            \n            input = Console.ReadLine();\n            \n            switch(input) {\n                case "1":\n                    Console.Write("Nouvelle tâche: ");\n                    tasks.Add(Console.ReadLine());\n                    break;\n                case "2":\n                    if(tasks.Count > 0) {\n                        Console.WriteLine("Index à supprimer:");\n                        int index = int.Parse(Console.ReadLine());\n                        if(index >= 0 && index < tasks.Count)\n                            tasks.RemoveAt(index);\n                    }\n                    break;\n                case "3":\n                    for(int i = 0; i < tasks.Count; i++)\n                        Console.WriteLine($"{i}: {tasks[i]}");\n                    break;\n            }\n        } while(input != "4");\n    }\n}',
            'test_cases': [
                {'input': '1\nAcheter du lait\n3\n4', 'output': '0: Acheter du lait'},
                {'input': '1\nFaire les devoirs\n2\n0\n3\n4', 'output': ''}
            ],
            'points': 20,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['lists', 'user input', 'loops', 'switch statements'],
                'common_mistakes': ['index out of range', 'not handling empty list']
            }
        },
        {
            'title': 'Classes et Objets',
            'description': 'Introduction aux classes et objets en C#.',
            'difficulty': 'intermediate',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 3,
            'instructions': 'Créez une classe Etudiant avec des propriétés et des méthodes.',
            'starter_code': 'using System;\n\nclass Etudiant {\n    // Ajoutez les propriétés et méthodes ici\n}\n\nclass Program {\n    static void Main() {\n        // Testez votre classe ici\n    }\n}',
            'solution_code': 'using System;\n\nclass Etudiant {\n    public string Nom { get; set; }\n    public int Age { get; set; }\n    public double Moyenne { get; private set; }\n    \n    public void AjouterNote(double note) {\n        Moyenne = (Moyenne + note) / 2;\n    }\n    \n    public void AfficherInfo() {\n        Console.WriteLine($"Nom: {Nom}, Age: {Age}, Moyenne: {Moyenne}");\n    }\n}\n\nclass Program {\n    static void Main() {\n        var etudiant = new Etudiant { Nom = "Jean", Age = 16 };\n        etudiant.AjouterNote(85);\n        etudiant.AfficherInfo();\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Nom: Jean, Age: 16, Moyenne: 85'}],
            'points': 35,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['classes', 'properties', 'methods'],
                'common_mistakes': ['access modifiers', 'property syntax']
            }
        },
        {
            'title': 'Héritage',
            'description': 'Comprendre l\'héritage en C#.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 4,
            'instructions': 'Créez une hiérarchie de classes pour différents types de véhicules.',
            'starter_code': 'using System;\n\nclass Vehicule {\n    // Classe de base\n}\n\nclass Voiture : Vehicule {\n    // Classe dérivée\n}\n\nclass Program {\n    static void Main() {\n        // Testez vos classes\n    }\n}',
            'solution_code': 'using System;\n\nclass Vehicule {\n    public string Marque { get; set; }\n    public virtual void Demarrer() {\n        Console.WriteLine("Le véhicule démarre.");\n    }\n}\n\nclass Voiture : Vehicule {\n    public int NombrePortes { get; set; }\n    public override void Demarrer() {\n        Console.WriteLine($"La voiture {Marque} démarre avec ses {NombrePortes} portes.");\n    }\n}\n\nclass Program {\n    static void Main() {\n        var voiture = new Voiture { Marque = "Toyota", NombrePortes = 4 };\n        voiture.Demarrer();\n    }\n}',
            'test_cases': [{'input': '', 'output': 'La voiture Toyota démarre avec ses 4 portes.'}],
            'points': 40,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['inheritance', 'virtual methods', 'overriding'],
                'common_mistakes': ['missing override keyword', 'base class access']
            }
        },
        {
            'title': 'Collections',
            'description': 'Utilisation des collections en C#.',
            'difficulty': 'intermediate',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 5,
            'instructions': 'Créez un gestionnaire de bibliothèque utilisant des List<T>.',
            'starter_code': 'using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        List<string> livres = new List<string>();\n        // Implémentez la gestion de la bibliothèque\n    }\n}',
            'solution_code': 'using System;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        List<string> livres = new List<string>();\n        \n        livres.Add("Le Petit Prince");\n        livres.Add("1984");\n        livres.Add("Harry Potter");\n        \n        Console.WriteLine("Livres disponibles:");\n        foreach(var livre in livres) {\n            Console.WriteLine($"- {livre}");\n        }\n        \n        Console.WriteLine($"Nombre total: {livres.Count}");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Livres disponibles:\n- Le Petit Prince\n- 1984\n- Harry Potter\nNombre total: 3'}],
            'points': 35,
            'complexity_analysis': {
                'cognitive_load': 'medium',
                'concepts': ['generic collections', 'foreach loops', 'list methods'],
                'common_mistakes': ['type constraints', 'collection modification']
            }
        },
        {
            'title': 'Interfaces',
            'description': 'Implémentation d\'interfaces en C#.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 6,
            'instructions': 'Créez une interface IFormeGeometrique et implémentez-la pour différentes formes.',
            'starter_code': 'using System;\n\ninterface IFormeGeometrique {\n    double CalculerAire();\n    double CalculerPerimetre();\n}\n\nclass Program {\n    static void Main() {\n        // Testez vos implémentations\n    }\n}',
            'solution_code': 'using System;\n\ninterface IFormeGeometrique {\n    double CalculerAire();\n    double CalculerPerimetre();\n}\n\nclass Cercle : IFormeGeometrique {\n    public double Rayon { get; set; }\n    \n    public double CalculerAire() {\n        return Math.PI * Rayon * Rayon;\n    }\n    \n    public double CalculerPerimetre() {\n        return 2 * Math.PI * Rayon;\n    }\n}\n\nclass Program {\n    static void Main() {\n        var cercle = new Cercle { Rayon = 5 };\n        Console.WriteLine($"Aire: {cercle.CalculerAire():F2}");\n        Console.WriteLine($"Périmètre: {cercle.CalculerPerimetre():F2}");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Aire: 78.54\nPérimètre: 31.42'}],
            'points': 45,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['interfaces', 'implementation', 'math operations'],
                'common_mistakes': ['missing implementation', 'math precision']
            }
        },
        {
            'title': 'Exceptions',
            'description': 'Gestion des exceptions en C#.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 7,
            'instructions': 'Créez un programme qui gère les exceptions lors de la division.',
            'starter_code': 'using System;\n\nclass Program {\n    static double Diviser(double a, double b) {\n        // Implémentez la division sécurisée\n        return 0;\n    }\n    \n    static void Main() {\n        // Testez la division\n    }\n}',
            'solution_code': 'using System;\n\nclass DivisionParZeroException : Exception {\n    public DivisionParZeroException(string message) : base(message) { }\n}\n\nclass Program {\n    static double Diviser(double a, double b) {\n        if(b == 0) {\n            throw new DivisionParZeroException("Division par zéro impossible");\n        }\n        return a / b;\n    }\n    \n    static void Main() {\n        try {\n            Console.WriteLine(Diviser(10, 2));\n            Console.WriteLine(Diviser(10, 0));\n        } catch(DivisionParZeroException e) {\n            Console.WriteLine($"Erreur: {e.Message}");\n        }\n    }\n}',
            'test_cases': [
                {'input': '', 'output': '5\nErreur: Division par zéro impossible'}
            ],
            'points': 40,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['exception handling', 'custom exceptions', 'try-catch'],
                'common_mistakes': ['missing try-catch', 'exception hierarchy']
            }
        },
        {
            'title': 'Délégués et Événements',
            'description': 'Utilisation des délégués et événements en C#.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 8,
            'instructions': 'Créez un système de notification utilisant les événements.',
            'starter_code': 'using System;\n\nclass Program {\n    // Définissez le délégué et l\'événement ici\n    \n    static void Main() {\n        // Implémentez le système de notification\n    }\n}',
            'solution_code': 'using System;\n\nclass Notification {\n    public delegate void NotificationHandler(string message);\n    public event NotificationHandler OnNotification;\n    \n    public void EnvoyerNotification(string message) {\n        OnNotification?.Invoke(message);\n    }\n}\n\nclass Program {\n    static void Main() {\n        var notif = new Notification();\n        notif.OnNotification += (msg) => Console.WriteLine($"Notification reçue: {msg}");\n        \n        notif.EnvoyerNotification("Bonjour!");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Notification reçue: Bonjour!'}],
            'points': 45,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['delegates', 'events', 'lambda expressions'],
                'common_mistakes': ['event subscription', 'null checking']
            }
        },
        {
            'title': 'LINQ',
            'description': 'Utilisation de LINQ pour la manipulation de données.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 9,
            'instructions': 'Utilisez LINQ pour filtrer et transformer une collection de données.',
            'starter_code': 'using System;\nusing System.Linq;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        var nombres = new List<int> { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };\n        // Utilisez LINQ ici\n    }\n}',
            'solution_code': 'using System;\nusing System.Linq;\nusing System.Collections.Generic;\n\nclass Program {\n    static void Main() {\n        var nombres = new List<int> { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };\n        \n        var pairs = nombres.Where(n => n % 2 == 0);\n        var carres = pairs.Select(n => n * n);\n        \n        Console.WriteLine("Carrés des nombres pairs:");\n        foreach(var n in carres) {\n            Console.WriteLine(n);\n        }\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Carrés des nombres pairs:\n4\n16\n36\n64\n100'}],
            'points': 50,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['LINQ', 'lambda expressions', 'collection operations'],
                'common_mistakes': ['query syntax', 'deferred execution']
            }
        },
        {
            'title': 'Async/Await',
            'description': 'Programmation asynchrone en C#.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 10,
            'instructions': 'Créez un programme qui simule le chargement asynchrone de données.',
            'starter_code': 'using System;\nusing System.Threading.Tasks;\n\nclass Program {\n    static async Task Main() {\n        // Implémentez le chargement asynchrone\n    }\n}',
            'solution_code': 'using System;\nusing System.Threading.Tasks;\n\nclass Program {\n    static async Task<string> ChargerDonnees() {\n        await Task.Delay(2000); // Simule un délai\n        return "Données chargées!";\n    }\n    \n    static async Task Main() {\n        Console.WriteLine("Début du chargement...");\n        var resultat = await ChargerDonnees();\n        Console.WriteLine(resultat);\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Début du chargement...\nDonnées chargées!'}],
            'points': 50,
            'complexity_analysis': {
                'cognitive_load': 'high',
                'concepts': ['async/await', 'tasks', 'concurrent programming'],
                'common_mistakes': ['blocking calls', 'error handling']
            }
        }
    ]

    # Create all activities and their tutorial steps
    for activity_data in cpp_activities + csharp_activities:
        # Extract tutorial steps data before creating activity
        tutorial_steps_data = activity_data.pop('tutorial_steps', [])

        # Create activity
        activity = CodingActivity(**activity_data)
        db.session.add(activity)
        db.session.flush()  # Get activity ID

        # Create tutorial steps
        for step_data in tutorial_steps_data:
            step_data['activity_id'] = activity.id
            tutorial_step = TutorialStep(**step_data)
            db.session.add(tutorial_step)

    db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        student = Student.query.filter_by(email=form.email.data).first()
        if student and check_password_hash(student.password_hash, form.password.data):
            login_user(student, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        flash('Email ou mot de passe incorrect.', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        student = Student(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password
        )
        db.session.add(student)
        db.session.commit()
        flash('Votre compte a été créé! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(current_user.username, current_user.email)
    if form.validate_on_submit():
        if form.avatar.data:
            # Save avatar
            avatar_path = os.path.join(app.root_path, 'static/avatars')
            os.makedirs(avatar_path, exist_ok=True)

            # Process and save avatar
            avatar_file = form.avatar.data
            filename = secure_filename(f"avatar_{current_user.id}_{int(datetime.utcnow().timestamp())}.jpg")

            # Open and process image
            image = Image.open(avatar_file)
            image = image.convert('RGB')  # Convert to RGB format

            # Resize to square
            size = (150, 150)
            if image.size[0] != image.size[1]:
                # Crop to square
                width, height = image.size
                new_size = min(width, height)
                left = (width - new_size) // 2
                top = (height - new_size) // 2
                right = left + new_size
                bottom = top + new_size
                image = image.crop((left, top, right, bottom))

            # Resize to final size
            image = image.resize(size, Image.Resampling.LANCZOS)

            # Save processed image
            filepath = os.path.join(avatar_path, filename)
            image.save(filepath, 'JPEG', quality=85)

            # Delete old avatar if exists
            if current_user.avatar_filename:
                old_avatar = os.path.join(avatar_path, current_user.avatar_filename)
                if os.path.exists(old_avatar):
                    os.remove(old_avatar)

            current_user.avatar_filename = filename

        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash('Votre profil a été mis à jour!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
    return render_template('profile.html', form=form)

# Initialize database and initial data
with app.app_context():
    db.create_all()
    create_initial_achievements()
    create_initial_activities()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)