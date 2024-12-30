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
    activities = [
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
        }
    ]

    # Remove records in correct order to maintain referential integrity
    TutorialProgress.query.delete()
    TutorialStep.query.delete()
    StudentProgress.query.delete()
    CodingActivity.query.delete()

    # Create activities
    for activity_data in activities:
        activity = CodingActivity(**activity_data)
        db.session.add(activity)
        db.session.commit()  # Commit to get activity.id

        # Add tutorial steps
        step1 = TutorialStep(
            activity=activity,
            step_number=1,
            title="Introduction aux conditions",
            content="Dans cette étape, nous allons apprendre à utiliser les conditions if-else en C#.",
            code_snippet="if (condition) {\n    // code si vrai\n} else {\n    // code si faux\n}",
            expected_output="",
            hint="Les conditions permettent à votre programme de prendre des décisions."
        )

        step2 = TutorialStep(
            activity=activity,
            step_number=2,
            title="Lecture des entrées",
            content="Apprenons à lire un nombre entré par l'utilisateur.",
            code_snippet="Console.Write(\"Entrez un nombre: \");\nint nombre = Convert.ToInt32(Console.ReadLine());",
            expected_output="Entrez un nombre: ",
            hint="Utilisez Console.ReadLine() pour lire l'entrée et Convert.ToInt32() pour la convertir en nombre."
        )

        step3 = TutorialStep(
            activity=activity,
            step_number=3,
            title="Vérification pair/impair",
            content="Utilisons l'opérateur modulo (%) pour vérifier si un nombre est pair ou impair.",
            code_snippet="if (nombre % 2 == 0) {\n    Console.WriteLine(\"Le nombre est pair.\");\n}",
            expected_output="Le nombre est pair.",
            hint="Un nombre est pair si sa division par 2 ne donne aucun reste."
        )

        db.session.add(step1)
        db.session.add(step2)
        db.session.add(step3)

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