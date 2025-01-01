import os
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# Initialize database
db = SQLAlchemy()

# Initialize caching
cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# App configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 1800
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
app.config['SESSION_COOKIE_HTTPONLY'] = True

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
    'pool_pre_ping': True
}

# Initialize extensions
db.init_app(app)
cache.init_app(app)

# Setup CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Import models after db initialization to avoid circular imports
from models import Student

@login_manager.user_loader
def load_user(id):
    try:
        return Student.query.get(int(id))
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
        return None

@app.route('/')
def index():
    try:
        achievements = []
        if current_user.is_authenticated:
            achievements = [sa.achievement for sa in current_user.achievements]
        return render_template('index.html', achievements=achievements)
    except Exception as e:
        logger.error(f"Database error in index route: {str(e)}")
        flash('An error occurred while loading the page.', 'error')
        return render_template('index.html', achievements=[]), 500

@app.route('/editor')
def editor():
    """Render the code editor page"""
    lang = session.get('lang', 'en')
    return render_template('editor.html', lang=lang)

@app.route('/execute', methods=['POST'])
@limiter.limit("20 per minute")
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
        from compiler_service import compile_and_run
        result = compile_and_run(code=code, language=language)
        if not result.get('success', False):
            return jsonify({
                'error': result.get('error', 'An error occurred during execution')
            }), 400

        return jsonify({
            'success': True,
            'output': result.get('output', '')
        })

    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred during execution'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = 5000
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)