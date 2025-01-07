import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_login import LoginManager, current_user
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.logger import setup_logging, get_logger, log_error
from database import db, init_db
from extensions import init_extensions, limiter
from models import Student

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Basic configuration
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key"),
        DEBUG=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_ENABLED=True,
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
    )

    # Setup logging
    setup_logging(app)
    logger = get_logger('app')

    try:
        # Initialize database
        init_db(app)

        # Initialize extensions
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

        # Register error handlers
        @app.errorhandler(400)
        def bad_request_error(error):
            error_data = log_error(error, error_type="BAD_REQUEST")
            return render_template('errors/400.html', error=error_data), 400

        @app.errorhandler(401)
        def unauthorized_error(error):
            error_data = log_error(error, error_type="UNAUTHORIZED")
            return render_template('errors/401.html', error=error_data), 401

        @app.errorhandler(403)
        def forbidden_error(error):
            error_data = log_error(error, error_type="FORBIDDEN")
            return render_template('errors/403.html', error=error_data), 403

        @app.errorhandler(404)
        def not_found_error(error):
            error_data = log_error(error, error_type="NOT_FOUND")
            return render_template('errors/404.html', error=error_data), 404

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            error_data = log_error(error, error_type="INTERNAL_SERVER_ERROR")
            return render_template('errors/500.html', error=error_data), 500

        @app.errorhandler(Exception)
        def handle_unhandled_error(error):
            db.session.rollback()
            error_data = log_error(error, error_type="UNHANDLED_EXCEPTION")
            return render_template('errors/500.html', error=error_data), 500

        # Register blueprints
        from routes.auth_routes import auth
        app.register_blueprint(auth)

        from routes.activity_routes import activities
        app.register_blueprint(activities, url_prefix='/activities')

        from routes.tutorial import tutorial_bp
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')

        # Root route
        @app.route('/')
        def index():
            if 'lang' not in session:
                session['lang'] = 'fr'
            return render_template('index.html',
                                lang=session.get('lang', 'fr'))

        # Create database tables
        with app.app_context():
            db.create_all()

        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}")
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)