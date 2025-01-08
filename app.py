import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, check_db_connection
from models import Student

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, 
                static_url_path='',
                static_folder='static',
                template_folder='templates')

    # Basic configuration
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_session'),
        SESSION_FILE_THRESHOLD=500,
        PERMANENT_SESSION_LIFETIME=1800,
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        },
        # Enable CSRF protection
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_SECRET_KEY=os.environ.get("CSRF_SECRET_KEY", "csrf_key_for_development"),
        # Session security
        SESSION_COOKIE_SECURE=False,  # Set to True in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )

    try:
        # Create session directory if not exists
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

        # Initialize extensions in order
        db.init_app(app)
        csrf = CSRFProtect(app)
        Session(app)
        CORS(app)

        # Initialize login manager
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'

        @login_manager.user_loader
        def load_user(user_id):
            try:
                return Student.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Handle proxy headers
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        # Add main route
        @app.route('/')
        def index():
            return render_template('index.html')

        @app.route('/activities')
        def activities():
            return redirect(url_for('activities.list_activities'))

        # Register blueprints
        from routes.auth_routes import auth
        app.register_blueprint(auth, url_prefix='/auth')

        from routes.activity_routes import activities
        app.register_blueprint(activities)

        from routes.tutorial import tutorial_bp
        app.register_blueprint(tutorial_bp)

        # Create database tables
        with app.app_context():
            db.create_all()
            if not check_db_connection():
                raise Exception("Failed to verify database connection")

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)