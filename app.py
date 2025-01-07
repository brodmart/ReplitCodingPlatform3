import os
import logging
from flask import Flask, render_template, request, session, jsonify
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
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
        }
    )

    # Setup logging first
    setup_logging(app)
    logger = logging.getLogger('app')

    try:
        # Initialize database
        logger.info("Initializing database...")
        db.init_app(app)

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

        # Register error handlers
        @app.errorhandler(400)
        def bad_request_error(error):
            logger.error(f"Bad Request Error: {error}")
            return jsonify({"error": "Bad Request", "message": str(error)}), 400

        @app.errorhandler(401)
        def unauthorized_error(error):
            logger.error(f"Unauthorized Error: {error}")
            return jsonify({"error": "Unauthorized", "message": str(error)}), 401

        @app.errorhandler(403)
        def forbidden_error(error):
            logger.error(f"Forbidden Error: {error}")
            return jsonify({"error": "Forbidden", "message": str(error)}), 403

        @app.errorhandler(404)
        def not_found_error(error):
            logger.error(f"Not Found Error: {error}")
            return jsonify({"error": "Not Found", "message": str(error)}), 404

        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal Server Error: {error}")
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": "Une erreur interne est survenue"}), 500

        @app.errorhandler(Exception)
        def handle_unhandled_error(error):
            logger.error(f"Unhandled Exception: {error}", exc_info=True)
            db.session.rollback()
            return jsonify({"error": "Internal Server Error", "message": "Une erreur inattendue est survenue"}), 500

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

        # Add static pages routes
        @app.route('/')
        def index():
            if 'lang' not in session:
                session['lang'] = 'fr'
            return render_template('index.html', lang=session.get('lang', 'fr'))

        @app.route('/about')
        def about():
            return render_template('about.html', lang=session.get('lang', 'fr'))

        @app.route('/contact')
        def contact():
            return render_template('contact.html', lang=session.get('lang', 'fr'))

        @app.route('/faq')
        def faq():
            return render_template('faq.html', lang=session.get('lang', 'fr'))

        @app.route('/terms')
        def terms():
            return render_template('terms.html', lang=session.get('lang', 'fr'))

        @app.route('/privacy')
        def privacy():
            return render_template('privacy.html', lang=session.get('lang', 'fr'))

        @app.route('/accessibility')
        def accessibility():
            return render_template('accessibility.html', lang=session.get('lang', 'fr'))

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)