import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from database import db, init_db
from extensions import limiter

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# Initialize extensions
init_db(app)  # Initialize database with configuration
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
csrf = CSRFProtect(app)
limiter.init_app(app)

# Register error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Import models after db initialization
from models import Student, CodeSubmission
from routes.auth_routes import auth

# Register blueprints
app.register_blueprint(auth)

@login_manager.user_loader
def load_user(id):
    try:
        return db.session.get(Student, int(id))
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/editor')
def editor():
    """Render the code editor page"""
    lang = session.get('lang', 'en')
    return render_template('editor.html', lang=lang)

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
        from compiler_service import compile_and_run
        result = compile_and_run(code=code, language=language)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred during execution'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)