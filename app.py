import os
import logging
from flask import Flask, session, request, render_template
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS
from compiler_service import compile_and_run, send_input, get_output, cleanup_session
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask and extensions
app = Flask(__name__)
app.config.update({
    'SECRET_KEY': os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only"),
    'SESSION_TYPE': 'filesystem',
    'JSON_SORT_KEYS': False,
})

# Initialize extensions
Session(app)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, ping_timeout=60)

@app.route('/')
def index():
    """Render the main activity page with console"""
    return render_template('activity.html')

@app.route('/console')
def console():
    """Alternative route for console page"""
    return render_template('activity.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    session['sid'] = request.sid
    emit('connection_established', {'status': 'connected', 'sid': request.sid})
    logger.debug(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if 'console_session_id' in session:
        cleanup_session(session['console_session_id'])
        logger.debug(f"Cleaned up session: {session['console_session_id']}")
    session.clear()
    logger.debug(f"Client disconnected: {request.sid}")

@socketio.on('compile_and_run')
def handle_compile_and_run(data):
    """Handle code compilation and execution"""
    if not data or 'code' not in data:
        emit('error', {'message': 'No code provided'})
        return

    try:
        result = compile_and_run(data['code'], 'csharp')
        logger.debug(f"Compilation result: {result}")

        if result.get('success'):
            session_id = result.get('session_id')
            if session_id:
                session['console_session_id'] = session_id
                emit('compilation_success', {
                    'session_id': session_id
                })

                # Initial output check
                output = get_output(session_id)
                logger.debug(f"Initial output: {output}")
                if output and output.get('success'):
                    emit('output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })
                    logger.debug("Emitted initial output to client")
            else:
                emit('error', {'message': 'Failed to create interactive session'})
        else:
            emit('compilation_error', {
                'error': result.get('error', 'Compilation failed')
            })

    except Exception as e:
        logger.error(f"Compilation error: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('input')
def handle_input(data):
    """Handle console input"""
    session_id = session.get('console_session_id')
    input_text = data.get('input')

    if not session_id or not input_text:
        emit('error', {'message': 'Invalid session or input'})
        return

    try:
        logger.debug(f"Sending input: {input_text} to session {session_id}")
        # Send input with newline
        result = send_input(session_id, input_text + '\n')
        logger.debug(f"Send input result: {result}")

        if result and result.get('success'):
            # Get program output after input
            output = get_output(session_id)
            logger.debug(f"Program output after input: {output}")

            # Keep checking for output until we get a response or timeout
            retry_count = 0
            max_retries = 5
            while (not output.get('output') and not output.get('error', '').startswith('Session not active') and retry_count < max_retries):
                time.sleep(0.1)  # Add a small delay between retries
                output = get_output(session_id)
                logger.debug(f"Retry {retry_count + 1}, output: {output}")
                if output.get('output'):
                    break
                retry_count += 1

            if output and output.get('success'):
                emit('output', {
                    'output': output.get('output', ''),
                    'waiting_for_input': output.get('waiting_for_input', False)
                })
                logger.debug(f"Emitted output to client after input: {output.get('output')}")
            else:
                emit('error', {'message': 'Failed to get program output'})
        else:
            emit('error', {'message': 'Failed to send input'})

    except Exception as e:
        logger.error(f"Input handling error: {str(e)}")
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)