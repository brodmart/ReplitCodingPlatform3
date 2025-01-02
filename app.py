import os
import logging
import secrets
import time
from flask import Flask, render_template, request, jsonify, session, g, flash, send_from_directory, redirect, url_for
from flask_cors import CORS
from database import init_db, db
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_migrate import Migrate
from extensions import init_extensions
from routes.activity_routes import activities
from routes.tutorial import tutorial_bp

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Define default templates for each language
TEMPLATES = {
    'cpp': """#include <iostream>
#include <string>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}""",
    'csharp': """using System;

class Program {
    static void Main() {
        // Votre code ici
    }
}"""
}

def create_app():
    """Create and configure the Flask application"""
    try:
        logger.info("Starting application creation...")
        app = Flask(__name__)

        # Configure security and session settings
        app.config.update(
            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32)),
            SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TEMPLATES_AUTO_RELOAD=True,
            SEND_FILE_MAX_AGE_DEFAULT=0,
            DEBUG=True,
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_TIME_LIMIT=3600,
            WTF_CSRF_SSL_STRICT=False,
            RATELIMIT_DEFAULT="200 per day",
            RATELIMIT_STORAGE_URL="memory://",
            RATELIMIT_HEADERS_ENABLED=True,
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        )
        logger.info("Application configuration completed")

        # Initialize database
        logger.info("Initializing database...")
        init_db(app)
        logger.info("Database initialization completed")

        # Initialize CSRF protection
        csrf = CSRFProtect()
        csrf.init_app(app)
        logger.info("CSRF protection initialized")

        # Initialize migrations
        migrate = Migrate(app, db)
        logger.info("Database migrations initialized")

        # Initialize extensions with db instance
        init_extensions(app, db)
        logger.info("Extensions initialized")

        # Enable CORS with specific origins
        CORS(app, resources={
            r"/activities/*": {"origins": "*"}
        })
        logger.info("CORS configured")

        # Register blueprints
        logger.info("Registering blueprints...")
        app.register_blueprint(activities, url_prefix='/activities')
        app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
        logger.info("Blueprints registered successfully")

        @app.route('/')
        def index():
            """Main editor page - accessible without authentication"""
            try:
                logger.debug("Accessing index route")
                lang = session.get('lang', 'fr')
                language = request.args.get('language', 'cpp').lower()

                if language not in TEMPLATES:
                    language = 'cpp'

                logger.info(f"Rendering editor template with language: {language}")
                return render_template(
                    'editor.html',
                    lang=lang,
                    language=language,
                    templates=TEMPLATES
                )
            except Exception as e:
                logger.error(f"Error in index route: {str(e)}", exc_info=True)
                return render_template('errors/500.html', lang=session.get('lang', 'fr')), 500

        @app.route('/grade/<grade>')
        def redirect_to_activities(grade):
            """Redirect to activities list"""
            return redirect(url_for('activities.list_activities', grade=grade))

        @app.before_request
        def before_request():
            """Log request information and set up request context"""
            g.start_time = time.time()
            if 'lang' not in session:
                session['lang'] = 'fr'
            logger.debug(f"Processing request: {request.endpoint}")

        @app.after_request
        def after_request(response):
            """Add response headers and log response time"""
            if hasattr(g, 'start_time'):
                elapsed = time.time() - g.start_time
                response.headers['X-Response-Time'] = str(elapsed)
                logger.debug(f"Request processed in {elapsed:.3f}s")

            if app.debug:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'

            return response

        @app.teardown_appcontext
        def shutdown_session(exception=None):
            """Clean up database session"""
            if exception:
                logger.error(f"Error during request: {str(exception)}")
            db.session.remove()

        logger.info("Application creation completed successfully")
        return app
    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}", exc_info=True)
        raise

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    logger.info("Starting development server...")
    app.run(host='0.0.0.0', port=8080, debug=True)