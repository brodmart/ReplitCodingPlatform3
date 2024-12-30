import subprocess
import tempfile
import os
import logging
from pathlib import Path

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
        # Use absolute path for g++
        cpp_compiler = '/nix/store/z3c7p0jw4cgkn1kxvxz0sb87kc2jxsl4-gcc-wrapper-12.3.0/bin/g++'

        # Compile
        compile_process = subprocess.run(
            [cpp_compiler, str(source_file), '-o', str(executable)],
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
        # Use absolute path for mono-mcs
        csharp_compiler = '/nix/store/6g6a2ixk1wv8wiv1vb0z7qi5q5jf8gqy-mono-6.12.0.182/bin/mcs'
        mono_runtime = '/nix/store/6g6a2ixk1wv8wiv1vb0z7qi5q5jf8gqy-mono-6.12.0.182/bin/mono'

        # Compile
        compile_process = subprocess.run(
            [csharp_compiler, str(source_file), '-out:' + str(executable)],
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
            [mono_runtime, str(executable)],
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