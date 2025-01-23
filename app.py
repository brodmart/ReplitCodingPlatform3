# Eventlet monkey patch must be the first import
import eventlet
eventlet.monkey_patch()

import os
import logging
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from flask_wtf.csrf import CSRFProtect
from compiler_simple import compile_and_run

# Basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
csrf = CSRFProtect(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'success'})

@socketio.on('compile_and_run')
def handle_compile_and_run(data):
    try:
        code = data.get('code', '')
        if not code:
            emit('output', {'success': False, 'error': 'No code provided'})
            return

        # Send immediate feedback
        emit('output', {
            'success': True,
            'output': 'Compiling and running code...\n',
            'waiting_for_input': False
        })

        # Compile and run
        result = compile_and_run(code)

        if result['success']:
            emit('output', {
                'success': True,
                'output': result['output'],
                'waiting_for_input': False
            })
        else:
            emit('output', {
                'success': False, 
                'error': result['error']
            })

    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        emit('output', {
            'success': False,
            'error': f"Server error: {str(e)}"
        })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)