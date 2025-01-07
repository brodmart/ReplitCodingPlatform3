import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from flask_wtf.csrf import CSRFError

# Configure logging from file
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('app')

def create_app():
    """Create and configure the Flask application"""
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

    try:
        # Initialize database
        logger.debug("Initializing database...")
        from database import init_db, db
        init_db(app)
        logger.debug("Database initialized successfully")

        # Initialize extensions
        logger.debug("Initializing extensions...")
        from extensions import init_extensions
        init_extensions(app)
        logger.debug("Extensions initialized successfully")

        # Enable CORS
        logger.debug("Configuring CORS...")
        CORS(app)
        logger.debug("CORS configured successfully")

        # Register blueprints with debug logging
        logger.debug("Starting blueprint registration...")

        try:
            from routes.auth_routes import auth
            app.register_blueprint(auth)
            logger.debug("Registered auth blueprint with prefix: /auth")
        except Exception as e:
            logger.error(f"Failed to register auth blueprint: {str(e)}", exc_info=True)
            raise

        try:
            from routes.activity_routes import activities
            app.register_blueprint(activities, url_prefix='/activities')
            logger.debug("Registered activities blueprint with prefix: /activities")
        except Exception as e:
            logger.error(f"Failed to register activities blueprint: {str(e)}", exc_info=True)
            raise

        try:
            from routes.tutorial import tutorial_bp
            app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
            logger.debug("Registered tutorial blueprint with prefix: /tutorial")
        except Exception as e:
            logger.error(f"Failed to register tutorial blueprint: {str(e)}", exc_info=True)
            raise

        # Log all registered routes for debugging
        logger.debug("Registered routes:")
        for rule in app.url_map.iter_rules():
            logger.debug(f"Route: {rule.rule} [{', '.join(rule.methods)}] -> {rule.endpoint}")

        @app.before_request
        def before_request():
            g.request_start_time = datetime.utcnow()
            logger.debug(f"Incoming request: {request.method} {request.path}")

        @app.after_request
        def after_request(response):
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                logger.debug(f"Request completed: {request.path} -> {response.status_code} in {duration.total_seconds():.3f}s")
            return response

        @app.route('/')
        def index():
            try:
                language = request.args.get('language', 'cpp')
                templates = {
                    'cpp': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
                    'csharp': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}'
                }

                if 'lang' not in session:
                    session['lang'] = 'fr'

                return render_template('index.html',
                                   lang=session.get('lang', 'fr'),
                                   language=language,
                                   templates=templates)
            except Exception as e:
                logger.error(f"Error rendering index: {str(e)}", exc_info=True)
                return render_template('errors/500.html'), 500

        @app.errorhandler(404)
        def not_found_error(error):
            logger.warning(f"404 error: {request.url}")
            return render_template('errors/404.html'), 404

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            logger.error(f"CSRF error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled error: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': "Une erreur inattendue s'est produite"
            }), 500

        # Create database tables
        with app.app_context():
            import models
            db.create_all()
            logger.info("Database tables created successfully")

        logger.info("Application initialization completed successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)