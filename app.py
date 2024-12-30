import os
import logging
from flask import Flask, render_template, request, jsonify
from compiler_service import compile_and_run

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/execute', methods=['POST'])
def execute():
    try:
        code = request.json.get('code', '')
        language = request.json.get('language', 'cpp')
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
            
        result = compile_and_run(code, language)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Execution error: {str(e)}")
        return jsonify({'error': str(e)}), 500
