import os
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO
from compiler_service import compile_and_run, send_input, get_output, cleanup_session

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only")
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    """Render the main activity page"""
    return render_template('activity.html')

@socketio.on('compile_and_run')
def handle_compile_and_run(data):
    """Handle code compilation and execution"""
    if not data or 'code' not in data:
        socketio.emit('error', {'message': 'No code provided'})
        return

    try:
        result = compile_and_run(data['code'], 'csharp')
        if result.get('success'):
            session_id = result.get('session_id')
            if session_id:
                socketio.emit('compilation_success')
                output = get_output(session_id)
                if output and output.get('success'):
                    socketio.emit('output', {
                        'session_id': session_id,
                        'output': output.get('output', ''),
                        'waiting_for_input': output.get('waiting_for_input', False)
                    })
            else:
                socketio.emit('error', {'message': 'Failed to create session'})
        else:
            socketio.emit('compilation_error', {'error': result.get('error', 'Compilation failed')})
    except Exception as e:
        logger.error(f"Compilation error: {str(e)}")
        socketio.emit('error', {'message': str(e)})

@socketio.on('input')
def handle_input(data):
    """Handle console input"""
    session_id = data.get('session_id')
    input_text = data.get('input')

    if not session_id or not input_text:
        socketio.emit('error', {'message': 'Invalid session or input'})
        return

    try:
        result = send_input(session_id, input_text + '\n')
        if result and result.get('success'):
            output = get_output(session_id)
            if output and output.get('success'):
                socketio.emit('output', {
                    'session_id': session_id,
                    'output': output.get('output', ''),
                    'waiting_for_input': output.get('waiting_for_input', False)
                })
            else:
                socketio.emit('error', {'message': 'Failed to get output'})
        else:
            socketio.emit('error', {'message': 'Failed to send input'})
    except Exception as e:
        logger.error(f"Input handling error: {str(e)}")
        socketio.emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)