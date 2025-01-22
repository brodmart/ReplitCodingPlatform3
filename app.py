import os
import logging
import uuid
import time
from flask import Flask, session, request, render_template
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_wtf.csrf import CSRFProtect
from compiler_service import compile_and_run, send_input, get_output, cleanup_session
from utils.compiler_logger import compiler_logger

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Socket.IO with enhanced configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    async_handlers=True
)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Enhanced configuration
    app.config.update({
        'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
        'SESSION_TYPE': 'filesystem',
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': True,
        'JSON_SORT_KEYS': False,
        'SOCKET_TIMEOUT': 60,
        'MAX_CONTENT_LENGTH': 100 * 1024 * 1024  # 100MB max content
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

        @app.context_processor
        def inject_language():
            return {'lang': session.get('lang', 'en')}

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
    """Setup WebSocket event handlers for console I/O with improved error handling"""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection with enhanced session management"""
        logger.info(f"Client connected: {request.sid}")
        session['sid'] = request.sid
        emit('connection_established', {'status': 'connected', 'sid': request.sid})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection with cleanup"""
        logger.info(f"Client disconnected: {request.sid}")
        if 'console_session_id' in session:
            try:
                # Clean up any running console session
                cleanup_session(session['console_session_id'])
            except Exception as e:
                logger.error(f"Error cleaning up session: {e}")
        session.clear()

    @socketio.on('compile_and_run')
    def handle_compile_and_run(data):
        """Handle code compilation and execution with improved error handling"""
        try:
            code = data.get('code')
            language = data.get('language', 'csharp')  # Default to C#

            if not code:
                logger.error("No code provided")
                emit('error', {'message': 'No code provided'})
                return

            logger.info(f"Starting {language} code compilation")
            logger.debug(f"Code to compile: {code}")

            # Generate unique session ID for tracking
            compilation_session_id = str(uuid.uuid4())
            logger.info(f"Created compilation session ID: {compilation_session_id}")

            # Log start of compilation
            compiler_logger.log_compilation_start(compilation_session_id, code)

            # Emit compilation start event
            emit('compilation_start', {
                'session_id': compilation_session_id,
                'timestamp': time.time()
            })

            # Attempt compilation with timeout handling
            result = compile_and_run(code, language, session_id=compilation_session_id)
            logger.info(f"Compilation result: {result}")

            if result.get('success'):
                session_id = result.get('session_id')
                if session_id:
                    # Store session ID and emit success
                    session['console_session_id'] = session_id
                    logger.info(f"Compilation successful, session_id: {session_id}")
                    emit('compilation_result', {
                        'success': True,
                        'session_id': session_id,
                        'interactive': result.get('interactive', False)
                    })

                    # Get and emit initial output
                    try:
                        output = get_output(session_id)
                        if output and output.get('success'):
                            logger.info(f"Initial output: {output.get('output', '')}")
                            emit('console_output', {
                                'output': output.get('output', ''),
                                'waiting_for_input': output.get('waiting_for_input', False)
                            })
                        else:
                            logger.warning(f"No initial output available: {output}")
                    except Exception as e:
                        logger.error(f"Error getting initial output: {e}")
                        emit('error', {'message': 'Failed to get initial program output'})
                else:
                    logger.error("No session ID in successful compilation result")
                    emit('error', {'message': 'Compilation succeeded but no session created'})
            else:
                error = result.get('error', 'Compilation failed')
                logger.error(f"Compilation failed: {error}")
                emit('compilation_result', {
                    'success': False,
                    'error': error
                })

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {'message': f'Failed to compile and run: {str(e)}'})

    @socketio.on('input')
    def handle_input(data):
        """Handle console input from client with improved error recovery"""
        try:
            session_id = session.get('console_session_id')
            input_text = data.get('input')

            if not session_id or not input_text:
                logger.error(f"Invalid input data - session_id: {session_id}, input: {input_text}")
                emit('error', {'message': 'Invalid input data'})
                return

            logger.debug(f"Sending input '{input_text}' to session {session_id}")
            result = send_input(session_id, input_text + '\n')
            logger.debug(f"Send input result: {result}")

            if result and result.get('success'):
                # Wait briefly for output processing
                import time
                time.sleep(0.1)

                output = get_output(session_id)
                logger.debug(f"Get output after input result: {output}")
                if output and output.get('success'):
                    emit('console_output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })
                else:
                    logger.error(f"Failed to get output after input: {output}")
                    emit('error', {'message': 'Failed to get program output'})
            else:
                logger.error(f"Failed to send input: {result}")
                emit('error', {'message': 'Failed to send input'})

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {'message': f'Failed to process input: {str(e)}'})

    @socketio.on_error()
    def handle_error(e):
        """Global error handler for all namespaces"""
        logger.error(f"Socket.IO error: {str(e)}", exc_info=True)
        emit('error', {'message': 'An unexpected error occurred'})

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)