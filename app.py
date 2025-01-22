import os
import logging
from flask import Flask, session, request, render_template, g
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_wtf.csrf import CSRFProtect

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Socket.IO with minimal configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True
)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Basic configuration
    app.config.update({
        'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
        'SESSION_TYPE': 'filesystem',
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': True,
        'JSON_SORT_KEYS': False  # Preserve output order
    })

    try:
        # Initialize extensions
        db.init_app(app)
        socketio.init_app(app)
        CORS(app)
        Session(app)
        csrf.init_app(app)

        with app.app_context():
            db.create_all()

        # Add context processor for language
        @app.context_processor
        def inject_language():
            return {'lang': session.get('lang', 'en')}

        # Add console route
        @app.route('/')
        def console():
            """Render the interactive console page"""
            return render_template('console.html')

        # Register Socket.IO event handlers
        setup_websocket_handlers()

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

def setup_websocket_handlers():
    """Setup WebSocket event handlers for console I/O"""
    from compiler_service import compile_and_run, send_input, get_output
    from utils.socketio_logger import log_socket_event, track_connection, track_session

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        logger.info(f"Client connected: {request.sid}")
        session['sid'] = request.sid
        track_connection(True)
        emit('connection_established', {'status': 'connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        logger.info(f"Client disconnected: {request.sid}")
        if 'console_session_id' in session:
            track_session(session['console_session_id'], False)
        session.pop('console_session_id', None)
        session.pop('sid', None)
        track_connection(False)

    @socketio.on('compile_and_run')
    def handle_compile_and_run(data):
        """Handle code compilation and execution"""
        try:
            code = data.get('code')
            if not code:
                emit('error', {'message': 'No code provided'})
                return

            logger.info("Compiling and running C# code...")
            result = compile_and_run(code, 'csharp')

            if result.get('success'):
                session_id = result.get('session_id')
                if session_id:
                    session['console_session_id'] = session_id
                    track_session(session_id, True)
                    emit('compilation_result', {
                        'success': True,
                        'session_id': session_id,
                        'interactive': result.get('interactive', False)
                    })

                    # For interactive programs, get initial output
                    if result.get('interactive'):
                        output = get_output(session_id)
                        if output and output.get('success'):
                            emit('output', {
                                'output': output.get('output', ''),
                                'waiting_for_input': output.get('waiting_for_input', False)
                            })
            else:
                emit('compilation_result', {
                    'success': False,
                    'error': result.get('error', 'Compilation failed')
                })

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {'message': f'Failed to compile and run: {str(e)}'})

    @socketio.on('input')
    def handle_input(data):
        """Handle console input from client"""
        try:
            session_id = session.get('console_session_id')
            input_text = data.get('input')

            if not session_id or not input_text:
                emit('error', {'message': 'Invalid input data'})
                return

            result = send_input(session_id, input_text)
            if result and result.get('success'):
                output = get_output(session_id)
                if output and output.get('success'):
                    emit('output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })
            else:
                emit('error', {'message': 'Failed to send input'})

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {'message': f'Failed to process input: {str(e)}'})

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)