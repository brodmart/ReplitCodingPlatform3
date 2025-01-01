from app import app, logger
from routes import blueprints

def init_app():
    """Initialize the application"""
    try:
        # Only import models and create tables
        with app.app_context():
            from models import db
            db.create_all()

        # Register all blueprints
        for blueprint in blueprints:
            app.register_blueprint(blueprint)
            logger.info(f"Registered blueprint: {blueprint.name}")

        return app
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

if __name__ == '__main__':
    app = init_app()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)