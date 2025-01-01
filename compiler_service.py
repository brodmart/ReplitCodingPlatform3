import subprocess
import tempfile
import os
import logging
import signal
from pathlib import Path
import re
import resource
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class CompilerError(Exception):
    """Custom exception for compiler-related errors"""
    pass

class ExecutionError(Exception):
    """Custom exception for execution-related errors"""
    pass

def format_compiler_error(error_text: str) -> Dict[str, Any]:
    """Format compiler error messages to be more user-friendly"""
    if not error_text:
        return {
            'error_details': None,
            'full_error': '',
            'formatted_message': "Une erreur inconnue est survenue"
        }

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

@contextmanager
def set_resource_limits():
    """Set resource limits for child processes"""
    try:
        # 1 second CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        # 100MB memory limit
        resource.setrlimit(resource.RLIMIT_AS, (100 * 1024 * 1024, 100 * 1024 * 1024))
        # No child processes
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        # No file writing
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        yield
    except Exception as e:
        logger.error(f"Failed to set resource limits: {e}")
        raise

@contextmanager
def create_temp_directory():
    """Create and clean up temporary directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        try:
            subprocess.run(['rm', '-rf', temp_dir], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run code with enhanced security and error handling"""
    if language not in ['cpp', 'csharp']:
        raise ValueError(f"Unsupported language: {language}")

    with create_temp_directory() as temp_dir:
        try:
            if language == 'cpp':
                return _compile_and_run_cpp(code, temp_dir, input_data)
            else:
                return _compile_and_run_csharp(code, temp_dir, input_data)
        except CompilerError as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
        except ExecutionError as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in compile_and_run: {e}")
            return {
                'success': False,
                'output': '',
                'error': 'An unexpected error occurred'
            }

def _compile_and_run_cpp(code: str, temp_dir: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C++ code with enhanced security"""
    source_file = Path(temp_dir) / "program.cpp"
    executable = Path(temp_dir) / "program"

    # Write source code to file
    try:
        with open(source_file, 'w') as f:
            f.write(code)
    except IOError as e:
        raise CompilerError(f"Failed to write source file: {e}")

    try:
        # Compile with extra security flags
        compile_process = subprocess.run(
            ['g++', '-Wall', '-Wextra', '-Werror', '-fsanitize=address',
             str(source_file), '-o', str(executable)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compile_process.returncode != 0:
            error_info = format_compiler_error(compile_process.stderr)
            raise CompilerError(error_info['formatted_message'])

        # Execute with resource limits
        with set_resource_limits():
            run_process = subprocess.run(
                [str(executable)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=5,
                preexec_fn=os.setsid
            )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr if run_process.stderr else None
        }

    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(0), signal.SIGKILL)  # Kill any remaining processes
        raise ExecutionError('Execution timed out')
    except subprocess.CalledProcessError as e:
        raise ExecutionError(f"Execution failed: {e}")
    except Exception as e:
        logger.error(f"Compilation/execution error: {str(e)}")
        raise ExecutionError(str(e))

def _compile_and_run_csharp(code: str, temp_dir: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C# code with enhanced security"""
    source_file = Path(temp_dir) / "program.cs"
    executable = Path(temp_dir) / "program.exe"

    try:
        with open(source_file, 'w') as f:
            f.write(code)
    except IOError as e:
        raise CompilerError(f"Failed to write source file: {e}")

    try:
        # Compile
        compile_process = subprocess.run(
            ['mcs', '-debug-', '-optimize+', str(source_file), '-out:' + str(executable)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compile_process.returncode != 0:
            error_info = format_compiler_error(compile_process.stderr)
            raise CompilerError(error_info['formatted_message'])

        # Execute with resource limits
        with set_resource_limits():
            run_process = subprocess.run(
                ['mono', '--debug', str(executable)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=5,
                preexec_fn=os.setsid
            )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr if run_process.stderr else None
        }

    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(0), signal.SIGKILL)  # Kill any remaining processes
        raise ExecutionError('Execution timed out')
    except subprocess.CalledProcessError as e:
        raise ExecutionError(f"Execution failed: {e}")
    except Exception as e:
        logger.error(f"Compilation/execution error: {str(e)}")
        raise ExecutionError(str(e))