import os
import logging
import secrets
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from database import init_db, db
from extensions import init_extensions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Configure secret key
    app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

    # Security configurations
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_TIME_LIMIT=3600,
        WTF_CSRF_SSL_STRICT=True
    )

    try:
        # Initialize database
        init_db(app)

        # Initialize extensions
        init_extensions(app)

        # Register blueprints
        from routes.auth_routes import auth
        from routes.activity_routes import activities

        app.register_blueprint(auth, url_prefix='/auth')
        app.register_blueprint(activities, url_prefix='/activities')

        # Register error handlers
        register_error_handlers(app)

        return app

    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}")
        raise

def register_error_handlers(app):
    """Register error handlers for the application"""

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

# Create the application instance
app = create_app()

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

    # Security headers
    response.headers.update({
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