"""
Compiler service for interactive code execution
"""
import subprocess
import tempfile
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with proper input/output handling.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'cpp':
                source_file = Path(temp_dir) / "program.cpp"
                executable = Path(temp_dir) / "program"

                # Write source code
                with open(source_file, 'w') as f:
                    f.write(code)

                # Compile
                compile_process = subprocess.run(
                    ['g++', str(source_file), '-o', str(executable), '-std=c++11'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'output': '',
                        'error': compile_process.stderr
                    }

                # Run with input
                try:
                    run_process = subprocess.run(
                        [str(executable)],
                        input=input_data,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        encoding='utf-8'
                    )

                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'error': run_process.stderr if run_process.stderr else None
                    }

                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'output': '',
                        'error': "Execution timeout"
                    }

            elif language == 'csharp':
                source_file = Path(temp_dir) / "program.cs"
                executable = Path(temp_dir) / "program.exe"

                # Write source code
                with open(source_file, 'w') as f:
                    f.write(code)

                # Compile
                compile_process = subprocess.run(
                    ['mcs', str(source_file), '-out:' + str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'output': '',
                        'error': compile_process.stderr
                    }

                # Run with input
                try:
                    run_process = subprocess.run(
                        ['mono', str(executable)],
                        input=input_data,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        encoding='utf-8'
                    )

                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'error': run_process.stderr if run_process.stderr else None
                    }

                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'output': '',
                        'error': "Execution timeout"
                    }

            else:
                return {
                    'success': False,
                    'output': '',
                    'error': f"Unsupported language: {language}"
                }

    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': f"Execution error: {str(e)}"
        }