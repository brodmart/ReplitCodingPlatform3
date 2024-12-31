import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from urllib.parse import urlparse
from database import db
from models import Student, CodingActivity, SharedCode
from routes import blueprints
from forms import LoginForm, RegisterForm
from compiler_service import compile_and_run

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
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(id):
    return Student.query.get(int(id))

# Register blueprints
for blueprint in blueprints:
    app.register_blueprint(blueprint)

@app.route('/')
def index():
    achievements = []
    if current_user.is_authenticated:
        achievements = [sa.achievement for sa in current_user.achievements]
    return render_template('index.html', achievements=achievements)

@app.route('/execute', methods=['POST'])
def execute_code():
    """Execute code and return the result"""
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    code = request.json.get('code')
    language = request.json.get('language')

    if not code or not language:
        return jsonify({'error': 'Missing code or language parameter'}), 400

    if language not in ['cpp', 'csharp']:
        return jsonify({'error': 'Unsupported language'}), 400

    try:
        result = compile_and_run(code=code, language=language)

        if not result.get('success', False):
            return jsonify({
                'error': result.get('error', 'Une erreur est survenue lors de l\'exécution')
            }), 400

        return jsonify({
            'success': True,
            'output': result.get('output', '')
        })

    except Exception as e:
        logging.error(f"Error executing code: {str(e)}")
        return jsonify({
            'error': 'Une erreur inattendue est survenue lors de l\'exécution'
        }), 500

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Student.query.filter_by(email=form.email.data).first()
        if user is None or not check_password_hash(user.password_hash, form.password.data):
            flash('Email ou mot de passe incorrect.', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
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

@app.route('/my-shared-codes')
@login_required
def my_shared_codes():
    """Display user's shared code snippets"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    shared_codes = SharedCode.query.filter_by(user_id=current_user.id)\
                                 .order_by(SharedCode.created_at.desc())\
                                 .all()

    return render_template('my_shares.html', shared_codes=shared_codes)

# Initialize database
with app.app_context():
    db.create_all()