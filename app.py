import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from urllib.parse import urlparse
from database import db
from models import Student, CodingActivity, SharedCode
from routes import blueprints
from forms import LoginForm, RegisterForm
from compiler_service import compile_and_run
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123")
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# Database configuration
logger.info("Configuring database connection...")
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    logger.error("DATABASE_URL environment variable is not set!")
    raise RuntimeError("DATABASE_URL must be set")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'pool_recycle': 1800,
}

logger.info("Initializing database...")
db.init_app(app)

# Setup CSRF protection
logger.info("Setting up CSRF protection...")
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# Initialize Flask-Login
logger.info("Initializing Flask-Login...")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(id):
    try:
        return Student.query.get(int(id))
    except SQLAlchemyError as e:
        logger.error(f"Error loading user: {str(e)}")
        return None

# Register blueprints
logger.info("Registering blueprints...")
for blueprint in blueprints:
    app.register_blueprint(blueprint)
    logger.debug(f"Registered blueprint: {blueprint.name}")

@app.route('/')
def index():
    try:
        achievements = []
        if current_user.is_authenticated:
            achievements = [sa.achievement for sa in current_user.achievements]
        return render_template('index.html', achievements=achievements)
    except SQLAlchemyError as e:
        logger.error(f"Database error in index route: {str(e)}")
        flash('Une erreur est survenue lors du chargement de la page.', 'error')
        return render_template('index.html', achievements=[])

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
        logger.error(f"Error executing code: {str(e)}")
        return jsonify({
            'error': 'Une erreur inattendue est survenue lors de l\'exécution'
        }), 500

@app.route('/my-shared-codes')
@login_required
def my_shared_codes():
    """Display user's shared code snippets"""
    try:
        shared_codes = SharedCode.query.filter_by(user_id=current_user.id)\
                                   .order_by(SharedCode.created_at.desc())\
                                   .all()
        return render_template('my_shares.html', shared_codes=shared_codes)
    except SQLAlchemyError as e:
        logger.error(f"Database error in my_shared_codes: {str(e)}")
        flash('Une erreur est survenue lors du chargement de vos codes partagés.', 'error')
        return render_template('my_shares.html', shared_codes=[])

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.route('/log-error', methods=['POST'])
def log_error():
    """Handle client-side error logging"""
    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Invalid format'}), 400

    error_data = request.json
    logger.error(f"Client error: {error_data}")
    return jsonify({'status': 'success'}), 200

# Initialize database
logger.info("Creating database tables...")
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

@app.route('/extend-session', methods=['POST'])
@login_required
def extend_session():
    """Extend the user's session"""
    try:
        session.permanent = True
        session.modified = True
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Error extending session: {str(e)}")
        return jsonify({'error': 'Failed to extend session'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)