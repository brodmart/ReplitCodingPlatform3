import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.logger import log_error, log_exception, get_logger
from database import db, init_db
from extensions import init_extensions
from models import Student

# Configure logging from file
logging.config.fileConfig('logging.conf')
logger = get_logger('app')

def create_app():
    """Create and configure the Flask application"""
    try:
        app = Flask(__name__)

        # Configure basic settings
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key"),
            DEBUG=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            WTF_CSRF_ENABLED=True,
            SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_recycle": 300,
                "pool_pre_ping": True,
            }
        )

        # Initialize database first
        logger.info("Initializing database...")
        init_db(app)
        logger.info("Database initialized successfully")

        # Initialize extensions
        logger.info("Initializing extensions...")
        init_extensions(app, db)
        logger.info("Extensions initialized successfully")

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
        @log_exception("INTERNAL_SERVER_ERROR")
        def internal_error(error):
            db.session.rollback()
            error_data = log_error(error, error_type="INTERNAL_SERVER_ERROR")
            return render_template('errors/500.html', error=error_data), 500

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            error_data = log_error(e, error_type="CSRF_ERROR")
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_unhandled_error(error):
            error_data = log_error(error, error_type="UNHANDLED_EXCEPTION")
            db.session.rollback()
            return render_template('errors/500.html', error="Une erreur inattendue s'est produite"), 500

        # Register request handlers
        @app.before_request
        def before_request():
            g.request_start_time = datetime.utcnow()
            logger.info(f"Incoming request: {request.method} {request.path}")

        @app.after_request
        def after_request(response):
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                logger.info(f"Request completed: {request.path} - Status: {response.status_code} - Duration: {duration.total_seconds()}s")
            return response

        # Register blueprints
        try:
            logger.info("Starting blueprint registration...")

            from routes.auth_routes import auth
            app.register_blueprint(auth)
            logger.info("Registered auth blueprint")

            from routes.activity_routes import activities
            app.register_blueprint(activities, url_prefix='/activities')
            logger.info("Registered activities blueprint")

            from routes.tutorial import tutorial_bp
            app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
            logger.info("Registered tutorial blueprint")

        except Exception as e:
            error_data = log_error(e, error_type="BLUEPRINT_REGISTRATION_ERROR")
            raise

        # Root route
        @app.route('/')
        @log_exception("INDEX_ERROR")
        def index():
            language = request.args.get('language', 'cpp')
            if 'lang' not in session:
                session['lang'] = 'fr'

            templates = {
                'cpp': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
                'csharp': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}'
            }

            return render_template('index.html',
                               lang=session.get('lang', 'fr'),
                               language=language,
                               templates=templates)

        # Create database tables
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                error_data = log_error(e, error_type="DATABASE_INITIALIZATION_ERROR")
                raise

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        error_data = log_error(e, error_type="APP_INITIALIZATION_ERROR")
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)