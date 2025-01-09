import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db, check_db_connection
from models import Student

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Create Flask app
def create_app():
            """Create and configure the Flask application"""
            app = Flask(__name__, 
                        static_url_path='',
                        static_folder='static',
                        template_folder='templates')

            # Basic configuration
            app.config.update(
                SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
                SESSION_TYPE='filesystem',
                SESSION_FILE_DIR=os.path.join(os.getcwd(), 'flask_session'),  # Ensure this directory exists
                SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/codecrafthub'),
                SQLALCHEMY_TRACK_MODIFICATIONS=False
            )

            try:
                # Create session directory if it does not exist
                os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

                # Initialize extensions in order
                db.init_app(app)
                csrf = CSRFProtect(app)
                Session(app)  # No additional arguments for the MemoryStorage should be added here
                CORS(app)

                # Initialize other components...

                # Register blueprints
                from routes.auth_routes import auth
                from routes.activity_routes import activities
                from routes.tutorial import tutorial_bp

                app.register_blueprint(auth)
                app.register_blueprint(activities)
                app.register_blueprint(tutorial_bp)

                # Register error handlers
                @app.errorhandler(404)
                def not_found_error(error):
                    return render_template('errors/404.html'), 404

                @app.errorhandler(500)
                def internal_error(error):
                    return render_template('errors/500.html'), 500

                logger.info("Application initialized successfully")
                return app
            except Exception as e:
                logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
                raise

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)