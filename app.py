import os
import logging
import secrets
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_compress import Compress
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize extensions
csrf = CSRFProtect()
compress = Compress()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")
        app = Flask(__name__)

        # Configure security and session settings
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
            TEMPLATES_AUTO_RELOAD=True,
            SEND_FILE_MAX_AGE_DEFAULT=0,
            DEBUG=True,  # Changed to True for debugging
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_TIME_LIMIT=3600,
            WTF_CSRF_SSL_STRICT=False,
            RATELIMIT_DEFAULT="200 per day",
            RATELIMIT_STORAGE_URL="memory://",
            RATELIMIT_HEADERS_ENABLED=True,
            JSON_AS_ASCII=False,
            JSONIFY_PRETTYPRINT_REGULAR=False,
            JSONIFY_MIMETYPE='application/json',
            # Add SQLAlchemy configuration
            SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        )

        # Initialize database first
        from database import init_db, db
        init_db(app)

        # Initialize extensions
        csrf.init_app(app)
        compress.init_app(app)
        migrate.init_app(app, db)
        limiter.init_app(app)

        # Enable CORS with specific origins
        CORS(app, resources={
            r"/activities/*": {
                "origins": "*",
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "X-CSRF-Token"],
                "methods": ["GET", "POST", "OPTIONS"]
            }
        })

        # Register blueprints
        from routes.activity_routes import activities
        from routes.tutorial import tutorial_bp
        from routes.auth_routes import auth

        app.register_blueprint(activities, url_prefix='/activities')
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        app.register_blueprint(auth, url_prefix='/auth')

        @app.route('/')
        def index():
            """Root route handler"""
            return render_template('editor.html', 
                                lang=session.get('lang', 'fr'),
                                templates={
                                    'cpp': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Votre code ici\n    return 0;\n}',
                                    'csharp': 'using System;\n\nclass Program {\n    static void Main() {\n        // Votre code ici\n    }\n}'
                                })

        # Routes for static pages
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

        @app.errorhandler(CSRFError)
        def handle_csrf_error(e):
            logger.error(f"CSRF error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
            }), 400

        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': "Une erreur inattendue s'est produite"
            }), 500

        # Create all database tables
        with app.app_context():
            # Import models here to avoid circular imports
            import models
            db.create_all()
            logger.info("Database tables created successfully")

        logger.info("Application creation completed successfully")
        return app

    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}", exc_info=True)
        raise

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting development server...")
    app.run(host='0.0.0.0', port=5000)  # Changed port to 5000