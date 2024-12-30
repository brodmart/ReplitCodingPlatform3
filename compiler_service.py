import subprocess
import tempfile
import os
import logging
from pathlib import Path

def compile_and_run(code, language):
    with tempfile.TemporaryDirectory() as temp_dir:
        if language == 'cpp':
            return _compile_and_run_cpp(code, temp_dir)
        elif language == 'csharp':
            return _compile_and_run_csharp(code, temp_dir)
        else:
            raise ValueError(f"Unsupported language: {language}")

def _compile_and_run_cpp(code, temp_dir):
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

def _compile_and_run_csharp(code, temp_dir):
    source_file = Path(temp_dir) / "program.cs"
    executable = Path(temp_dir) / "program.exe"
    
    # Write source code to file
    with open(source_file, 'w') as f:
        f.write(code)
    
    try:
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
