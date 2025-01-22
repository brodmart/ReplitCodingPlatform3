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
from utils.compiler_logger import CompilerLogger
from utils.logging_config import setup_logging
from utils.socketio_logger import log_socket_event, track_connection, track_session, log_error

# Initialize loggers
logger = setup_logging('app')
socketio_logger = setup_logging('socketio')
compiler_logger = CompilerLogger()
db_logger = setup_logging('database')

# Try to use Redis for message queue, fall back to in-memory if Redis is not available
message_queue = 'redis://'
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
    redis_client.ping()
except (redis.ConnectionError, redis.TimeoutError):
    logger.warning("Redis not available, falling back to in-memory queue")
    message_queue = None

# Initialize Socket.IO with enhanced configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    async_handlers=True,
    message_queue=message_queue,
    always_connect=True
)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()

def create_app():
    """Create and configure the Flask application with enhanced logging"""
    logger.info("Initializing Flask application")
    app = Flask(__name__)

    # Enhanced configuration with logging
    try:
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
        logger.debug("Application configuration loaded")

        # Initialize extensions with error tracking
        try:
            db.init_app(app)
            logger.info("Database initialized")
        except Exception as e:
            logger.error("Database initialization failed", exc_info=True)
            raise

        try:
            socketio.init_app(app)
            logger.info("Socket.IO initialized")
        except Exception as e:
            logger.error("Socket.IO initialization failed", exc_info=True)
            raise

        try:
            CORS(app)
            Session(app)
            csrf.init_app(app)
            logger.info("CORS, Session, and CSRF protection initialized")
        except Exception as e:
            logger.error("Extension initialization failed", exc_info=True)
            raise

        with app.app_context():
            db.create_all()
            logger.info("Database tables created")

        @app.context_processor
        def inject_language():
            return {'lang': session.get('lang', 'en')}

        @app.route('/')
        def console():
            """Render the interactive console page"""
            logger.debug("Rendering console page")
            return render_template('console.html')

        # Register Socket.IO event handlers with enhanced logging
        setup_websocket_handlers()

        logger.info("Application initialized successfully")
        return app

    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

def setup_websocket_handlers():
    """Setup WebSocket event handlers with comprehensive logging and error handling"""

    @socketio.on('connect')
    @log_socket_event
    def handle_connect(auth=None):
        """Handle client connection with enhanced session management and logging"""
        client_info = {
            'sid': request.sid,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
        logger.info(f"Client connected: {request.sid}")
        session['sid'] = request.sid
        track_connection(True, client_info)
        emit('connection_established', {'status': 'connected', 'sid': request.sid})

    @socketio.on('disconnect')
    @log_socket_event
    def handle_disconnect(auth=None):
        """Handle client disconnection with cleanup and logging"""
        logger.info(f"Client disconnected: {request.sid}")
        if 'console_session_id' in session:
            try:
                cleanup_session(session['console_session_id'])
                logger.debug(f"Cleaned up session: {session['console_session_id']}")
            except Exception as e:
                log_error("cleanup_error", f"Error cleaning up session: {e}")
        track_connection(False)
        session.clear()

    @socketio.on('compile_and_run')
    @log_socket_event
    def handle_compile_and_run(data):
        """Handle code compilation and execution with comprehensive logging"""
        try:
            code = data.get('code')
            language = data.get('language', 'csharp')

            if not code:
                logger.error("No code provided")
                emit('error', {'message': 'No code provided'})
                return

            logger.info(f"Starting {language} code compilation")
            logger.debug(f"Code to compile: {code}")

            # Generate unique session ID and log start
            compilation_session_id = str(uuid.uuid4())
            compiler_logger.info(f"Created compilation session ID: {compilation_session_id}")

            # Track compilation metrics with extended timeout
            start_time = time.time()
            compiler_logger.log_compilation_start(compilation_session_id, code)

            # Emit start event with session ID
            emit('compilation_start', {
                'session_id': compilation_session_id,
                'timestamp': start_time
            })

            # Attempt compilation with extended timeout handling
            result = compile_and_run(code, language, session_id=compilation_session_id)
            duration = time.time() - start_time
            logger.info(f"Compilation completed in {duration:.2f}s: {result}")

            if result.get('success'):
                session_id = result.get('session_id')
                if session_id:
                    session['console_session_id'] = session_id
                    track_session(session_id, True, {
                        'language': language,
                        'compilation_time': duration
                    })
                    emit('compilation_result', {
                        'success': True,
                        'session_id': session_id,
                        'interactive': result.get('interactive', False),
                        'metrics': {
                            'compilation_time': duration
                        }
                    })

                    # Get and emit initial output with error handling
                    try:
                        output = get_output(session_id)
                        if output and output.get('success'):
                            logger.debug(f"Initial output: {output}")
                            emit('console_output', {
                                'output': output.get('output', ''),
                                'waiting_for_input': output.get('waiting_for_input', False)
                            })
                        else:
                            logger.warning(f"No initial output available: {output}")
                            emit('error', {'message': 'No initial output available'})
                    except Exception as e:
                        log_error("output_error", f"Error getting initial output: {e}")
                        emit('error', {'message': 'Failed to get initial program output'})
                else:
                    log_error("session_error", "No session ID in successful compilation result")
                    emit('error', {'message': 'Compilation succeeded but no session created'})
            else:
                error = result.get('error', 'Compilation failed')
                log_error("compilation_error", f"Compilation failed: {error}")
                emit('compilation_result', {
                    'success': False,
                    'error': error,
                    'metrics': {
                        'compilation_time': duration
                    }
                })

        except Exception as e:
            log_error("compilation_error", f"Error in compile_and_run: {str(e)}")
            emit('error', {'message': f'Failed to compile and run: {str(e)}'})
            raise

    @socketio.on('input')
    @log_socket_event
    def handle_input(data):
        """Handle console input with comprehensive logging"""
        try:
            session_id = session.get('console_session_id')
            input_text = data.get('input')

            if not session_id or not input_text:
                log_error("input_error", f"Invalid input data - session_id: {session_id}, input: {input_text}")
                emit('error', {'message': 'Invalid input data'})
                return

            logger.debug(f"Sending input '{input_text}' to session {session_id}")
            result = send_input(session_id, input_text + '\n')
            logger.debug(f"Send input result: {result}")

            if result and result.get('success'):
                time.sleep(0.1)  # Brief delay for output processing
                output = get_output(session_id)
                logger.debug(f"Get output after input result: {output}")

                if output and output.get('success'):
                    emit('console_output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })
                else:
                    log_error("output_error", f"Failed to get output after input: {output}")
                    emit('error', {'message': 'Failed to get program output'})
            else:
                log_error("input_error", f"Failed to send input: {result}")
                emit('error', {'message': 'Failed to send input'})

        except Exception as e:
            log_error("input_error", f"Error in handle_input: {str(e)}")
            emit('error', {'message': f'Failed to process input: {str(e)}'})

    @socketio.on_error()
    def handle_error(e):
        """Global error handler with comprehensive logging"""
        log_error("socketio_error", f"Socket.IO error: {str(e)}")
        emit('error', {'message': 'An unexpected error occurred'})

app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)