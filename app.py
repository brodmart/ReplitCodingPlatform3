import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g
from flask_cors import CORS
from flask_wtf.csrf import CSRFError

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

    # Setup basic logging
    logging.basicConfig(level=logging.DEBUG)

    # Initialize database
    from database import init_db, db
    init_db(app)

    # Initialize extensions
    from extensions import init_extensions
    init_extensions(app)

    # Enable CORS
    CORS(app, resources={
        r"/activities/*": {
            "origins": "*",
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "X-CSRF-Token"]
        }
    })

    # Register blueprints
    from routes.activity_routes import activities
    from routes.tutorial import tutorial_bp
    from routes.auth_routes import auth

    app.register_blueprint(activities, url_prefix='/activities')
    app.register_blueprint(tutorial_bp, url_prefix='/tutorial')
    app.register_blueprint(auth, url_prefix='/auth')

    @app.before_request
    def before_request():
        g.request_start_time = datetime.utcnow()
        app.logger.info(f"Request: {request.method} {request.path}")

    @app.after_request
    def after_request(response):
        if hasattr(g, 'request_start_time'):
            duration = datetime.utcnow() - g.request_start_time
            app.logger.info(f"Response: {response.status_code} in {duration.total_seconds():.3f}s")
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
            app.logger.error(f"Error rendering index: {str(e)}")
            return render_template('errors/500.html'), 500

    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 error: {request.url}")
        return render_template('errors/404.html'), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.error(f"CSRF error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Token de sécurité invalide. Veuillez rafraîchir la page.'
        }), 400

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled error: {str(e)}")
        return jsonify({
            'success': False,
            'error': "Une erreur inattendue s'est produite"
        }), 500

    # Create database tables
    with app.app_context():
        import models
        db.create_all()
        app.logger.info("Database tables created")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)