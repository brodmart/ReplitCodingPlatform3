"""
Compiler service for code execution and testing.
"""
import subprocess
import tempfile
import os
import logging
import traceback
import signal
import psutil
from pathlib import Path
from typing import Dict, Optional, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CompilerError(Exception):
    """Raised when compilation fails"""
    pass

class ExecutionError(Exception):
    """Raised when execution fails"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code for testing purposes.
    This is a wrapper around the more detailed compiler_service implementation.
    """
    if not code or not language:
        logger.error("Invalid input parameters: code or language is missing")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        logger.debug(f"Attempting to compile and run {language} code")
        logger.debug(f"Code length: {len(code)} characters")

        # For C#, ensure required namespaces are present
        if language.lower() == 'csharp':
            required_namespaces = [
                "using System;",
                "using System.IO;",
                "using System.Collections.Generic;",
                "using System.Linq;"
            ]
            for namespace in required_namespaces:
                if namespace not in code:
                    code = namespace + "\n" + code

        try:
            # Normalize language
            language = language.lower()
            if language not in ['cpp', 'csharp']:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Set up source and executable files based on language
                if language == 'cpp':
                    source_file = temp_path / "program.cpp"
                    executable = temp_path / "program"
                    compile_cmd = ['g++', str(source_file), '-o', str(executable), '-std=c++11']
                    run_cmd = [str(executable)]
                else:  # csharp
                    source_file = temp_path / "program.cs"
                    executable = temp_path / "program.exe"
                    # Optimized C# compilation settings
                    compile_cmd = [
                        'mcs',
                        '-optimize+',  # Enable optimizations
                        '-debug-',     # Disable debug symbols
                        str(source_file),
                        '-out:' + str(executable)
                    ]
                    run_cmd = ['mono', '--gc=sgen', str(executable)]  # Use better GC

                # Write code to file
                with open(source_file, 'w') as f:
                    f.write(code)

                try:
                    logger.debug(f"Compiling with command: {' '.join(compile_cmd)}")
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30  # Reduced compile timeout
                    )
                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'error': f"Compilation timeout after 30 seconds"
                    }

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': compile_process.stderr
                    }

                # Make executable
                os.chmod(executable, 0o755)

                try:
                    # Execute the program with resource limits
                    process = subprocess.Popen(
                        run_cmd,
                        stdin=subprocess.PIPE if input_data else None,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,  # Line buffering
                        preexec_fn=os.setsid
                    )

                    try:
                        # Monitor process resources
                        pid = process.pid
                        def check_resources():
                            try:
                                proc = psutil.Process(pid)
                                cpu_percent = proc.cpu_percent()
                                memory_percent = proc.memory_percent()
                                if cpu_percent > 90 or memory_percent > 90:
                                    return True
                                return False
                            except:
                                return False

                        stdout, stderr = process.communicate(
                            input=input_data,
                            timeout=30  # Reduced execution timeout
                        )

                        if process.returncode == 0:
                            # Only return stdout if there was actually output
                            output = stdout.strip() if stdout else "Program executed successfully with no output."
                            return {
                                'success': True,
                                'output': output
                            }
                        else:
                            return {
                                'success': False,
                                'error': stderr or "Program failed with no error message"
                            }

                    except subprocess.TimeoutExpired:
                        # Kill the process group
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        except:
                            pass
                        return {
                            'success': False,
                            'error': f"Execution timeout after 30 seconds"
                        }

                except Exception as e:
                    logger.error(f"Execution error: {e}", exc_info=True)
                    return {
                        'success': False,
                        'error': f"Execution error: {str(e)}"
                    }

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f"Service error: {str(e)}"
            }

    except Exception as e:
        logger.error(f"Unexpected error in compile_and_run: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'output': '',
            'error': "Code execution service encountered an error. Please try again."
        }

import subprocess
import tempfile
import os
import logging
import shutil
import signal
import psutil
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Global session management
active_sessions = {}
session_lock = Lock()

class CompilerSession:
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id = session_id
        self.temp_dir = temp_dir
        self.process = None
        self.last_activity = None
        self.stdout_buffer = []
        self.stderr_buffer = []
        self.waiting_for_input = False

def is_interactive_code(code: str, language: str) -> bool:
    """Detect if code is likely interactive based on input patterns"""
    code_lower = code.lower()
    if language == 'cpp':
        return 'cin' in code_lower or 'getline' in code_lower
    elif language == 'csharp':
        # Add more C# input patterns
        return 'console.readline' in code_lower or 'console.read' in code_lower or 'readkey' in code_lower
    return False


def send_input(session_id: str, input_data: str) -> Dict[str, Any]:
    """Send input to an interactive session"""
    if session_id not in active_sessions:
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    try:
        if session.process and session.process.poll() is None:
            session.process.stdin.write(input_data + '\n')
            session.process.stdin.flush()
            session.waiting_for_input = False
            return {'success': True}
        else:
            return {'success': False, 'error': 'Process not running'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from an interactive session"""
    if session_id not in active_sessions:
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    try:
        output = []
        if session.process:
            if session.process.poll() is not None:
                # Process ended
                remaining_output, remaining_error = session.process.communicate()
                if remaining_output:
                    output.append(remaining_output)
                cleanup_session(session_id)
                return {
                    'success': True,
                    'output': ''.join(output),
                    'session_ended': True
                }

            # Check for new output
            try:
                while True:
                    line = session.process.stdout.readline()
                    if not line:
                        break
                    output.append(line)
                    # Check for input prompts
                    if any(prompt in line.lower() for prompt in [
                        'input', 'enter', 'type', '?', ':', '>',
                        'cin', 'console.readline'
                    ]):
                        session.waiting_for_input = True
            except:
                pass  # No more output available

        return {
            'success': True,
            'output': ''.join(output),
            'waiting_for_input': session.waiting_for_input,
            'session_ended': False
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def monitor_process_resources(pid: int) -> Tuple[float, float]:
    """Monitor CPU and memory usage of a process"""
    try:
        process = psutil.Process(pid)
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_percent = process.memory_percent()
        return cpu_percent, memory_percent
    except:
        return 0.0, 0.0

def cleanup_session(session_id: str) -> None:
    """Clean up resources for a session"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        try:
            if session.process and session.process.poll() is None:
                try:
                    group_id = os.getpgid(session.process.pid)
                    os.killpg(group_id, signal.SIGTERM)
                except:
                    session.process.terminate()
                try:
                    session.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    session.process.kill()
                    session.process.wait()

            if os.path.exists(session.temp_dir):
                shutil.rmtree(session.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
        finally:
            with session_lock:
                del active_sessions[session_id]