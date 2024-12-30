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

@app.route('/tutorial/<int:activity_id>', defaults={'step': 1})
@app.route('/tutorial/<int:activity_id>/<int:step>')
@login_required
def tutorial(activity_id, step=1):
    activity = CodingActivity.query.get_or_404(activity_id)

    # Get all tutorial steps for this activity
    tutorial_steps = TutorialStep.query.filter_by(activity_id=activity_id).order_by(TutorialStep.step_number).all()
    if not tutorial_steps:
        flash('Ce tutoriel n\'a pas encore d\'étapes définies.', 'warning')
        return redirect(url_for('view_activity', activity_id=activity_id))

    # Validate step number
    total_steps = len(tutorial_steps)
    if step < 1 or step > total_steps:
        return redirect(url_for('tutorial', activity_id=activity_id, step=1))

    # Get current step
    current_tutorial_step = tutorial_steps[step - 1]

    # Get or create progress for this step
    progress = TutorialProgress.query.filter_by(
        student_id=current_user.id,
        step_id=current_tutorial_step.id
    ).first()

    if not progress:
        progress = TutorialProgress(
            student_id=current_user.id,
            step_id=current_tutorial_step.id
        )
        db.session.add(progress)
        db.session.commit()

    # Determine if we should show hint
    show_hint = request.args.get('hint', '').lower() == 'true'

    # Check if current step is completed
    step_completed = progress.completed

    # Determine if there are previous/next steps
    prev_step = step > 1
    next_step = step < total_steps

    return render_template('tutorial.html',
                         activity=activity,
                         current_step=step,
                         total_steps=total_steps,
                         current_tutorial_step=current_tutorial_step,
                         show_hint=show_hint,
                         step_completed=step_completed,
                         prev_step=prev_step,
                         next_step=next_step)

