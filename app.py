import os
import logging
import uuid
from flask import Flask, session, request, render_template
from flask_socketio import SocketIO, emit
from flask_session import Session
from flask_cors import CORS
from compiler_service import compile_and_run, send_input, get_output, cleanup_session

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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True)

@app.route('/')
def console():
    """Render the interactive console page"""
    return render_template('console.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    session['sid'] = request.sid
    emit('connection_established', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection with cleanup"""
    logger.info(f"Client disconnected: {request.sid}")
    if 'console_session_id' in session:
        cleanup_session(session['console_session_id'])
    session.clear()

@socketio.on('compile_and_run')
def handle_compile_and_run(data):
    """Handle code compilation and execution"""
    try:
        code = data.get('code')
        if not code:
            emit('error', {'message': 'No code provided'})
            return

        # Start compilation process
        result = compile_and_run(code, 'csharp')

        if result.get('success'):
            session_id = result.get('session_id')
            if session_id:
                session['console_session_id'] = session_id
                emit('compilation_result', {
                    'success': True,
                    'session_id': session_id,
                    'interactive': True
                })

                # Get initial output after short delay
                import time
                time.sleep(0.5)

                output = get_output(session_id)
                if output and output.get('success'):
                    emit('output', {
                        'output': output.get('output', ''),
                        'waiting_for_input': True
                    })
            else:
                emit('error', {'message': 'Failed to create interactive session'})
        else:
            emit('compilation_result', {
                'success': False,
                'error': result.get('error', 'Compilation failed')
            })

    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        emit('error', {'message': f'Failed to compile and run: {str(e)}'})

@socketio.on('input')
def handle_input(data):
    """Handle console input"""
    try:
        session_id = session.get('console_session_id')
        input_text = data.get('input')

        if not session_id or not input_text:
            emit('error', {'message': 'Invalid input data'})
            return

        result = send_input(session_id, input_text + '\n')

        if result and result.get('success'):
            time.sleep(0.1)
            output = get_output(session_id)

            if output and output.get('success'):
                emit('console_output', {
                    'output': output.get('output', ''),
                    'waiting_for_input': output.get('waiting_for_input', False)
                })
            else:
                emit('error', {'message': 'Failed to get program output'})
        else:
            emit('error', {'message': 'Failed to send input'})

    except Exception as e:
        logger.error(f"Error in handle_input: {str(e)}")
        emit('error', {'message': f'Failed to process input: {str(e)}'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)