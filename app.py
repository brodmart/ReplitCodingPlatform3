import os
import logging
import secrets
import time
from flask import Flask, render_template, request, jsonify, session, g, flash, send_from_directory, redirect, url_for
from flask_cors import CORS
from database import init_db, db
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_login import current_user
from flask_migrate import Migrate
from extensions import init_extensions
from models import Student
from routes.auth_routes import auth
from routes.activity_routes import activities

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    # Configure security and session settings
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TEMPLATES_AUTO_RELOAD=True,
        SEND_FILE_MAX_AGE_DEFAULT=0,
        DEBUG=True,
        SESSION_COOKIE_SECURE=False,  # Set to True in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_ENABLED=True,  # Enable CSRF protection
        WTF_CSRF_TIME_LIMIT=3600,
        WTF_CSRF_SSL_STRICT=False,
        RATELIMIT_DEFAULT="200 per day",
        RATELIMIT_STORAGE_URL="memory://",
        RATELIMIT_HEADERS_ENABLED=True,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    )

    try:
        # Initialize CSRF protection first
        csrf = CSRFProtect()
        csrf.init_app(app)

        # Initialize database
        logger.info("Initializing database...")
        init_db(app)

        # Initialize migrations
        migrate = Migrate(app, db)

        # Initialize extensions with db instance
        init_extensions(app, db)

        # Enable CORS with specific origins
        CORS(app, resources={
            r"/auth/*": {"origins": "*"},
            r"/activities/*": {"origins": "*"}
        })

        # Register blueprints with URL prefixes
        logger.info("Registering blueprints...")
        app.register_blueprint(auth)
        app.register_blueprint(activities, url_prefix='/activities')

        @app.route('/')
        def index():
            """Main editor page - accessible without authentication"""
            try:
                # Always render the editor page without requiring authentication
                lang = session.get('lang', 'fr')
                logger.debug("Rendering editor template")
                return render_template('index.html', lang=lang)
            except Exception as e:
                logger.error(f"Error rendering editor template: {str(e)}")
                return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

        @app.route('/grade/<grade>')
        def redirect_to_activities(grade):
            """Redirect to activities list - accessible without authentication"""
            return redirect(url_for('activities.list_activities', grade=grade))

        @app.before_request
        def before_request():
            g.start_time = time.time()
            g.user = current_user
            if 'lang' not in session:
                session['lang'] = 'fr'
            logger.debug(f"Processing request: {request.endpoint}")

        @app.after_request
        def after_request(response):
            if hasattr(g, 'start_time'):
                elapsed = time.time() - g.start_time
                response.headers['X-Response-Time'] = str(elapsed)

            if app.debug:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'

            return response

        @app.teardown_appcontext
        def shutdown_session(exception=None):
            db.session.remove()

        return app

    except Exception as e:
        logger.error(f"Error creating application: {str(e)}", exc_info=True)
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)