import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_login import LoginManager, current_user
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.logger import log_error, log_exception, get_logger
from database import db, init_db
from extensions import init_extensions
from models import Student
import psutil
import platform

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
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
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
            error_data = log_error(error, error_type="BAD_REQUEST", include_trace=True,
                                  client_info={
                                      'ip': request.remote_addr,
                                      'user_agent': str(request.user_agent),
                                      'referrer': request.referrer,
                                      'path': request.path,
                                      'method': request.method,
                                      'headers': dict(request.headers),
                                      'args': dict(request.args),
                                      'form': dict(request.form)
                                  })
            logger.warning("Bad Request", error_id=error_data.get('id'))
            return render_template('errors/400.html', error=error_data), 400

        @app.errorhandler(401)
        def unauthorized_error(error):
            error_data = log_error(error, error_type="UNAUTHORIZED", include_trace=True,
                                   auth_info={
                                       'authenticated': current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False,
                                       'auth_type': request.headers.get('Authorization-Type'),
                                       'client_ip': request.remote_addr,
                                       'user_agent': str(request.user_agent)
                                   })
            logger.warning("Unauthorized Access", error_id=error_data.get('id'))
            return render_template('errors/401.html', error=error_data), 401

        @app.errorhandler(403)
        def forbidden_error(error):
            error_data = log_error(error, error_type="FORBIDDEN", include_trace=True,
                                   auth_info={
                                       'user_id': current_user.id if hasattr(current_user, 'id') else None,
                                       'roles': getattr(current_user, 'roles', []),
                                       'request_path': request.path,
                                       'request_method': request.method
                                   })
            logger.warning("Forbidden Access", error_id=error_data.get('id'))
            return render_template('errors/403.html', error=error_data), 403

        @app.errorhandler(404)
        def not_found_error(error):
            error_data = log_error(error, error_type="NOT_FOUND", include_trace=True,
                                   request_info={
                                       'path': request.path,
                                       'method': request.method,
                                       'args': dict(request.args),
                                       'referrer': request.referrer,
                                       'user_agent': str(request.user_agent)
                                   })
            logger.warning("Resource Not Found", error_id=error_data.get('id'))
            return render_template('errors/404.html', error=error_data), 404

        @app.errorhandler(500)
        @log_exception("INTERNAL_SERVER_ERROR")
        def internal_error(error):
            db.session.rollback()
            error_data = log_error(error, error_type="INTERNAL_SERVER_ERROR", include_trace=True,
                                   performance_metrics={
                                       'response_time': (datetime.utcnow() - g.request_start_time).total_seconds() if hasattr(g, 'request_start_time') else None,
                                       'memory_usage': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
                                       'cpu_percent': psutil.Process().cpu_percent(),
                                       'thread_count': len(psutil.Process().threads())
                                   },
                                   system_info={
                                       'python_version': platform.python_version(),
                                       'platform': platform.platform(),
                                       'processor': platform.processor()
                                   })
            logger.error("Internal Server Error",
                          error_id=error_data.get('id'),
                          error_type="INTERNAL_SERVER_ERROR",
                          traceback=error_data.get('traceback'))
            return render_template('errors/500.html', error=error_data), 500

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            error_data = log_error(e, error_type="CSRF_ERROR", include_trace=True,
                                   security_info={
                                       'token_present': bool(request.form.get('csrf_token')),
                                       'referrer': request.referrer,
                                       'origin': request.headers.get('Origin'),
                                       'request_method': request.method,
                                       'content_type': request.content_type
                                   })
            logger.warning("CSRF Validation Failed", error_id=error_data.get('id'))
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_unhandled_error(error):
            error_data = log_error(error, error_type="UNHANDLED_EXCEPTION", include_trace=True,
                                   system_info={
                                       'python_version': platform.python_version(),
                                       'os': platform.system(),
                                       'memory_usage': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
                                       'cpu_percent': psutil.Process().cpu_percent(),
                                       'open_files': len(psutil.Process().open_files()),
                                       'connections': len(psutil.Process().connections())
                                   })
            db.session.rollback()
            logger.critical("Unhandled Exception",
                             error_id=error_data.get('id'),
                             error_type=error.__class__.__name__,
                             traceback=error_data.get('traceback'))
            return render_template('errors/500.html', error=error_data), 500

        # Register request handlers
        @app.before_request
        def before_request():
            g.request_start_time = datetime.utcnow()
            logger.info(f"Incoming request: {request.method} {request.path}",
                         client_info={
                             'ip': request.remote_addr,
                             'user_agent': str(request.user_agent),
                             'path': request.path,
                             'method': request.method
                         })

        @app.after_request
        def after_request(response):
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                logger.info(f"Request completed: {request.path}",
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
            error_data = log_error(e, error_type="BLUEPRINT_REGISTRATION_ERROR")
            logger.error("Failed to register blueprints", error_id=error_data.get('id'))
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
                logger.error("Failed to create database tables", error_id=error_data.get('id'))
                raise

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        error_data = log_error(e, error_type="APP_INITIALIZATION_ERROR")
        logger.critical("Failed to initialize application", error_id=error_data.get('id'))
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)