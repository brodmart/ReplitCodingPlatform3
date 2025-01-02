import os
import logging
import secrets
import time
from flask import Flask, render_template, request, jsonify, session, g, flash, send_from_directory
from flask_cors import CORS
from database import init_db, db
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_login import LoginManager, current_user, AnonymousUserMixin

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# create the app
app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Initialize Flask-Compress
compress = Compress()
compress.init_app(app)

# Configure secret key and development settings
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
    DEBUG=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    WTF_CSRF_TIME_LIMIT=3600,
    WTF_CSRF_SSL_STRICT=False,
    SERVER_NAME=None
)

# Custom static file serving with cache control
@app.route('/static/<path:filename>')
def custom_static(filename):
    response = send_from_directory(app.static_folder, filename)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Initialize database
init_db(app)

@app.before_request
def before_request():
    """Set start time for request timing"""
    g.start_time = time.time()
    g.user = current_user
    logger.debug(f"Processing request: {request.endpoint}")

@app.after_request
def after_request(response):
    """Add security headers and timing information"""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = str(elapsed)

    # Disable caching for all responses in development
    if app.debug:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    return response

@app.route('/')
def index():
    try:
        # Get language preference from session
        lang = session.get('lang', 'fr')
        logger.debug("Rendering index template")
        return render_template('index.html', lang=lang)
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        return render_template('errors/500.html', lang=lang), 500

@app.route('/execute', methods=['POST'])
def execute_code():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    try:
        code = request.json.get('code', '').strip()
        language = request.json.get('language', 'cpp').lower()

        if not code:
            return jsonify({'error': 'Code cannot be empty'}), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({'error': 'Unsupported language'}), 400

        # Import here to avoid circular imports
        from compiler_service import compile_and_run

        # Execute the code using compiler service
        result = compile_and_run(code=code, language=language)

        return jsonify({
            'success': True,
            'output': result.get('output', ''),
            'error': result.get('error')
        })

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Add a simple user loader function
@login_manager.user_loader
def load_user(user_id):
    try:
        from models import Student
        return Student.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)