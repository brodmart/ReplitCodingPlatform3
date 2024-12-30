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
    tutorial_steps = activity.tutorial_steps.order_by(TutorialStep.step_number).all()
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
    tutorial_steps = activity.tutorial_steps.order_by(TutorialStep.step_number).all()
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
            'points': 10,
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Comprendre la structure de base',
                    'content': 'Dans C++, chaque programme commence par des *includes* et une fonction principale appelée `main`.\n\nLes includes sont comme des livres de référence que votre programme peut utiliser. `iostream` contient les outils pour l\'entrée/sortie.\n\n**Erreurs courantes à éviter:**\n- Oublier le point-virgule après l\'include\n- Mal orthographier iostream\n- Oublier les chevrons < > autour de iostream',
                    'code_snippet': '#include <iostream>\n\nint main() {\n    // Le code va ici\n    return 0;\n}',
                    'hint': 'Regardez attentivement la syntaxe: #include doit être suivi de <iostream>'
                },
                {
                    'step_number': 2,
                    'title': 'Ajouter l\'instruction d\'affichage',
                    'content': 'Pour afficher du texte, nous utilisons `std::cout` suivi de `<<`.\n\nLe `std::` indique que nous utilisons l\'espace de noms standard de C++.\n\n**Erreurs courantes à éviter:**\n- Oublier std:: avant cout\n- Utiliser des apostrophes \' \' au lieu des guillemets " "\n- Oublier << entre cout et le texte\n- Oublier le point-virgule à la fin',
                    'code_snippet': '    std::cout << "Bonjour le monde!";',
                    'hint': 'Pensez à la direction des flèches <<, elles pointent vers cout'
                }
            ]
        },
        # Variables et Types (C++)
        {
            'title': 'Variables et Types',
            'description': 'Apprendre à utiliser les variables et les types de données en C++.',
            'difficulty': 'beginner',
            'curriculum': 'TEJ2O',
            'language': 'cpp',
            'sequence': 2,
            'instructions': 'Créez un programme qui déclare et utilise différents types de variables.',
            'starter_code': '#include <iostream>\n\nint main() {\n    // Déclarez vos variables ici\n    \n    // Affichez les résultats\n    return 0;\n}',
            'solution_code': '#include <iostream>\n\nint main() {\n    int age = 16;\n    double moyenne = 85.5;\n    char grade = \'A\';\n\n    std::cout << "Age: " << age << std::endl;\n    std::cout << "Moyenne: " << moyenne << std::endl;\n    std::cout << "Note: " << grade << std::endl;\n    return 0;\n}',
            'test_cases': [{'input': '', 'output': 'Age: 16\nMoyenne: 85.5\nNote: A'}],
            'points': 15,
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Types de données de base',
                    'content': 'En C++, il existe plusieurs types de données fondamentaux:\n- `int`: nombres entiers\n- `double`: nombres décimaux\n- `char`: caractères simples\n- `bool`: valeurs vraies/fausses\n\n**Erreurs courantes:**\n- Utiliser des virgules au lieu des points pour les décimaux\n- Ne pas initialiser les variables\n- Utiliser des guillemets " " pour les char au lieu des apostrophes \'',
                    'code_snippet': 'int age;      // Pour l\'âge\ndouble note;   // Pour les notes\nchar grade;    // Pour les lettres de notes',
                    'hint': 'Pensez à initialiser vos variables avec des valeurs appropriées'
                }
            ]
        },
        # Structures de Contrôle (C++)
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
                {'input': '95', 'output': 'Entrez une note: Excellent!'},
                {'input': '80', 'output': 'Entrez une note: Très bien!'},
                {'input': '65', 'output': 'Entrez une note: Passable'},
                {'input': '55', 'output': 'Entrez une note: Échec'}
            ],
            'points': 20,
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Structure if/else',
                    'content': 'Les structures conditionnelles permettent à votre programme de prendre des décisions.\n\n**Erreurs courantes:**\n- Oublier les accolades { }\n- Utiliser = au lieu de == pour la comparaison\n- Mal ordonner les conditions (commencer par les plus spécifiques)',
                    'code_snippet': 'if (condition) {\n    // code si vrai\n} else {\n    // code si faux\n}',
                    'hint': 'Commencez par la note la plus élevée et descendez progressivement'
                }
            ]
        },
        # ICS3U C# Activities
        {
            'title': 'Introduction à C#',
            'description': 'Premiers pas avec C# et les bases de la programmation.',
            'difficulty': 'beginner',
            'curriculum': 'ICS3U',
            'language': 'csharp',
            'sequence': 1,
            'instructions': 'Créez votre première application console C# qui affiche un message personnalisé.',
            'starter_code': 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        // Votre code ici\n    }\n}',
            'solution_code': 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        Console.WriteLine("Bienvenue dans le monde de C#!");\n    }\n}',
            'test_cases': [{'input': '', 'output': 'Bienvenue dans le monde de C#!'}],
            'points': 10,
            'tutorial_steps': [
                {
                    'step_number': 1,
                    'title': 'Structure d\'un programme C#',
                    'content': 'Un programme C# commence toujours par des `using` qui importent les fonctionnalités nécessaires.\n\nLa classe `Program` et la méthode `Main` sont les points d\'entrée de l\'application.\n\n**Erreurs courantes:**\n- Oublier le point-virgule après using System\n- Mal placer les accolades\n- Oublier static pour Main',
                    'code_snippet': 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        // Le code va ici\n    }\n}',
                    'hint': 'Vérifiez que toutes les accolades sont bien appariées'
                }
            ]
        }
    ]

    # Create activities and their tutorial steps
    for activity_data in activities:
        # Extract tutorial steps data
        tutorial_steps_data = activity_data.pop('tutorial_steps', [])

        # Create activity
        activity = CodingActivity(**activity_data)
        db.session.add(activity)
        db.session.flush()  # This assigns an ID to the activity

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