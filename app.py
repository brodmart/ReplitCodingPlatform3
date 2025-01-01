import os
import logging
import secrets
import time
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

    # Enhanced security configurations
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        REMEMBER_COOKIE_DURATION=timedelta(days=14),
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE='Lax',
        WTF_CSRF_TIME_LIMIT=3600,
        WTF_CSRF_SSL_STRICT=True,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024  # 10MB max file size
    )

    # Compression settings
    app.config['COMPRESS_MIN_SIZE'] = 500
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html', 'text/css', 'text/javascript',
        'application/json', 'application/javascript'
    ]

    # Add performance middleware
    app.wsgi_app = PerformanceMiddleware(app.wsgi_app)

    try:
        # Initialize database with retry logic
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
    """Set start time for request timing"""
    g.start_time = time.time()

@app.after_request
def after_request(response):
    """Add security headers and timing information"""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = str(elapsed)

    # Enhanced security headers with strict CSP
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'nonce-{nonce}' cdn.jsdelivr.net",
        'style-src': "'self' cdn.jsdelivr.net",
        'img-src': "'self' data: https:",
        'font-src': "'self' cdn.jsdelivr.net",
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
        'form-action': "'self'",
        'base-uri': "'self'",
        'upgrade-insecure-requests': ''
    }

    nonce = secrets.token_hex(16)
    session['csp_nonce'] = nonce
    csp['script-src'] = csp['script-src'].format(nonce=nonce)

    response.headers.update({
        'Content-Security-Policy': '; '.join(f"{key} {value}" for key, value in csp.items()),
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    })
    return response

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Properly remove database session"""
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
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)