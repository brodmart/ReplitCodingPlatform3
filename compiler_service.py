"""
Compiler service for interactive code execution
"""
import subprocess
import tempfile
import os
import logging
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

def compile_and_run(code: str, language: str, input_data: Optional[str] = None, compile_only: bool = False, dest_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with proper input/output handling.
    If compile_only is True, it will only compile the code and copy the executable to dest_dir or current directory.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            chunk_size = 1024 * 1024 # 1MB chunks

            if language == 'cpp':
                source_file = temp_path / "program.cpp"
                executable = temp_path / "program"

                # Write code in chunks to handle large files
                with open(source_file, 'w') as f:
                    for i in range(0, len(code), chunk_size):
                        chunk = code[i:i + chunk_size]
                        f.write(chunk)
                        f.flush()
                        logger.debug(f"Wrote chunk {i//chunk_size + 1} of {(len(code) + chunk_size - 1)//chunk_size}")

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

                if compile_only:
                    # Copy executable to destination directory if specified, otherwise to current directory
                    try:
                        dest_path = Path(dest_dir) if dest_dir else Path.cwd()
                        dest_executable = dest_path / executable.name
                        shutil.copy2(executable, dest_executable)
                        os.chmod(dest_executable, 0o755)  # Make executable
                        return {'success': True}
                    except Exception as e:
                        return {
                            'success': False,
                            'error': f"Failed to copy executable: {str(e)}"
                        }

                # Run with input if not compile_only
                try:
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
                        'error': run_process.stderr if run_process.stderr else None
                    }

                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'output': '',
                        'error': "Execution timeout"
                    }

            elif language == 'csharp':
                source_file = temp_path / "program.cs"
                executable = temp_path / "program.exe"

                # Write code in chunks to handle large files
                with open(source_file, 'w') as f:
                    for i in range(0, len(code), chunk_size):
                        chunk = code[i:i + chunk_size]
                        f.write(chunk)
                        f.flush()
                        logger.debug(f"Wrote chunk {i//chunk_size + 1} of {(len(code) + chunk_size - 1)//chunk_size}")

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

                if compile_only:
                    # Copy executable to destination directory if specified, otherwise to current directory
                    try:
                        dest_path = Path(dest_dir) if dest_dir else Path.cwd()
                        dest_executable = dest_path / executable.name
                        shutil.copy2(executable, dest_executable)
                        os.chmod(dest_executable, 0o755)  # Make executable
                        return {'success': True}
                    except Exception as e:
                        return {
                            'success': False,
                            'error': f"Failed to copy executable: {str(e)}"
                        }

                # Run with input if not compile_only
                try:
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
        logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
        return {
            'success': False,
            'output': '',
            'error': f"Execution error: {str(e)}"
        }