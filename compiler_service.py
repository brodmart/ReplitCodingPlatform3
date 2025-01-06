import subprocess
import tempfile
import os
import logging
import signal
import resource
import errno
from pathlib import Path
import re
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class CompilerError(Exception):
    """Custom exception for compiler-related errors"""
    pass

class ExecutionError(Exception):
    """Custom exception for execution-related errors"""
    pass

class MemoryLimitExceeded(ExecutionError):
    """Custom exception for memory limit violations"""
    pass

class TimeoutError(ExecutionError):
    """Custom exception for execution timeout"""
    pass

def format_compiler_error(error_text: str, lang: str = 'cpp') -> Dict[str, Any]:
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

    if lang == 'cpp':
        for line in error_lines:
            if 'error:' in line:
                # Extract line number and error message for C++
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
    else:  # C#
        for line in error_lines:
            if '(CS' in line:
                # Extract line number and error message for C#
                match = re.search(r'program\.cs\((\d+),(\d+)\):\s*error\s*(CS\d+):\s*(.+)', line)
                if match:
                    line_num, col_num, error_code, message = match.groups()
                    main_error = {
                        'line': int(line_num),
                        'column': int(col_num),
                        'code': error_code,
                        'message': message.strip(),
                        'type': 'error'
                    }
                    break

    if main_error:
        formatted_msg = (
            f"Erreur ligne {main_error['line']}: {main_error['message']}"
            if 'code' not in main_error else
            f"Erreur {main_error['code']} ligne {main_error['line']}: {main_error['message']}"
        )
        return {
            'error_details': main_error,
            'full_error': error_text,
            'formatted_message': formatted_msg
        }
    return {
        'error_details': None,
        'full_error': error_text,
        'formatted_message': error_text.split('\n')[0] if error_text else "Erreur de compilation"
    }

@contextmanager
def create_temp_directory():
    """Create and clean up temporary directory with proper context management"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        try:
            subprocess.run(['rm', '-rf', temp_dir], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")

def set_memory_limit():
    """Set memory limit to 25MB - reduced from 50MB to prevent allocation issues"""
    memory_limit = 25 * 1024 * 1024  # 25MB in bytes
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    except Exception as e:
        logger.error(f"Failed to set memory limit: {e}")
        # Continue execution with default limits
        return False
    return True

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run code with enhanced security and resource limits"""
    if language not in ['cpp', 'csharp']:
        raise ValueError(f"Unsupported language: {language}")

    with create_temp_directory() as temp_dir:
        try:
            if language == 'cpp':
                return _compile_and_run_cpp(code, temp_dir, input_data)
            else:
                return _compile_and_run_csharp(code, temp_dir, input_data)
        except CompilerError as e:
            logger.error(f"Compilation error: {str(e)}")
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
        except (ExecutionError, MemoryLimitExceeded, TimeoutError) as e:
            error_msg = {
                ExecutionError: "Erreur d'exécution",
                MemoryLimitExceeded: "Limite de mémoire dépassée (100MB)",
                TimeoutError: "Temps d'exécution dépassé (5 secondes)"
            }.get(type(e), "Erreur inattendue")
            logger.error(f"{error_msg}: {str(e)}")
            return {
                'success': False,
                'output': '',
                'error': f"{error_msg}: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in compile_and_run: {e}")
            return {
                'success': False,
                'output': '',
                'error': "Une erreur inattendue s'est produite"
            }

def _compile_and_run_cpp(code: str, temp_dir: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C++ code with enhanced security and memory management"""
    source_file = Path(temp_dir) / "program.cpp"
    executable = Path(temp_dir) / "program"

    try:
        # Write source code to file
        with open(source_file, 'w') as f:
            f.write(code)

        # Compile with basic safety flags, removing optimization and sanitizer flags
        compile_process = subprocess.run(
            ['g++', '-Wall', '-Wextra', '-Werror',
             '-fstack-protector',
             str(source_file), '-o', str(executable)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compile_process.returncode != 0:
            error_info = format_compiler_error(compile_process.stderr, 'cpp')
            logger.error(f"Compilation failed: {error_info['formatted_message']}")
            raise CompilerError(error_info['formatted_message'])

        # Set basic ulimit for the child process
        def preexec_fn():
            """Setup process isolation and basic resource limits"""
            try:
                # Set a soft memory limit of 25MB
                resource.setrlimit(resource.RLIMIT_AS, (25 * 1024 * 1024, -1))
                # Set CPU time limit
                resource.setrlimit(resource.RLIMIT_CPU, (5, -1))
                # Create new process group for easier cleanup
                os.setsid()
            except Exception as e:
                logger.warning(f"Failed to set resource limits: {e}")

        run_process = subprocess.run(
            [str(executable)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=5,  # 5 seconds timeout
            preexec_fn=preexec_fn
        )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr if run_process.stderr else None
        }

    except OSError as e:
        if e.errno == errno.ENOMEM:
            logger.error("Memory allocation error: %s", str(e))
            return {
                'success': False,
                'output': '',
                'error': 'Le programme nécessite trop de mémoire. Veuillez réduire l\'utilisation de la mémoire ou utiliser des tableaux plus petits.'
            }
        return {
            'success': False,
            'output': '',
            'error': f'Erreur système: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Unexpected error in C++ execution: {str(e)}")
        return {
            'success': False,
            'output': '',
            'error': 'Une erreur inattendue s\'est produite lors de l\'exécution'
        }

def _compile_and_run_csharp(code: str, temp_dir: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run C# code with enhanced security"""
    source_file = Path(temp_dir) / "program.cs"
    executable = Path(temp_dir) / "program.exe"

    try:
        with open(source_file, 'w') as f:
            f.write(code)

        # Compile with optimization and security flags
        compile_process = subprocess.run(
            ['mcs', '-debug-', '-optimize+', '-define:SECURITY_CHECK',
             str(source_file), '-out:' + str(executable)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compile_process.returncode != 0:
            error_info = format_compiler_error(compile_process.stderr, 'csharp')
            raise CompilerError(error_info['formatted_message'])

        # Execute with resource limits and isolation
        # Add Mono GC optimization flags
        run_process = subprocess.run(
            ['nice', '-n', '19',  # Lower priority
             'mono', '--debug',
             '--gc=sgen',  # Use SGen GC
             '--gc-params=max-heap-size=25M',  # Limit heap size
             '--gc-params=nursery-size=2M',    # Smaller nursery for more frequent but faster collections
             str(executable)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=5,  # 5 seconds timeout
            preexec_fn=lambda: (
                os.setsid(),  # New process group
                set_memory_limit()  # Memory limit from earlier function
            )
        )

        return {
            'success': True,
            'output': run_process.stdout,
            'error': run_process.stderr if run_process.stderr else None
        }

    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(0), signal.SIGKILL)  # Kill all processes in group
        raise TimeoutError('Le programme a dépassé la limite de temps de 5 secondes')
    except subprocess.CalledProcessError as e:
        raise ExecutionError(f"Erreur d'exécution: {e}")
    except OSError as e:
        if e.errno == errno.ENOMEM:
            raise MemoryLimitExceeded('Le programme a dépassé la limite de mémoire')
        raise ExecutionError(f"Erreur système: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in C# execution: {str(e)}")
        raise ExecutionError(str(e))