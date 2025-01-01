import os
import logging
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, g
from database import db, init_db, DatabaseHealthCheck
from extensions import (
    init_extensions, PerformanceMiddleware, cache,
    compress, csrf, limiter, login_manager
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Security configurations
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Compression settings
    app.config['COMPRESS_MIN_SIZE'] = 500
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/javascript', 'application/json']

    # CSRF Protection
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600

    # Add performance middleware
    app.wsgi_app = PerformanceMiddleware(app.wsgi_app)

    try:
        # Initialize database
        init_db(app)

        # Initialize all extensions
        init_extensions(app)

    except Exception as e:
        logger.error(f"Failed to initialize app: {str(e)}")
        raise

    return app

# Create the application instance
app = create_app()

# Request handlers
@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = str(elapsed)

    # Add security headers
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
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

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    error_data = {
        'error_id': secrets.token_hex(8),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.utcnow().isoformat()
    }
    logger.error(f"Application error: {error_data}")
    return render_template('errors/500.html', error_id=error_data['error_id']), 500

# Basic routes
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
        error_id = secrets.token_hex(8)
        logger.error(f"Execution error {error_id}: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred during execution',
            'error_id': error_id
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)