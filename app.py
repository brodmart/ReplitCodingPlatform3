import os
import logging
import secrets
import time
from flask import Flask, render_template, request, jsonify, session, g, flash, send_from_directory
from flask_cors import CORS
from database import init_db, db
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_login import current_user, AnonymousUserMixin
from extensions import init_extensions, login_manager
from routes.auth_routes import auth
from routes.activity_routes import activities

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# create the app
app = Flask(__name__)

# Configure security and session settings
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
    DEBUG=True,
    SESSION_COOKIE_SECURE=False,  # Set to True in production
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    WTF_CSRF_TIME_LIMIT=3600,
    WTF_CSRF_SSL_STRICT=False,
    LOGIN_VIEW='auth.login'  # Add this to ensure login_required works correctly
)

# Initialize database
init_db(app)

# Initialize extensions
init_extensions(app)

# Register blueprints with correct URL prefixes
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(activities, url_prefix='/activities')

# Custom static file serving with cache control
@app.route('/static/<path:filename>')
def custom_static(filename):
    response = send_from_directory(app.static_folder, filename)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.before_request
def before_request():
    """Set start time for request timing"""
    g.start_time = time.time()
    g.user = current_user
    # Set default language if not present
    if 'lang' not in session:
        session['lang'] = 'fr'
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
        return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)