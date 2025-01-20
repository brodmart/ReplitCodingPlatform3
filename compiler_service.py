"""
Compiler service for interactive code execution with enhanced session management
"""
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
        return 'console.readline' in code_lower or 'console.read' in code_lower
    return False

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

def compile_and_run(
    code: str,
    language: str,
    input_data: Optional[str] = None,
    compile_only: bool = False,
    interactive: Optional[bool] = None,
    compile_timeout: int = 30,
    execution_timeout: int = 60
) -> Dict[str, Any]:
    """
    Enhanced compile and run with better resource management and interactive support
    """
    try:
        # Auto-detect interactive mode if not specified
        if interactive is None:
            interactive = is_interactive_code(code, language)
            logger.debug(f"Auto-detected interactive mode: {interactive}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            chunk_size = 1024 * 1024  # 1MB chunks

            if language == 'cpp':
                source_file = temp_path / "program.cpp"
                executable = temp_path / "program"
            elif language == 'csharp':
                source_file = temp_path / "program.cs"
                executable = temp_path / "program.exe"
            else:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

            # Write code in chunks
            with open(source_file, 'w') as f:
                for i in range(0, len(code), chunk_size):
                    chunk = code[i:i + chunk_size]
                    f.write(chunk)
                    f.flush()

            # Compile with appropriate timeout
            compile_cmd = (
                ['g++', str(source_file), '-o', str(executable), '-std=c++11']
                if language == 'cpp'
                else ['mcs', str(source_file), '-out:' + str(executable)]
            )

            try:
                logger.debug(f"Compiling with command: {compile_cmd}")
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=compile_timeout
                )
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'error': f"Compilation timeout after {compile_timeout} seconds"
                }

            if compile_process.returncode != 0:
                return {
                    'success': False,
                    'error': compile_process.stderr
                }

            if compile_only:
                return {'success': True}

            # Make executable
            os.chmod(executable, 0o755)

            # Execute with proper resource limits
            cmd = [str(executable)] if language == 'cpp' else ['mono', str(executable)]

            try:
                # Set process group for better cleanup
                logger.debug(f"Starting process with command: {cmd}")
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE if interactive or input_data else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffering
                    preexec_fn=os.setsid,  # Create new process group
                    cwd=temp_dir
                )

                if interactive:
                    # Return process info for interactive handling
                    logger.debug("Starting interactive session")
                    session_id = str(process.pid)
                    with session_lock:
                        active_sessions[session_id] = CompilerSession(session_id, temp_dir)
                        active_sessions[session_id].process = process
                    return {
                        'success': True,
                        'session_id': session_id,
                        'interactive': True
                    }
                else:
                    # Non-interactive execution
                    try:
                        stdout, stderr = process.communicate(
                            input=input_data,
                            timeout=execution_timeout
                        )

                        # Monitor resource usage
                        cpu_usage, memory_usage = monitor_process_resources(process.pid)
                        if cpu_usage > 90 or memory_usage > 90:
                            logger.warning(f"High resource usage - CPU: {cpu_usage}%, Memory: {memory_usage}%")

                        return {
                            'success': process.returncode == 0,
                            'output': stdout,
                            'error': stderr if process.returncode != 0 else None,
                            'cpu_usage': cpu_usage,
                            'memory_usage': memory_usage
                        }

                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        return {
                            'success': False,
                            'error': f"Execution timeout after {execution_timeout} seconds. Check for infinite loops or add Console.ReadLine() for interactive programs."
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