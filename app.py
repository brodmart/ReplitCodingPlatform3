import os
import logging
import logging.config
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from flask_wtf.csrf import CSRFError
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging from file
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('app')

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
            },
            # Rate limiter configuration
            RATELIMIT_STORAGE_URL="memory://",
            RATELIMIT_STRATEGY="fixed-window",
            RATELIMIT_DEFAULT="200 per day"
        )

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

        # Enable CORS with proper configuration
        logger.debug("Configuring CORS...")
        CORS(app, resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "X-CSRF-Token"]
            }
        })
        logger.debug("CORS configured successfully")

        # Handle proxy headers
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        # Register error handlers
        @app.errorhandler(404)
        def not_found_error(error):
            logger.warning(f"404 error: {request.url}")
            return render_template('errors/404.html'), 404

        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"500 error: {str(error)}", exc_info=True)
            db.session.rollback()
            return render_template('errors/500.html'), 500

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            logger.error(f"CSRF error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        # Register request handlers
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

        # Register blueprints
        try:
            logger.debug("Starting blueprint registration...")

            from routes.auth_routes import auth
            app.register_blueprint(auth)
            logger.debug("Registered auth blueprint")

            from routes.activity_routes import activities
            app.register_blueprint(activities, url_prefix='/activities')
            logger.debug("Registered activities blueprint")

            from routes.tutorial import tutorial_bp
            app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
            logger.debug("Registered tutorial blueprint")

        except Exception as e:
            logger.error(f"Failed to register blueprints: {str(e)}", exc_info=True)
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
                logger.error(f"Error rendering index: {str(e)}", exc_info=True)
                return render_template('errors/500.html'), 500

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