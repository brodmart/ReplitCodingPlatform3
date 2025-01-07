import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_login import LoginManager, current_user
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.logger import log_error, get_logger, setup_logging
from database import db, init_db
from extensions import init_extensions
from models import Student

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
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_recycle": 300,
                "pool_pre_ping": True,
            }
        )

        # Setup enhanced logging
        setup_logging(app)
        logger.info("Enhanced logging system initialized")

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
                logger.error(f"Error loading user {user_id}", error=str(e))
                return None

        # Handle proxy headers
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        # Register error handlers with enhanced logging
        @app.errorhandler(400)
        def bad_request_error(error):
            error_data = log_error(error, error_type="BAD_REQUEST", 
                                 include_trace=True,
                                 endpoint=request.endpoint,
                                 method=request.method)
            logger.warning("Bad Request", 
                         error_id=error_data.get('id'),
                         path=request.path)
            return render_template('errors/400.html', error=error_data), 400

        @app.errorhandler(401)
        def unauthorized_error(error):
            error_data = log_error(error, error_type="UNAUTHORIZED",
                                 include_trace=True,
                                 endpoint=request.endpoint,
                                 authentication_present=bool(request.authorization))
            logger.warning("Unauthorized Access",
                         error_id=error_data.get('id'),
                         path=request.path)
            return render_template('errors/401.html', error=error_data), 401

        @app.errorhandler(403)
        def forbidden_error(error):
            error_data = log_error(error, error_type="FORBIDDEN",
                                 include_trace=True,
                                 user_id=current_user.id if not current_user.is_anonymous else None)
            logger.warning("Forbidden Access",
                         error_id=error_data.get('id'),
                         path=request.path)
            return render_template('errors/403.html', error=error_data), 403

        @app.errorhandler(404)
        def not_found_error(error):
            error_data = log_error(error, error_type="NOT_FOUND",
                                 include_trace=True,
                                 requested_path=request.path)
            logger.warning("Resource Not Found",
                         error_id=error_data.get('id'),
                         path=request.path)
            return render_template('errors/404.html', error=error_data), 404

        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()
            error_data = log_error(error, error_type="INTERNAL_SERVER_ERROR",
                                 include_trace=True,
                                 endpoint=request.endpoint)
            logger.error("Internal Server Error",
                        error_id=error_data.get('id'),
                        error_type="INTERNAL_SERVER_ERROR",
                        traceback=error_data.get('traceback'))
            return render_template('errors/500.html', error=error_data), 500

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            error_data = log_error(e, error_type="CSRF_ERROR",
                                 include_trace=True,
                                 endpoint=request.endpoint)
            logger.warning("CSRF Validation Failed",
                         error_id=error_data.get('id'),
                         path=request.path)
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_unhandled_error(error):
            error_data = log_error(error, error_type="UNHANDLED_EXCEPTION",
                                 include_trace=True,
                                 endpoint=request.endpoint)
            db.session.rollback()
            logger.critical("Unhandled Exception",
                          error_id=error_data.get('id'),
                          error_type=error.__class__.__name__,
                          traceback=error_data.get('traceback'))
            return render_template('errors/500.html', error=error_data), 500

        # Register request handlers with detailed logging
        @app.before_request
        def before_request():
            g.request_start_time = datetime.utcnow()
            logger.info("Incoming request",
                       method=request.method,
                       path=request.path,
                       endpoint=request.endpoint,
                       ip=request.remote_addr,
                       user_agent=str(request.user_agent))

        @app.after_request
        def after_request(response):
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                logger.info("Request completed",
                          path=request.path,
                          duration=duration.total_seconds(),
                          status_code=response.status_code,
                          content_length=response.content_length)
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
            logger.error("Failed to register blueprints",
                        error=str(e),
                        error_type=type(e).__name__)
            raise

        # Root route
        @app.route('/')
        def index():
            try:
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
            except Exception as e:
                logger.error("Error in index route",
                           error=str(e),
                           error_type=type(e).__name__)
                raise

        # Create database tables
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.error("Failed to create database tables",
                           error=str(e),
                           error_type=type(e).__name__)
                raise

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.critical("Failed to initialize application",
                       error=str(e),
                       error_type=type(e).__name__)
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)