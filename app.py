import os
import logging
from flask import Flask, render_template, request, session, jsonify
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.logger import setup_logging
from database import db, check_db_connection
from extensions import init_extensions
from models import Student

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, 
                static_url_path='',
                static_folder='static',
                template_folder='templates')

    # Basic configuration
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
        DEBUG=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_ENABLED=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        },
        # Session configuration for interactive console
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_session'),
        SESSION_FILE_THRESHOLD=500,
        PERMANENT_SESSION_LIFETIME=1800  # 30 minutes
    )

    # Setup logging first
    setup_logging(app)
    logger = logging.getLogger('app')

    try:
        # Initialize database
        logger.info("Initializing database...")
        db.init_app(app)

        # Create session directory
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

        # Initialize Flask-Session
        Session(app)

        # Initialize extensions before blueprints
        init_extensions(app, db)

        # Initialize login manager
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
        login_manager.login_message_category = 'info'

        @login_manager.user_loader
        def load_user(user_id):
            try:
                return Student.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Handle proxy headers
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        # Register blueprints
        try:
            from routes.auth_routes import auth
            app.register_blueprint(auth)

            from routes.activity_routes import activities
            app.register_blueprint(activities, url_prefix='/activities')

            from routes.tutorial import tutorial_bp
            app.register_blueprint(tutorial_bp, url_prefix='/tutorial')

            logger.info("All blueprints registered successfully")
        except Exception as e:
            logger.error(f"Failed to register blueprints: {str(e)}")
            raise

        # Create database tables within app context
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.error(f"Failed to create database tables: {str(e)}")
                raise

            # Verify database connection
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