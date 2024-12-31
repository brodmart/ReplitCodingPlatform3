import os
import logging
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import LoginManager, current_user, login_user, login_required, logout_user
from compiler_service import compile_and_run
from database import db
from models import (
    Student, Achievement, StudentAchievement, CodeSubmission, 
    SharedCode, CodingActivity, StudentProgress
)
from sqlalchemy import desc
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
from forms import LoginForm, RegisterForm #Added


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

    # Ensure incorrect_examples is properly loaded from JSON
    if activity.incorrect_examples:
        try:
            if isinstance(activity.incorrect_examples, str):
                activity.incorrect_examples = json.loads(activity.incorrect_examples)
            app.logger.debug(f"Loaded incorrect examples for activity {activity_id}: {activity.incorrect_examples}")
        except json.JSONDecodeError:
            app.logger.error(f"Failed to parse incorrect_examples for activity {activity_id}")
            activity.incorrect_examples = []
    else:
        app.logger.debug(f"No incorrect examples found for activity {activity_id}")

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

def create_initial_activities():
    """Initialize database with coding activities"""
    try:
        # First remove dependent records
        StudentProgress.query.delete()
        # Then remove activities
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
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Inclusion de bibliothèque:
   #include <iostream>    // Pour l'entrée/sortie

2. Fonction principale:
   int main() {
       // Votre code ici
       return 0;
   }

3. Afficher du texte:
   std::cout << "votre texte" << std::endl;

4. Points importants:
   - N'oubliez pas le point-virgule (;) après chaque instruction
   - Les guillemets ("") sont nécessaires pour le texte
   - std::endl ajoute une nouvelle ligne
</pre>''',
                'instructions': '''Modifiez le programme exemple pour afficher "Bonjour le monde!" au lieu de "Salut tout le monde!".

