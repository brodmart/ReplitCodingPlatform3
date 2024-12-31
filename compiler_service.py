import subprocess
import tempfile
import os
import logging
from pathlib import Path
import re

def format_compiler_error(error_text):
    """Format compiler error messages to be more user-friendly"""
    if not error_text:
        return "Une erreur inconnue est survenue"

    # Extract the main error message
    error_lines = error_text.split('\n')
    main_error = None
    for line in error_lines:
        if 'error:' in line:
            # Extract line number and error message
            match = re.search(r'program\.cpp:(\d+):(\d+):\s*error:\s*(.+)', line)
            if match:
                line_num, col_num, message = match.groups()
                main_error = {
                    'line': int(line_num),
                    'column': int(col_num),
                    'message': message.strip(),
                    'type': 'error'
                }
                break

    if main_error:
        return {
            'error_details': main_error,
            'full_error': error_text,
            'formatted_message': f"Erreur ligne {main_error['line']}: {main_error['message']}"
        }
    return {
        'error_details': None,
        'full_error': error_text,
        'formatted_message': error_text.split('\n')[0] if error_text else "Erreur de compilation"
    }

def compile_and_run(code, language, input_data=None):
    with tempfile.TemporaryDirectory() as temp_dir:
        if language == 'cpp':
            return _compile_and_run_cpp(code, temp_dir, input_data)
        elif language == 'csharp':
            return _compile_and_run_csharp(code, temp_dir, input_data)
        else:
            raise ValueError(f"Unsupported language: {language}")

def _compile_and_run_cpp(code, temp_dir, input_data=None):
    source_file = Path(temp_dir) / "program.cpp"
    executable = Path(temp_dir) / "program"

    # Write source code to file
    with open(source_file, 'w') as f:
        f.write(code)

    try:
        # Compile
        compile_process = subprocess.run(
            ['g++', str(source_file), '-o', str(executable)],
            capture_output=True,
            text=True
        )

        if compile_process.returncode != 0:
            return {
                'success': False,
                'output': '',
                'error': compile_process.stderr
            }

        # Execute
        run_process = subprocess.run(
            [str(executable)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=5
        )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Execution timed out'
        }
    except Exception as e:
        logging.error(f"Compilation/execution error: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': str(e)
        }

def _compile_and_run_csharp(code, temp_dir, input_data=None):
    source_file = Path(temp_dir) / "program.cs"
    executable = Path(temp_dir) / "program.exe"

    # Write source code to file
    with open(source_file, 'w') as f:
        f.write(code)

    try:
        # Use mcs and mono from PATH after system dependency installation
        # Compile
        compile_process = subprocess.run(
            ['mcs', str(source_file), '-out:' + str(executable)],
            capture_output=True,
            text=True
        )

        if compile_process.returncode != 0:
            return {
                'success': False,
                'output': '',
                'error': compile_process.stderr
            }

        # Execute
        run_process = subprocess.run(
            ['mono', str(executable)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=5
        )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Execution timed out'
        }
    except Exception as e:
        logging.error(f"Compilation/execution error: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': str(e)
        }