import os
import logging
import secrets
import html
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, g
from flask_compress import Compress
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
from database import db, init_db, DatabaseHealthCheck
from extensions import limiter, PerformanceMiddleware

# Configure logging with proper format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'
)
logger = logging.getLogger(__name__)

def log_error(error, context=None):
    """Global error tracking function"""
    error_id = secrets.token_hex(8)
    error_data = {
        'error_id': error_id,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.utcnow().isoformat(),
        'context': context
    }
    logger.error(f"Application error: {error_data}")
    return error_data

# Initialize Flask app
app = Flask(__name__)
compress = Compress()
compress.init_app(app)
app.config['COMPRESS_MIN_SIZE'] = 500  # Only compress responses larger than 500 bytes
app.config['COMPRESS_LEVEL'] = 6  # Higher compression level
app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/javascript', 'application/json']
app.wsgi_app = PerformanceMiddleware(app.wsgi_app)

# Global rate limiting
@app.before_request
def global_rate_limit():
    if request.remote_addr:
        key = f'rate_limit_{request.remote_addr}'
        try:
            if cache.get(key) and cache.get(key) > 100:  # 100 requests per minute
                return jsonify({'error': 'Rate limit exceeded'}), 429
            cache.inc(key, timeout=60)
        except:
            pass  # Fail open if cache errors

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = str(elapsed)
    return response

# Security configurations
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Session timeout
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize extensions
init_db(app)  # Initialize database with configuration
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
csrf = CSRFProtect(app)
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
limiter.init_app(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate

# Add CSP and security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to response"""
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",  # Required for Monaco editor
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: https:",
        'font-src': "'self' data:",
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
        'form-action': "'self'",
        'base-uri': "'self'"
    }

    response.headers['Content-Security-Policy'] = '; '.join(f"{key} {value}" for key, value in csp.items())
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

def sanitize_input(f):
    """Decorator to sanitize user input"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.form:
            clean_form = {key: html.escape(str(value)) for key, value in request.form.items()}
            request.form = clean_form
        if request.args:
            clean_args = {key: html.escape(str(value)) for key, value in request.args.items()}
            request.args = clean_args
        return f(*args, **kwargs)
    return decorated_function

# Register error handlers
@app.errorhandler(408)
def request_timeout(error):
    return jsonify({'error': 'Request timeout'}), 408

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    error_data = log_error(error, context={'route': request.path, 'method': request.method})
    return render_template('errors/500.html', error_id=error_data.get('error_id')), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'strong'

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
@sanitize_input
def execute_code():
    """Execute code and return the result"""
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', '').lower()

        if not code or not language:
            return jsonify({'error': 'Missing code or language parameter'}), 400

        if language not in ['cpp', 'csharp']:
            return jsonify({'error': 'Unsupported language'}), 400

        # Use parameterized function call
        from compiler_service import compile_and_run
        result = compile_and_run(code=code, language=language)
        return jsonify(result)

    except Exception as e:
        error_data = log_error(e, context={'route': 'execute', 'method': 'POST'})
        return jsonify({'error': 'An unexpected error occurred during execution', 'error_id': error_data.get('error_id')}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)