Points à noter:
1. Le message doit être exactement "Bonjour le monde!"
2. N'oubliez pas le point d'exclamation
3. Conservez le reste du code tel quel''',
                'starter_code': '#include <iostream>\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
                'solution_code': '#include <iostream>\n\nint main() {\n    std::cout << "Bonjour le monde!" << std::endl;\n    return 0;\n}',
                'test_cases': [{'input': '', 'output': 'Bonjour le monde!'}],
                'hints': [
                    'N\'oubliez pas d\'inclure iostream',
                    'Utilisez std::cout pour afficher du texte',
                    'Terminez avec return 0'
                ],
                'common_errors': [
                    'Oublier le point-virgule à la fin de l\'instruction cout',
                    'Écrire "iostream.h" au lieu de <iostream>',
                    'Oublier d\'utiliser std:: devant cout',
                    'Oublier les guillemets autour du texte à afficher'
                ],
                'points': 10,
                'incorrect_examples': '''[
                    {
                        "code": "#include <iostream>\nint main() {\n    std::cout << \"Salutations!\" << std::endl;\n    return 0;\n}",
                        "error": "Message incorrect"
                    },
                    {
                        "code": "#include <iostream>\nint main() {\n    std::cout << \"Bonjour le monde\" << std::endl;\n    return 0;\n}",
                        "error": "Point d'exclamation manquant"
                    }
                ]'''
            },
            {
                'title': 'Saisie Utilisateur',
                'description': 'Apprendre à recevoir et traiter les entrées utilisateur en C++.',
                'difficulty': 'beginner',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 2,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Inclusions:
   #include <iostream>    // Pour l'entrée/sortie
   #include <string>     // Pour les chaînes de caractères

2. Déclarer une variable texte:
   std::string nom;

3. Lire une ligne de texte:
   std::getline(std::cin, nom);

4. Afficher avec une variable:
   std::cout << "Bonjour, " << nom << "!" << std::endl;

5. Points importants:
   - N'oubliez pas d'inclure <string> pour std::string
   - std::getline lit toute une ligne, y compris les espaces
   - L'opérateur << peut être utilisé plusieurs fois
</pre>''',
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
                'common_errors': [
                    'Utiliser cin >> nom au lieu de getline (ne gère pas les espaces)',
                    'Oublier d\'inclure la bibliothèque <string>',
                    'Ne pas vider le buffer après un cin >>',
                    'Oublier de déclarer la variable nom comme std::string'
                ],
                'points': 15,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { std::string nom; std::cin >> nom; std::cout << \"Bonjour, \" << nom << \"!\" << std::endl; }", "error": "Utilisation incorrecte de cin"}, {"code": "#include <iostream>\nint main() { std::string nom; std::getline(std::cin, nom); std::cout << nom << std::endl; }", "error": "Message incorrect"}]'
            },
            {
                'title': 'Calculatrice Simple',
                'description': 'Créer une calculatrice basique pour additionner deux nombres.',
                'difficulty': 'beginner',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 3,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer des variables numériques:
   int nombre1, nombre2;

2. Lire un nombre:
   std::cin >> nombre1;

3. Opérations mathématiques:
   + : addition       (a + b)
   - : soustraction   (a - b)
   * : multiplication (a * b)
   / : division       (a / b)

4. Afficher le résultat:
   std::cout << "Résultat: " << (nombre1 + nombre2);
</pre>''',
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
                'common_errors': [
                    'Ne pas vérifier si l\'entrée est bien un nombre',
                    'Oublier de gérer le dépassement d\'entier',
                    'Ne pas afficher de message pour guider l\'utilisateur',
                    'Additionner les nombres comme des chaînes de caractères'
                ],
                'points': 20,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { int a, b; std::cout << a + b << std::endl; }", "error": "Variables non initialisées"}, {"code": "#include <iostream>\nint main() { int a = 5, b = \"3\"; std::cout << a + b << std::endl; }", "error": "Type incorrect"}]'
            },
            {
                'title': 'Conditions Si-Sinon',
                'description': 'Apprendre à utiliser les structures conditionnelles en C++.',
                'difficulty': 'beginner',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 4,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Structures conditionnelles:
   if (condition) {
       // instructions si la condition est vraie
   } else if (autre condition) {
       // instructions si la deuxième condition est vraie
   } else {
       // instructions si aucune condition n'est vraie
   }

2. Opérateurs de comparaison:
   == : égal à
   != : différent de
   >  : supérieur à
   <  : inférieur à
   >= : supérieur ou égal à
   <= : inférieur ou égal à

3. Points importants:
   - Les accolades {} sont nécessaires pour les blocs d'instructions
   - Utilisez des opérateurs de comparaison appropriés
</pre>''',
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
                'common_errors': [
                    'Oublier les accolades après if, else if, else',
                    'Mauvaise utilisation des opérateurs de comparaison',
                    'Ne pas gérer tous les cas possibles (positif, négatif, zéro)',
                    'Oublier de demander l\'entrée à l\'utilisateur'
                ],
                'points': 25,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { int n; if (n > 0) std::cout << \"positif\"; }", "error": "Accolades manquantes"}, {"code": "#include <iostream>\nint main() { int n; if (n = 0) std::cout << \"zéro\"; }", "error": "Mauvaise utilisation de l\'opérateur =="}]'
            },
            {
                'title': 'Boucle Simple',
                'description': 'Introduction aux boucles for en C++.',
                'difficulty': 'beginner',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 5,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucle for:
   for (initialisation; condition; incrémentation) {
       // instructions à répéter
   }

2. Points importants:
   - L'initialisation se fait une seule fois au début de la boucle
   - La condition est vérifiée avant chaque itération
   - L'incrémentation se fait après chaque itération
   - Les accolades {} sont nécessaires pour le bloc d'instructions
</pre>''',
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
                'common_errors': [
                    'Mauvaise initialisation de la boucle for',
                    'Mauvaise condition de terminaison de la boucle',
                    'Incrémentation incorrecte du compteur',
                    'Ne pas afficher de sortie'
                ],
                'points': 30,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { for (int i = 1; i < 5; i++) std::cout << i; }", "error": "Condition incorrecte"}, {"code": "#include <iostream>\nint main() { for (int i = 1; i <= 5; i--) std::cout << i; }", "error": "Incrémentation incorrecte"}]'
            },
            {
                'title': 'Table de Multiplication',
                'description': 'Utiliser les boucles imbriquées en C++.',
                'difficulty': 'intermediate',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 6,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucles imbriquées:
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= n; j++) {
            // instructions à répéter
        }
    }

2. Points importants:
    - La boucle interne s'exécute entièrement pour chaque itération de la boucle externe
    - Utilisez des variables de boucle appropriées pour l'indexation
    - Assurez-vous que les boucles imbriquées sont correctement imbriquées
</pre>''',
                'instructions': 'Créez un programme qui affiche la table de multiplication jusqu\'à N.',
                'starter_code': '#include <iostream>\n\nint main() {\n    int n;\n    // Votre code ici\n    return 0;\n}',
                'solution_code': '''#include <iostream>\n\nint main() {\n    int n;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> n;\n    for (int i = 1; i <= n; i++) {\n        for (int j = 1; j <= n; j++) {\n            std::cout << i * j << "\\t";\n        }\n        std::cout << std::endl;\n    }\n    return 0;\n}''',
                'test_cases': [
                    {'input': '3\n', 'output': 'Entrez un nombre: 1\t2\t3\t\n2\t4\t6\t\n3\t6\t9\t\n'}
                ],
                'hints': [
                    'Utilisez deux boucles for imbriquées',
                    'Utilisez \\t pour aligner les colonnes',
                    'Multipliez les compteurs i et j'
                ],
                'common_errors': [
                    'Mauvaise imbrication des boucles',
                    'Mauvaise utilisation de \\t pour l\'alignement',
                    'Calcul incorrect du produit',
                    'Ne pas gérer correctement les sauts de ligne'
                ],
                'points': 35,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { for (int i = 1; i <= 3; i++) { for (int j = 1; j <=3; j++) std::cout << i + j << \"\\t\"; } } }", "error": "Multiplication incorrecte"}, {"code": "#include <iostream>\nint main() { for (int i = 1; i <= 3; i++) { for (int j = 1; j <= 3; j++) { std::cout << i * j; } } }", "error": "Sauts de ligne manquants"}]'
            },
            {
                'title': 'Calcul de Moyenne',
                'description': 'Travailler avec les tableaux en C++.',
                'difficulty': 'intermediate',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 7,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer un tableau:
   double[] nombres = new double[n];

2. Calculer la somme:
   double somme = 0;
   for (int i = 0; i < n; i++) {
       somme += nombres[i];
   }

3. Calculer la moyenne:
   double moyenne = somme / n;

4. Points importants:
   - Assurez-vous que n est supérieur à 0 pour éviter la division par zéro.
   - Les tableaux sont indexés à partir de 0.
</pre>''',
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
                'common_errors': [
                    'Division par zéro si n est égal à 0',
                    'Mauvaise gestion des types de données (int au lieu de double)',
                    'Oublier d\'initialiser la somme à 0',
                    'Ne pas demander le nombre de nombres à l\'utilisateur'
                ],
                'points': 40,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { int n; double somme = 0; for (int i = 0; i < n; i++) somme += i; std::cout << somme / n; }", "error": "Variables non initialisées"}, {"code": "#include <iostream>\nint main() { int n; int somme = 0; for (int i = 0; i < n; i++) somme += i; std::cout << somme / n; }", "error": "Mauvaise gestion des types de données"}]'
            },
            {
                'title': 'Plus Grand Nombre',
                'description': 'Travailler avec les conditions et les boucles.',
                'difficulty': 'intermediate',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 8,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer une variable:
   double max;

2. Comparer des nombres:
   if (nombre > max) {
       max = nombre;
   }

3. Boucle for:
   for (int i = 2; i <= n; i++) {
       // instructions à répéter
   }

4. Points importants:
   - Initialiser max avec le premier nombre.
   - Comparer chaque nouveau nombre à max dans la boucle.
   - Mettre à jour max si un nombre plus grand est trouvé.
</pre>''',
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
                'common_errors': [
                    'Ne pas initialiser correctement max',
                    'Mauvaise comparaison des nombres',
                    'Ne pas gérer correctement les cas de nombres égaux',
                    'Ne pas afficher la sortie'
                ],
                'points': 45,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { int n; double max = 0; for (int i = 0; i < n; i++) { double nombre; if (nombre < max) max = nombre; } }", "error": "Mauvaise comparaison"}, {"code": "#include <iostream>\nint main() { int n; double max; for (int i = 0; i < n; i++) { double nombre; if (nombre > max) max = nombre; } }", "error": "max non initialisé"}]'
            },
            {
                'title': 'Calculatrice de Factorielle',
                'description': 'Introduction aux fonctions en C++.',
                'difficulty': 'intermediate',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 9,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer une fonction:
   long factorielle(int n) {
       // instructions
   }

2. Récursion:
   Une fonction qui s'appelle elle-même.

3. Cas de base:
   Le cas qui arrête la récursion.

4. Points importants:
   - Le cas de base est essentiel pour éviter les boucles infinies.
   - La récursion peut être plus lisible mais moins efficace que les boucles itératives.
</pre>''',
                'instructions': 'Créez une fonction qui calcule la factorielle d\'un nombre.',
                'starter_code': '#include <iostream>\n\n// Créez la fonction factorielle ici\n\nint main() {\n    int nombre;\n    // Votre code ici\n    return 0;\n}',
                'solution_code': '#include <iostream>\n\nlong factorielle(int n) {\n    if (n <= 1) return 1;\n    return n * factorielle(n - 1);\n}\n\nint main() {\n    int nombre;\n    std::cout << "Entrez un nombre: ";\n    std::cin >> nombre;\n    if (nombre < 0) {\n                std::cout << "Erreur: nombre négatif" << std::endl;\n    } else {\n        std::cout << nombre << "! =" << factorielle(nombre) << std::endl;\    }\n    return 0;\n}',
                'test_cases': [
                    {'input': '5\n', 'output': 'Entrez un nombre: 5! = 120'},
                    {'input': '0\n', 'output': 'Entrez un nombre: 0! = 1'}
                ],
                'hints': [
                    'Utilisez la récursion ou une boucle',
                    'N\'oubliez pas le cas de base (0! = 1)',
                    'Attention aux nombres négatifs'
                ],
                'common_errors': [
                    'Cas de base incorrect pour la récursion',
                    'Dépassement de pile pour les grands nombres',
                    'Ne pas gérer les nombres négatifs',
                    'Mauvaise utilisation de la récursionor boucle iterative'
                ],
                'points': 50,
                'incorrect_examples': '[{"code": "#include <iostream>\nlong factorielle(int n) { return n * factorielle(n); }", "error": "Cas de base manquant"}, {"code": "#include <iostream>\nlong factorielle(int n) { if (n == 0) return 0; return n * factorielle(n - 1); }", "error": "Cas de base incorrect"}]'
            },
            {
                'title':'Générateur de Motifs',
                'description': 'Utiliser les boucles imbriquées pour créer des motifs.',
                'difficulty': 'intermediate',
                'curriculum': 'TEJ2O',
                'language': 'cpp',
                'sequence': 10,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucles imbriquées:
   for (int i = 1; i <= hauteur; i++) {
       for (int j = 1; j <= largeur; j++) {
           // instructions à répéter
       }
   }

2. Saut de ligne:
   std::endl;

3. Points importants:
   - Contrôlez le nombre d'espaces et d'étoiles selon les lignes.
   - Utilisez des boucles imbriquées pour créer des motifs répétitifs.
</pre>''',
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
                'common_errors': [
                    'Mauvaise gestion des espaces',
                    'Mauvais calcul du nombre d\'étoiles',
                    'Ne pas gérer correctement les sauts de ligne',
                    'Imbrication incorrecte des boucles'
                ],
                'points': 55,
                'incorrect_examples': '[{"code": "#include <iostream>\nint main() { for (int i = 1; i <= 3; i++) { for (int j = 1; j <= i; j++) std::cout << \"*\"; } }", "error": "Triangle incorrect"}, {"code": "#include <iostream>\nint main() { for (int i = 1; i<= 3; i++) { for (int j = 1; j <= 3; j++) std::cout << \"*\"; } }", "error": "Triangle incorrect"}]'
            },
            # ICS3U C# Activities - Continue with the next part
            {
                'title': 'Conditions If-Else',
                'description': 'Apprendre à utiliser les structures conditionnelles en C#.',
                'difficulty': 'beginner',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 4,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Structures conditionnelles:
   if (condition) {
       // instructions si la condition est vraie
   } else {
       // instructions si la condition est fausse
   }

2. Opérateur modulo (%):
   Retourne le reste d\'une division.

3. Points importants:
   - Les accolades {} sont nécessaires pour les blocs d\'instructions.
   - L\'opérateur modulo (%) est utile pour vérifier la parité.
</pre>''',
                'instructions': 'Créez un programme qui détermine si un nombre est pair ou impair.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int nombre;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int nombre;\n        Console.Write("Entrez un nombre: ");\n        nombre = Convert.ToInt32(Console.ReadLine());\n        if (nombre % 2 == 0) {\n            Console.WriteLine("Le nombre est pair.");\n        } else {\n            Console.WriteLine("Le nombre est impair.");\n        }\n    }\n}',
                'test_cases': [
                    {'input': '4\n', 'output': 'Entrez un nombre: Le nombre est pair.'},
                    {'input': '7\n', 'output': 'Entrez un nombre: Le nombre est impair.'}
                ],
                'hints': [
                    'Utilisez l\'opérateur modulo (%)',
                    'Si nombre % 2 == 0, le nombre est pair',
                    'Sinon, le nombre est impair'
                ],
                'common_errors': [
                    'Mauvaise utilisation de l\'opérateur modulo',
                    'Mauvaise condition dans le if-else',
                    'Oublier de gérer les cas possibles',
                    'Ne pas demander l\'entrée à l\'utilisateur'
                ],
                'points': 25,
                'incorrect_examples': '[{"code": "using System; class Programme { static void Main() { int n; if (n % 2 == 1) Console.WriteLine(n + \" est pair\"); } }", "error": "Message incorrect"}, {"code": "using System; class Programme { static void Main() { int n; if (n % 2 = 0) Console.WriteLine(n + \" est pair\"); } }", "error": "Mauvaise utilisation de l\'opérateur =="}]'
            },
            {
                'title': 'Boucles For',
                'description': 'Introduction aux boucles for en C#.',
                'difficulty': 'beginner',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 5,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucle for:
   for (int i = 1; i <= n; i++) {
       // instructions à répéter
   }

2. Points importants:
   - L\'initialisation se fait une seule fois au début.
   - La condition est vérifiée avant chaque itération.
   - L\'incrémentation se fait après chaque itération.
   - Les accolades {} sont nécessaires pour le bloc d\'instructions.
</pre>''',
                'instructions': 'Écrivez un programme qui affiche les nombres de 1 à N.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        Console.Write("Entrez un nombre: ");\n        n = Convert.ToInt32(Console.ReadLine());\n        for (int i = 1; i <= n; i++) {\n            Console.Write(i + " ");\n        }\n        Console.WriteLine();\n    }\n}',
                'test_cases': [
                    {'input': '5\n', 'output': 'Entrez un nombre: 1 2 3 4 5 '},
                    {'input': '3\n', 'output': 'Entrez un nombre: 1 2 3 '}
                ],
                'hints': [
                    'Utilisez une boucle for',
                    'La variable i commence à 1',
                    'Affichez chaque nombre suivi d\'un espace'
                ],
                'common_errors': [
                    'Mauvaise initialisation de la boucle for',
                    'Mauvaise condition de terminaison',
                    'Incrémentation incorrecte du compteur',
                    'Ne pas afficher la sortie'
                ],
                'points': 30,
                'incorrect_examples': '[{"code": "using System; class Programme { static void Main() { for (int i = 1; i < 5; i++) Console.Write(i); } }", "error": "Condition incorrecte"}, {"code": "using System; class Programme { static void Main() { for (int i = 1; i <= 5; i--) Console.Write(i); } }", "error": "Incrémentation incorrecte"}]'
            },
            {
                'title': 'Table de Multiplication',
                'description': 'Utiliser les boucles imbriquées en C#.',
                'difficulty': 'intermediate',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 6,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucles imbriquées:
   for (int i = 1; i <= n; i++) {
       for (int j = 1; j <= n; j++) {
           // instructions à répéter
       }
   }

2. Points importants:
   - La boucle interne s\'exécute entièrement pour chaque itération de la boucle externe.
   - Utilisez des variables de boucle appropriées pour l\'indexation.
   - Assurez-vous que les boucles imbriquées sont correctement imbriquées.
</pre>''',
                'instructions': 'Créez un programme qui affiche la table de multiplication jusqu\'à N.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        Console.Write("Entrez un nombre: ");\n        n = Convert.ToInt32(Console.ReadLine());\n        for (int i = 1; i <= n; i++) {\n            for (int j = 1; j <= n; j++) {\n                Console.Write(i * j + "\\t");\n            }\n            Console.WriteLine();\n        }\n    }\n}',
                'test_cases': [
                    {'input': '3\n', 'output': 'Entrez un nombre: 1\t2\t3\n2\t4\t6\n3\t6\t9\n'}
                ],
                'hints': [
                    'Utilisez deux boucles for imbriquées',
                    'Utilisez \\t pour aligner les colonnes',
                    'Multipliez les compteurs i et j'
                ],
                'common_errors': [
                    'Mauvaise imbrication des boucles',
                    'Mauvaise utilisation de \\t',
                    'Calcul incorrect du produit',
                    'Mauvaise gestion des sauts de ligne'
                ],
                'points': 35,
                'incorrect_examples': '[{"code": "using System; class Programme { static void Main() { for (int i = 1; i <= 3; i++) { for (int j = 1; j <=3; j++) Console.Write(i + j + \"\\t\"); } } }", "error": "Multiplication incorrecte"}, {"code": "using System; class Programme { static void Main() { for (int i = 1; i <= 3; i++) { for (int j = 1; j <= 3; j++) { Console.Write(i * j); } } } }", "error": "Sauts de ligne manquants"}]'
            },
            {
                'title': 'Calcul de Moyenne',
                'description': 'Travailler avec les tableaux en C#.',
                'difficulty': 'intermediate',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 7,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer un tableau:
   double[] nombres = new double[n];

2. Calculer la somme:
   double somme = 0;
   for (int i = 0; i < n; i++) {
       somme += nombres[i];
   }

3. Calculer la moyenne:
   double moyenne = somme / n;

4. Points importants:
   - Assurez-vous que n est supérieur à 0 pour éviter la division par zéro.
   - Les tableaux sont indexés à partir de 0.
</pre>''',
                'instructions': 'Créez un programme qui calcule la moyenne de N nombres.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        Console.Write("Combien de nombres? ");\n        n = Convert.ToInt32(Console.ReadLine());\n        double[] nombres = new double[n];\n        double somme = 0;\n        for (int i = 0; i < n; i++) {\n            Console.Write($"Nombre {i + 1}: ");\n            nombres[i] = Convert.ToDouble(Console.ReadLine());\n            somme += nombres[i];\n        }\n        Console.WriteLine($"Moyenne: {somme / n}");\n    }\n}',
                'test_cases': [
                    {'input': '3\n10\n20\n30\n', 'output': 'Combien de nombres? Nombre 1: Nombre 2: Nombre 3: Moyenne: 20'}
                ],
                'hints': [
                    'Utilisez un tableau pour stocker les nombres',
                    'Calculez la somme des nombres',
                    'Divisez la somme par n pour la moyenne'
                ],
                'common_errors': [
                    'Division par zéro si n est 0',
                    'Mauvaise gestion des types de données',
                    'Oublier d\'initialiser la somme',
                    'Ne pas demander le nombre de nombres'
                ],
                'points': 40,
                'incorrect_examples': '[{"code": "using System; class Programme { static void Main() { int n; double somme = 0; for (int i = 0; i < n; i++) somme += i; Console.WriteLine(somme / n); } }", "error": "Variables non initialisées"}, {"code": "using System; class Programme { static void Main() { int n; int somme = 0; for (int i = 0; i < n; i++) somme += i; Console.WriteLine(somme / n); } }", "error": "Mauvaise gestion des types de données"}]'
            },
            {
                'title': 'Plus Grand Nombre',
                'description': 'Travailler avec les conditions et les boucles.',
                'difficulty': 'intermediate',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 8,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer une variable:
   double max;

2. Comparer des nombres:
   if (nombre > max) {
       max = nombre;
   }

3. Boucle for:
   for (int i = 2; i <= n; i++) {
       // instructions à répéter
   }

4. Points importants:
   - Initialiser max avec le premier nombre.
   - Comparer chaque nouveau nombre à max dans la boucle.
   - Mettre à jour max si un nombre plus grand est trouvé.
</pre>''',
                'instructions': 'Écrivez un programme qui trouve le plus grand nombre parmi N nombres.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int n;\n        Console.Write("Combien de nombres? ");\n        n = Convert.ToInt32(Console.ReadLine());\n        double max;\n        Console.Write("Nombre 1: ");\n        max = Convert.ToDouble(Console.ReadLine());\n        for (int i = 2; i <= n; i++) {\n            double nombre;\n            Console.Write($"Nombre {i}: ");\n            nombre = Convert.ToDouble(Console.ReadLine());\n            if (nombre > max) {\n                max = nombre;\n            }\n        }\n        Console.WriteLine($"Le plus grand nombre est: {max}");\n    }\n}',
                'test_cases': [
                    {'input': '4\n5\n8\n2\n10\n', 'output': 'Combien de nombres? Nombre 1: Nombre 2: Nombre 3: Nombre 4: Le plus grand nombre est: 10'}
                ],
                'hints': [
                    'Initialisez max avec le premier nombre',
                    'Comparez chaque nouveau nombre avec max',
                    'Mettez à jour max si nécessaire'
                ],
                'common_errors': [
                    'Ne pas initialiser correctement max',
                    'Mauvaise comparaison des nombres',
                    'Ne pas gérer les cas de nombres égaux',
                    'Ne pas afficher la sortie'
                ],
                'points': 45,
                'incorrect_examples': '[{"code": "using System; class Programme { static void Main() { int n; double max = 0; for (int i = 0; i < n; i++) { double nombre; if (nombre < max) max = nombre; } } }", "error": "Mauvaise comparaison"}, {"code": "using System; class Programme { static void Main() { int n; double max; for (int i = 0; i < n; i++) { double nombre; if (nombre > max) max = nombre; } } }", "error": "max non initialisé"}]'
            },
            {
                'title': 'Calcul de Factorielle',
                'description': 'Introduction aux fonctions en C#.',
                'difficulty': 'intermediate',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 9,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Déclarer une fonction:
   static long Factorielle(int n) {
       // instructions
   }

2. Récursion:
   Une fonction qui s\'appelle elle-même.

3. Cas de base:
   Le cas qui arrête la récursion.

4. Points importants:
   - Le cas de base est essentiel pour éviter les boucles infinies.
   - La récursion peut être plus lisible mais moins efficace que les boucles itératives.
</pre>''',
                'instructions': 'Créez une fonction qui calcule la factorielle d\'un nombre.',
                'starter_code': 'using System;\n\nclass Programme {\n    // Créez la fonction factorielle ici\n    static void Main() {\n        int nombre;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static long Factorielle(int n) {\n        if (n <= 1) return 1;\n        return n * Factorielle(n - 1);\n    }\n    static void Main() {\n        int nombre;\n        Console.Write("Entrez un nombre: ");\n        nombre = Convert.ToInt32(Console.ReadLine());\n        if (nombre < 0) {\n            Console.WriteLine("Erreur: nombre négatif");\n        } else {\n            Console.WriteLine($"{nombre}! = {Factorielle(nombre)}");\n        }\n    }\n}',
                'test_cases': [
                    {'input': '5\n', 'output': 'Entrez un nombre: 5! = 120'},
                    {'input': '0\n', 'output': 'Entrez un nombre: 0! = 1'}
                ],
                'hints': [
                    'Utilisez la récursion ou une boucle',
                    'N\'oubliez pas le cas de base (0! = 1)',
                    'Attention aux nombres négatifs'
                ],
                'common_errors': [
                    'Cas de base incorrect pour la récursion',
                    'Dépassement de pile pour les grands nombres',
                    'Ne pas gérer les nombres négatifs',
                    'Mauvaise utilisation de la récursion ou boucle iterative'
                ],
                'points': 50,
                'incorrect_examples': '[{"code": "using System; class Programme { static long Factorielle(int n) { return n * Factorielle(n); } }", "error": "Cas de base manquant"}, {"code": "using System; class Programme { static long Factorielle(int n) { if (n == 0) return 0; return n * Factorielle(n - 1); } }", "error": "Cas de base incorrect"}]'
            },
            {
                'title': 'Générateur de Motifs',
                'description': 'Utiliser les boucles imbriquées pour créer des motifs.',
                'difficulty': 'intermediate',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 10,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Boucles imbriquées:
   for (int i = 1; i <= hauteur; i++) {
       for (int j = 1; j <= largeur; j++) {
           // instructions à répéter
       }
   }

2. Saut de ligne:
   Console.WriteLine();

3. Points importants:
   - Contrôlez le nombre d\'espaces et d\'étoiles selon les lignes.
   - Utilisez des boucles imbriquées pour créer des motifs répétitifs.
</pre>''',
                'instructions': 'Créez un programme qui affiche un triangle d\'étoiles.',
                'starter_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int hauteur;\n        // Votre code ici\n    }\n}',
                'solution_code': 'using System;\n\nclass Programme {\n    static void Main() {\n        int hauteur;\n        Console.Write("Hauteur du triangle: ");\n        hauteur = Convert.ToInt32(Console.ReadLine());\n        for (int i = 1; i <= hauteur; i++) {\n            for (int j = 1; j <= hauteur - i; j++) {\n                Console.Write(" ");\n            }\n            for (int j = 1; j <= 2 * i - 1; j++) {\n                Console.Write("*");\n            }\n            Console.WriteLine();\n        }\n    }\n}',
                'test_cases': [
                    {'input': '3\n', 'output': 'Hauteur du triangle:   *\n **\n***\n'}
                ],
                'hints': [
                    'Utilisez des boucles imbriquées',
                    'Calculez les espaces et étoiles nécessaires',
                    'La ligne i a 2*i - 1 étoiles'
                ],
                'common_errors': [
                    'Mauvaise gestion des espaces',
                    'Mauvais calcul du nombre d\'étoiles',
                    'Ne pas gérer les sauts de ligne',
                    'Imbrication incorrecte des boucles'
                ],
                'points': 55,
                'incorrect_examples': '''[
                    {
                        "code": "using System; class Programme { static void Main() { for (int i =1; i <= 3; i++) { for (int j = 1; j <= i; j++) Console.Write(\"*\\\"); } } }",
                        "error": "Triangle incorrect"
                    },
                    {
                        "code": "using System; classProgramme { static void Main() { for (int i = 1; i<= 3; i++) { for (int j = 1; j <= 3; j++) Console.Write(\"*\\\"); } } }",
                        "error": "Triangle incorrect"
                    }
                ]'''
            },
            {
                'title': 'Gestion des Étudiants',
                'description': 'Introduction à la programmation orientée objet en C#.',
                'difficulty': 'advanced',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 11,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Définir une classe:
   class Etudiant {
       // propriétés et méthodes
   }

2. Propriétés:
   public string Nom { get; set; }

3. Méthodes:
   public void AjouterNote(double note) { ... }

4. Points importants:
   - Encapsulation: protéger les données internes de la classe.
   - Les modificateurs d\'accès (public, private) contrôlent l\'accès aux membres de la classe.
</pre>''',
                'instructions': 'Créez une classe Étudiant avec des propriétés et des méthodes pour gérer les informations des étudiants.',
                'starter_code': '''using System;
1292:
1293:class Etudiant {
1294:    // Ajoutez les propriétés ici
1295:
1296:    // Ajoutez les méthodes ici
1297:}
1298:
1299:class Programme {
1300:    static void Main() {
1301:        // Votre code ici
1302:    }
1303:}''',
                'solution_code': '''using System;
1305:
1306:class Etudiant {
1307:    public string Nom { get; set; }
1308:    public int Age { get; set; }
1309:    public double Moyenne { get; private set; }
1310:    private int nombreNotes = 0;
1311:    private double sommeNotes = 0;
1312:
1313:    public void AjouterNote(double note) {
1314:        if (note >= 0 && note <= 100) {
1315:            sommeNotes += note;
1316:            nombreNotes++;
1317:            Moyenne = sommeNotes / nombreNotes;
1318:        }
1319:    }
1320:
1321:    public string ObtenirInformations() {
1322:        return $"Nom: {Nom}, Age: {Age}, Moyenne: {Moyenne:F1}";
1323:    }
1324:}
1325:
1326:class Programme {
1327:    static void Main() {
1328:        Etudiant etudiant = new Etudiant();
1329:        Console.Write("Nom de l'étudiant: ");
1330:        etudiant.Nom = Console.ReadLine();
1331:        Console.Write("Age de l'étudiant: ");
1332:        etudiant.Age = Convert.ToInt32(Console.ReadLine());
1333:        Console.Write("Note: ");
1334:        etudiant.AjouterNote(Convert.ToDouble(Console.ReadLine()));
1335:        Console.WriteLine(etudiant.ObtenirInformations());
1336:    }
1337:}''',
                'test_cases': [
                    {'input': 'Marie\n16\n85\n', 'output': 'Nom de l\'étudiant: Age de l\'étudiant: Note: Nom: Marie, Age: 16, Moyenne: 85.0'}
                ],
                'hints': [
                    'Utilisez des propriétés auto-implémentées pour Nom et Age',
                    'Encapsulez la logique de calcul de la moyenne',
                    'Utilisez le formatage de chaîne pour l\'affichage'
                ],
                'common_errors': [
                    'Mauvaise déclaration des propriétés',
                    'Mauvaise implémentation des méthodes',
                    'Ne pas gérer les erreurs d\'entrée',
                    'Mauvaise utilisation des modificateurs d\'accès'
                ],
                'points': 60,
                'incorrect_examples': '[{"code": "using System; class Etudiant { public string Nom; public int Age; }", "error": "Propriétés incomplètes"}, {"code": "using System; class Etudiant { public string Nom { get; set; } public int Age { get; set; } public double Moyenne { get; set; } }", "error": "Moyenne non encapsulée"}]'
            },
            {
                'title': 'Liste Chaînée Simple',
                'description': 'Implémentation d\'une structure de données de base.',
                'difficulty': 'advanced',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 12,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Classe Noeud:
   class Noeud {
       public int Valeur;
       public Noeud Suivant;
   }

2. Liste chaînée:
   class ListeChainee {
       private Noeud tete;
   }

3. Méthodes Ajouter et Afficher:
   public void Ajouter(int valeur) { ... }
   public void Afficher() { ... }

4. Points importants:
   - La gestion des pointeurs est cruciale.
   - Gérez le cas où la liste est vide.
</pre>''',
                'instructions': 'Créez une liste chaînée simple avec des opérations de base (ajout et affichage).',
                'starter_code': '''using System;
1385:
1386:class Noeud {
1387:    public int Valeur;
1388:    public Noeud Suivant;
1389:
1390:    public Noeud(int valeur) {
1391:        Valeur = valeur;
1392:        Suivant = null;
1393:    }
1394:}
1395:
1396:class ListeChainee {
1397:    private Noeud tete;
1398:
1399:    // Implémentez les méthodes Ajouter et Afficher
1400:}
1401:
1402:class Programme {
1403:    static void Main() {
1404:        // Votre code ici
1405:    }
1406:}''',
                'solution_code': '''using System;
1408:
1409:class Noeud {
1410:    public int Valeur;
1411:    public Noeud Suivant;
1412:
1413:    public Noeud(int valeur) {
1414:        Valeur = valeur;
1415:        Suivant = null;
1416:    }
1417:}
1418:
1419:class ListeChainee {
1420:    private Noeud tete;
1421:
1422:    public void Ajouter(int valeur) {
1423:        Noeud nouveau = new Noeud(valeur);
1424:        if (tete == null) {
1425:            tete = nouveau;
1426:        } else {
1427:            Noeud courant = tete;
1428:            while (courant.Suivant != null) {
1429:                courant = courant.Suivant;
1430:            }
1431:            courant.Suivant = nouveau;
1432:        }
1433:    }
1434:
1435:    public void Afficher() {
1436:        Noeud courant = tete;
1437:        while (courant != null) {
1438:            Console.Write(courant.Valeur + " ");
1439:            courant = courant.Suivant;
1440:        }
1441:        Console.WriteLine();
1442:    }
1443:}
1444:
1445:class Programme {
1446:    static void Main() {
1447:        ListeChainee liste = new ListeChainee();
1448:        Console.Write("Nombre d'éléments: ");
1449:        int n = Convert.ToInt32(Console.ReadLine());
1450:
1451:        for (int i = 0; i < n; i++) {
1452:            Console.Write($"Élément {i + 1}: ");
1453:            int valeur = Convert.ToInt32(Console.ReadLine());
1454:            liste.Ajouter(valeur);
1455:        }
1456:
1457:        Console.Write("Liste: ");
1458:        liste.Afficher();
1459:    }
1460:}''',
                'test_cases': [
                    {'input': '3\n10\n20\n30\n', 'output': 'Nombre d\'éléments: Élément 1: Élément 2: Élément 3: Liste: 10 20 30 '}
                ],
                'hints': [
                    'Créez une classe Noeud pour chaque élément',
                    'Gardez une référence vers le premier nœud (tête)',
                    'Parcourez la liste pour ajouter à la fin'
                ],
                'common_errors': [
                    'Mauvaise gestion des pointeurs',
                    'Fuites de mémoire',
                    'Ne pas gérer correctement le cas de liste vide',
                    'Ne pas parcourir correctement la liste'
                ],
                'points': 65,
                'incorrect_examples': '[{"code": "using System; class Noeud { public int Valeur; }", "error": "Noeud incomplet"}, {"code": "using System; class ListeChainee { public void Ajouter(int valeur) { } }", "error": "Méthode Ajouter incomplète"}]'
            },
            {
                'title': 'Gestionnaire de Tâches',
                'description': 'Application de gestion de tâches avec priorités.',
                'difficulty': 'advanced',
                'curriculum': 'ICS3U',
                'language': 'csharp',
                'sequence': 13,
                'syntax_help': '''<h6>Éléments de syntaxe nécessaires:</h6>
<pre>
1. Classe Tache:
   class Tache {
       public string Description;
       public int Priorite;
   }

2. Liste de tâches:
   List<Tache> taches = new List<Tache>();

3. Trier la liste:
   taches.Sort((a, b) => b.Priorite.CompareTo(a.Priorite));

4. Points importants:
   - Utilisez une List<T> pour stocker les tâches.
   - Implémentez la méthode CompareTo pour trier par priorité.
</pre>''',
                'instructions': 'Créez un gestionnaire de tâches qui permet d\'ajouter et d\'afficher des tâches avec leurs priorités.',
                'starter_code': '''using System;
1505:using System.Collections.Generic;
1506:
1507:class Tache {
1508:    // Implémentez la classe Tache
1509:}
1510:
1511:class Programme {
1512:    static void Main() {
1513:        // Votre code ici
1514:    }
1515:}''',
                'solution_code': '''using System;
1517:using System.Collections.Generic;
1518:
1519:class Tache {
1520:    public string Description { get; set; }
1521:    public int Priorite { get; set; }
1522:
1523:    public Tache(string description, int priorite) {
1524:        Description = description;
1525:        Priorite = priorite;
1526:    }
1527:
1528:    public override string ToString() {
1529:        return $"[Priorité: {Priorite}] {Description}";
1530:    }
1531:}
1532:
1533:class Programme {
1534:    static void Main() {
1535:        List<Tache> taches = new List<Tache>();
1536:
1537:        Console.Write("Nombre de tâches: ");
1538:        int n = Convert.ToInt32(Console.ReadLine());
1539:
1540:        for (int i = 0; i < n; i++) {
1541:            Console.Write($"Description de la tâche {i + 1}: ");
1542:            string description = Console.ReadLine();
1543:            Console.Write("Priorité (1-5): ");
1544:            int priorite = Convert.ToInt32(Console.ReadLine());
1545:            taches.Add(new Tache(description, priorite));
1546:        }
1547:
1548:        taches.Sort((a, b) => b.Priorite.CompareTo(a.Priorite));
1549:
1550:        Console.WriteLine("\nListe des tâches par priorité:");
1551:        foreach (var tache in taches) {
1552:            Console.WriteLine(tache);
1553:        }
1554:    }
1555:}''',
                'test_cases': [
                    {'input': '2\nÉtudier pour l\'examen\n5\nFaire les courses\n3\n', 
                     'output': 'Nombre de tâches: Description de la tâche 1: Priorité (1-5): Description de la tâche 2: Priorité (1-5): \nListe des tâches par priorité:\n[Priorité: 5] Étudier pour l\'examen\n[Priorité: 3] Faire les courses'}
                ],
                'hints': [
                    'Utilisez une List<T> pour stocker les tâches',
                    'Implémentez ToString() pour l\'affichage',
                    'Utilisez Sort() avec un comparateur personnalisé'
                ],
                'common_errors': [
                    'Mauvaise gestion de la liste de tâches',
                    'Mauvaise implémentation de la comparaison de priorités',
                    'Ne pas trier correctement la liste',
                    'Ne pas afficher correctement la sortie'
                ],
                'points': 70,
                'incorrect_examples': '[{"code": "using System; using System.Collections.Generic; class Tache { public string Description; }", "error": "Tache incomplète"}, {"code": "using System; using System.Collections.Generic; class Programme { static void Main() { List<Tache> taches = new List<Tache>(); taches.Sort(); } }", "error": "Tri incorrect"}]'
            }
        ]

        for activity_data in activities:
            activity = CodingActivity(**activity_data)
            db.session.add(activity)

        db.session.commit()
        logging.info(f"Successfully created {len(activities)} activities")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating activities: {str(e)}")
        raise

# Initialize activities in app context
with app.app_context():
    create_initial_activities()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Student.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
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
        user = Student(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        flash('Votre compte a été créé! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/validate_code', methods=['POST'])
def validate_code():
    """
    Validate code syntax in real-time and provide bilingual feedback and syntax help
    """
    code = request.json.get('code', '')
    language = request.json.get('language', '')
    activity_id = request.json.get('activity_id')

    if not code or not language or not activity_id:
        return jsonify({'errors': [], 'syntax_help': ''})

    activity = CodingActivity.query.get(activity_id)
    if not activity:
        return jsonify({'errors': [], 'syntax_help': ''})

    errors = []

    # Basic syntax validation for C++
    if language == 'cpp':
        if '#include' not in code:
            errors.append({
                'message_fr': 'N\'oubliez pas d\'inclure les bibliothèques nécessaires',
                'message_en': 'Don\'t forget to include necessary libraries'
            })
        if 'main()' not in code:
            errors.append({
                'message_fr': 'La fonction main() est requise',
                'message_en': 'The main() function is required'
            })
        if code.count('{') != code.count('}'):
            errors.append({
                'message_fr': 'Vérifiez vos accolades - il en manque certaines',
                'message_en': 'Check your braces - some are missing'
            })

    return jsonify({
        'errors': errors,
        'syntax_help': activity.syntax_help
    })