@app.route('/tutorial/<int:activity_id>/<int:step>/verify', methods=['POST'])
@login_required
def verify_tutorial_step(activity_id, step):
    activity = CodingActivity.query.get_or_404(activity_id)
    tutorial_step = TutorialStep.query.filter_by(
        activity_id=activity_id,
        step_number=step
    ).first_or_404()

    code = request.json.get('code', '')
    if not code:
        return jsonify({'success': False, 'message': 'No code provided'})

    # Get progress
    progress = TutorialProgress.query.filter_by(
        student_id=current_user.id,
        step_id=tutorial_step.id
    ).first()

    if not progress:
        return jsonify({'success': False, 'message': 'Progress not found'})

    # Increment attempts
    progress.attempts += 1

    # Execute code
    result = compile_and_run(code, activity.language)

    # Verify output matches expected output
    success = False
    if result.get('success'):
        output = result.get('output', '').strip()
        expected = tutorial_step.expected_output.strip()
        success = output == expected

        if success:
            progress.completed = True
            progress.completed_at = datetime.utcnow()

            # Check if all steps are completed
            all_steps = TutorialStep.query.filter_by(activity_id=activity_id).all()
            all_completed = all(
                TutorialProgress.query.filter_by(
                    student_id=current_user.id,
                    step_id=step.id,
                    completed=True
                ).first() for step in all_steps
            )

            if all_completed:
                # Mark activity as completed
                activity_progress = StudentProgress.query.filter_by(
                    student_id=current_user.id,
                    activity_id=activity_id
                ).first()

                if activity_progress:
                    activity_progress.completed = True
                    activity_progress.completed_at = datetime.utcnow()

                # Award points
                current_user.score += activity.points
                flash(f'Félicitations! Vous avez terminé le tutoriel et gagné {activity.points} points!')

    db.session.commit()

    return jsonify({
        'success': success,
        'message': 'Step completed successfully!' if success else 'Output does not match expected result'
    })

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
    """Initialize database with coding activities"""
    # First remove all related records in correct order to maintain referential integrity
    TutorialProgress.query.delete()
    TutorialStep.query.delete()
    StudentProgress.query.delete()
    CodingActivity.query.delete()

    activities = [
        # TEJ2O C++ Activities
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
            'hints': [
                'N\'oubliez pas d\'inclure iostream',
                'Utilisez std::cout pour afficher du texte',
                'Terminez avec return 0'
            ],
            'points': 10
        },
        {
            'title': 'Saisie Utilisateur',
            'description': 'Apprendre à recevoir et traiter les entrées utilisateur en C++.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 2,
            'instructions': 'Créez un programme qui demande le nom de l\'utilisateur et affiche un message de bienvenue personnalisé.',
            'starter_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string nom;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n#include <string>\n\nint main() {\n    std::string nom;\n    std::cout << "Entrez votre nom: ";\n    std::getline(std::cin, nom);\n    std::cout << "Bonjour, " << nom << "!" << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': 'Marie\n', 'output': 'Entrez votre nom: Bonjour, Marie!'},
                {'input': 'Pierre\n', 'output': 'Entrez votre nom: Bonjour, Pierre!'}
            ],
            'hints': [
                'Utilisez std::string pour stocker le texte',
                'std::getline permet de lire une ligne complète',
                'N\'oubliez pas d\'inclure la bibliothèque string'
            ],
            'points': 15
        },
        {
            'title': 'Calculatrice Simple',
            'description': 'Créer une calculatrice basique pour additionner deux nombres.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 3,
            'instructions': 'Écrivez un programme qui demande deux nombres à l\'utilisateur et affiche leur somme.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int nombre1, nombre2;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int nombre1, nombre2;\n    std::cout << "Premier nombre: ";\n    std::cin >> nombre1;\n    std::cout << "Deuxième nombre: ";\n    std::cin >> nombre2;\n    std::cout << "Somme: " << nombre1 + nombre2 << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '5\n3\n', 'output': 'Premier nombre: Deuxième nombre: Somme: 8'},
                {'input': '10\n20\n', 'output': 'Premier nombre: Deuxième nombre: Somme: 30'}
            ],
            'hints': [
                'Utilisez int pour les nombres entiers',
                'L\'opérateur + additionne les nombres',
                'Affichez chaque invite avant de lire l\'entrée'
            ],
            'points': 20
        },
        {
            'title': 'Conditions Si-Sinon',
            'description': 'Apprendre à utiliser les structures conditionnelles en C++.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 4,
            'instructions': 'Créez un programme qui détermine si un nombre est positif, négatif ou zéro.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int nombre;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int nombre;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> nombre;\n    if (nombre > 0) {\n        std::cout << "Le nombre est positif" << std::endl;\n    } else if (nombre < 0) {\n        std::cout << "Le nombre est négatif" << std::endl;\n    } else {\n        std::cout << "Le nombre est zéro" << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '5\n', 'output': 'Entrez un nombre: Le nombre est positif'},
                {'input': '-3\n', 'output': 'Entrez un nombre: Le nombre est négatif'},
                {'input': '0\n', 'output': 'Entrez un nombre: Le nombre est zéro'}
            ],
            'hints': [
                'Utilisez if, else if, et else pour les conditions',
                'Comparez le nombre avec 0',
                'N\'oubliez pas les accolades { }'
            ],
            'points': 25
        },
        {
            'title': 'Boucle Simple',
            'description': 'Introduction aux boucles for en C++.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 5,
            'instructions': 'Écrivez un programme qui affiche les nombres de 1 à N.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> n;\n    for (int i = 1; i <= n; i++) {\n        std::cout << i << " ";\n    }\n    std::cout << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '5\n', 'output': 'Entrez un nombre: 1 2 3 4 5 '},
                {'input': '3\n', 'output': 'Entrez un nombre: 1 2 3 '}
            ],
            'hints': [
                'Utilisez une boucle for',
                'La variable i commence à 1',
                'Affichez chaque nombre suivi d\'un espace'
            ],
            'points': 30
        },
        {
            'title': 'Table de Multiplication',
            'description': 'Utiliser les boucles imbriquées en C++.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 6,
            'instructions': 'Créez un programme qui affiche la table de multiplication jusqu\'à N.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> n;\n    for (int i = 1; i <= n; i++) {\n        for (int j = 1; j <= n; j++) {\n            std::cout << i * j << "\\t";\n        }\n        std::cout << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '3\n', 'output': 'Entrez un nombre: 1\t2\t3\t\n2\t4\t6\t\n3\t6\t9\t\n'}
            ],
            'hints': [
                'Utilisez deux boucles for imbriquées',
                'Utilisez \\t pour aligner les colonnes',
                'Multipliez les compteurs i et j'
            ],
            'points': 35
        },
        {
            'title': 'Calcul de Moyenne',
            'description': 'Travailler avec les tableaux en C++.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 7,
            'instructions': 'Créez un programme qui calcule la moyenne de N nombres.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Combien de nombres? ";\n    std::cin >> n;\n    \n    double somme = 0;\n    for (int i = 1; i <= n; i++) {\n        double nombre;\n        std::cout << "Nombre " << i << ": ";\n        std::cin >> nombre;\n        somme += nombre;\n    }\n    \n    std::cout << "Moyenne: " << somme/n << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '3\n10\n20\n30\n', 'output': 'Combien de nombres? Nombre 1: Nombre 2: Nombre 3: Moyenne: 20'}
            ],
            'hints': [
                'Utilisez une boucle pour lire les nombres',
                'Gardez une variable pour la somme',
                'Divisez la somme par n pour la moyenne'
            ],
            'points': 40
        },
        {
            'title': 'Plus Grand Nombre',
            'description': 'Travailler avec les conditions et les boucles.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 8,
            'instructions': 'Écrivez un programme qui trouve le plus grand nombre parmi N nombres.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Combien de nombres? ";\n    std::cin >> n;\n    \n    double max;\n    std::cout << "Nombre 1: ";\n    std::cin >> max;\n    \n    for (int i = 2; i <= n; i++) {\n        double nombre;\n        std::cout << "Nombre " << i << ": ";\n        std::cin >> nombre;\n        if (nombre > max) {\n            max = nombre;\n        }\n    }\n    \n    std::cout << "Le plus grand nombre est: " << max << std::endl;\n    return 0;\n}',
            'test_cases': [
                {'input': '4\n5\n8\n2\n10\n', 'output': 'Combien de nombres? Nombre 1: Nombre 2: Nombre 3: Nombre 4: Le plus grand nombre est: 10'}
            ],
            'hints': [
                'Initialisez max avec le premier nombre',
                'Comparez chaque nouveau nombre avec max',
                'Mettez à jour max si nécessaire'
            ],
            'points': 45
        },
        {
            'title': 'Calculatrice de Factorielle',
            'description': 'Introduction aux fonctions en C++.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 9,
            'instructions': 'Créez une fonction qui calcule la factorielle d\'un nombre.',
            'starter_code': '#include <iostream>\n\n// Créez la fonction factorielle ici\n\nint main() {\n    int nombre;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nlong factorielle(int n) {\n    if (n <= 1) return 1;\n    return n * factorielle(n - 1);\n}\n\nint main() {\n    int nombre;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> nombre;\n    if (nombre < 0) {\n        stdcout << "Erreur: nombre négatif" << std::endl;\n    } else {\n        std::cout << nombre << "! = " << factorielle(nombre) << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '5\n', 'output': 'Entrez un nombre: 5! = 120'},
                {'input': '0\n', 'output': 'Entrez un nombre: 0! = 1'}
            ],
            'hints': [
                'Utilisez la récursion ou une boucle',
                'N\'oubliez pas le cas de base (0! = 1)',
                'Attention aux nombres négatifs'
            ],
            'points': 50
        },
        {
            'title': 'Générateur de Motifs',
            'description': 'Utiliser les boucles imbriquées pour créer des motifs.',
            'difficulty': 'intermediate',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 10,
            'instructions': 'Créez un programme qui affiche un triangle d\'étoiles.',
            'starter_code': '#include <iostream>\n\nint main() {\n    int hauteur;\n    // Votre code ici\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int hauteur;\n    std::cout << "Hauteur du triangle: ";\n    std::cin >> hauteur;\n    \n    for (int i = 1; i <= hauteur; i++) {\n        // Espaces\n        for (int j = 1; j <= hauteur - i; j++) {\n            std::cout << " ";\n        }\n        // Étoiles\n        for (int j = 1; j <= 2*i - 1; j++) {\n            std::cout << "*";\n        }\n        std::cout << std::endl;\n    }\n    return 0;\n}',
            'test_cases': [
                {'input': '3\n', 'output': 'Hauteur du triangle:   *\n **\n***\n'}
            ],
            'hints': [
                'Utilisez des boucles imbriquées',
                'Calculez les espaces et étoiles nécessaires',
                'La ligne i a 2*i - 1 étoiles'
            ],
            'points': 55
        },
        # ICS3U C# Activities
        {
            'title': 'Gestion des Étudiants',
            'description': 'Créer une application de gestion des étudiants avec des structures de données.',
            'difficulty': 'intermediate',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 1,
            'instructions': 'Créez une application qui gère une liste d\'étudiants avec leurs notes.',
            'starter_code': '''using System;
using System.Collections.Generic;

class Programme {
    static void Main() {
        List<string> noms = new List<string>();
        List<double> notes = new List<double>();
        // Votre code ici
    }
}''',
            'solution_code': '''using System;
using System.Collections.Generic;

class Programme {
    static void Main() {
        List<string> noms = new List<string>();
        List<double> notes = new List<double>();

        Console.Write("Nombre d'étudiants: ");
        int n = Convert.ToInt32(Console.ReadLine());

        for (int i = 0; i < n; i++) {
            Console.Write($"Nom de l'étudiant {i+1}: ");
            noms.Add(Console.ReadLine());
            Console.Write($"Note: ");
            notes.Add(Convert.ToDouble(Console.ReadLine()));
        }

        double moyenne = 0;
        for (int i = 0; i < n; i++) {
            moyenne += notes[i];
        }
        moyenne /= n;

        Console.WriteLine($"Moyenne de la classe: {moyenne:F2}");

        for (int i = 0; i < n; i++) {
            if (notes[i] > moyenne) {
                Console.WriteLine($"{noms[i]} est au-dessus de la moyenne");
            }
        }
    }
}''',
            'test_cases': [
                {'input': '3\nAlice\n85\nBob\n92\nCarol\n78\n',
                 'output': 'Nombre d\'étudiants: Nom de l\'étudiant 1: Note: Nom de l\'étudiant 2: Note: Nom de l\'étudiant 3: Note: Moyenne de la classe: 85.00\nAlice est au-dessus de la moyenne\nBob est au-dessus de la moyenne'}
            ],
            'hints': [
                'Utilisez List<T> pour stocker les données',
                'Convert.ToDouble pour les notes',
                'Utilisez une boucle pour calculer la moyenne'
            ],
            'points': 60
        },
        {
            'title': 'Liste Chaînée Simple',
            'description': 'Implémenter une structure de données de liste chaînée.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 2,
            'instructions': 'Créez une implémentation simple d\'une liste chaînée.',
            'starter_code': '''using System;

class Node {
    public int Data;
    public Node Next;

    public Node(int data) {
        Data = data;
        Next = null;
    }
}

class LinkedList {
    private Node head;

    // Implémentez les méthodes ici
}

class Programme {
    static void Main() {
        LinkedList liste = new LinkedList();
        // Votre code ici
    }
}''',
            'solution_code': '''using System;

class Node {
    public int Data;
    public Node Next;

    public Node(int data) {
        Data = data;
        Next = null;
    }
}

class LinkedList {
    private Node head;

    public void Add(int data) {
        Node newNode = new Node(data);
        if (head == null) {
            head = newNode;
            return;
        }

        Node current = head;
        while (current.Next != null) {
            current = current.Next;
        }
        current.Next = newNode;
    }

    public void Print() {
        Node current = head;
        while (current != null) {
            Console.Write(current.Data + " ");
            current = current.Next;
        }
        Console.WriteLine();
    }
}

class Programme {
    static void Main() {
        LinkedList liste = new LinkedList();
        Console.Write("Nombre d'éléments: ");
        int n = Convert.ToInt32(Console.ReadLine());

        for (int i = 0; i < n; i++) {
            Console.Write($"Élément {i+1}: ");
            int valeur = Convert.ToInt32(Console.ReadLine());
            liste.Add(valeur);
        }

        Console.Write("Liste: ");
        liste.Print();
    }
}''',
            'test_cases': [
                {'input': '4\n10\n20\n30\n40\n',
                 'output': 'Nombre d\'éléments: Élément 1: Élément 2: Élément 3: Élément 4: Liste: 10 20 30 40 '}
            ],
            'hints': [
                'Utilisez une classe Node pour chaque élément',
                'Gardez une référence vers le premier nœud (head)',
                'Parcourez la liste pour ajouter à la fin'
            ],
            'points': 70
        },
        {
            'title': 'Gestionnaire de Tâches',
            'description': 'Créer un gestionnaire de tâches simple avec priorités.',
            'difficulty': 'advanced',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 3,
            'instructions': 'Implémentez un gestionnaire de tâches avec priorités.',
            'starter_code': '''using System;
using System.Collections.Generic;

class Tache {
    public string Description { get; set; }
    public int Priorite { get; set; }

    public Tache(string description, int priorite) {
        Description = description;
        Priorite = priorite;
    }
}

class Programme {
    static void Main() {
        List<Tache> taches = new List<Tache>();
        // Votre code ici
    }
}''',
            'solution_code': '''using System;
using System.Collections.Generic;
using System.Linq;

class Tache {
    public string Description { get; set; }
    public int Priorite { get; set; }

    public Tache(string description, int priorite) {
        Description = description;
        Priorite = priorite;
    }
}

class Programme {
    static void Main() {
        List<Tache> taches = new List<Tache>();

        Console.Write("Nombre de tâches: ");
        int n = Convert.ToInt32(Console.ReadLine());

        for (int i = 0; i < n; i++) {
            Console.Write($"Description de la tâche {i+1}: ");
            string description = Console.ReadLine();
            Console.Write("Priorité (1-5): ");
            int priorite = Convert.ToInt32(Console.ReadLine());
            taches.Add(new Tache(description, priorite));
        }

        var tachesTriees = taches.OrderByDescending(t => t.Priorite).ToList();

        Console.WriteLine("\nTâches par priorité:");
        foreach (var tache in tachesTriees) {
            Console.WriteLine($"[Priorité {tache.Priorite}] {tache.Description}");
        }
    }
}''',
            'test_cases': [
                {'input': '3\nÉtudier\n5\nJouer\n1\nDormir\n3\n',
                 'output': 'Nombre de tâches: Description de la tâche 1: Priorité (1-5): Description de la tâche 2: Priorité (1-5): Description de la tâche 3: Priorité (1-5): \nTâches par priorité:\n[Priorité 5] Étudier\n[Priorité 3] Dormir\n[Priorité 1] Jouer'}
            ],
            'hints': [
                'Utilisez une classe pour représenter les tâches',
                'OrderByDescending pour trier par priorité',
                'Utilisez les propriétés auto-implémentées'
            ],
            'points': 80
        }
    ]

    # Create activities one by one, with their tutorial steps
    for activity_data in activities:
        # Create activity first
        activity = CodingActivity(**{
            k: v for k, v in activity_data.items() 
            if k not in ['test_cases', 'hints']  # Exclude JSON fields
        })
        activity.test_cases = activity_data['test_cases']
        activity.hints = activity_data.get('hints', [])

        db.session.add(activity)
        db.session.commit()  # Commit to get activity.id

        # Add tutorial steps for this activity
        steps = [
            {
                'step_number': 1,
                'title': "Comprendre l'exercice",
                'content': f"Lisez attentivement l'énoncé: {activity.instructions}",
                'code_snippet': activity.starter_code,
                'expected_output': "",
                'hint': "Prenez le temps de bien comprendre ce qui est demandé."
            },
            {
                'step_number': 2,
                'title': "Analyser les exemples",
                'content': "Examinez les exemples de test pour comprendre le format attendu.",
                'code_snippet': "",
                'expected_output': activity.test_cases[0]['output'] if activity.test_cases else "",
                'hint': "Les tests vous montrent exactement ce qui est attendu."
            },
            {
                'step_number': 3,
                'title': "Implémenter la solution",
                'content': "Complétez le code pour résoudre l'exercice.",
                'code_snippet': activity.starter_code,
                'expected_output': activity.test_cases[0]['output'] if activity.test_cases else "",
                'hint': activity.hints[0] if activity.hints else "Procédez étape par étape."
            }
        ]

        for step_data in steps:
            step = TutorialStep(activity=activity, **step_data)
            db.session.add(step)

        db.session.commit()

    logging.info(f"Created {CodingActivity.query.count()} activities")
    logging.info(f"Created {TutorialStep.query.count()} tutorial steps")

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