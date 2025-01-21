import subprocess
import tempfile
import os
import logging
import traceback
import signal
import psutil
import shutil
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
import uuid
import time
from threading import Thread, Event, Lock
import select
import io

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CompilerError(Exception):
    """Raised when compilation fails"""
    pass

class ExecutionError(Exception):
    """Raised when execution fails"""
    pass

class ProcessMonitor(Thread):
    def __init__(self, process, timeout=30):
        super().__init__()
        self.process = process
        self.timeout = timeout
        self.start_time = time.time()
        self.stopped = Event()

    def run(self):
        while not self.stopped.is_set():
            if time.time() - self.start_time > self.timeout:
                try:
                    if self.process.poll() is None:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except:
                    pass
                break
            try:
                proc = psutil.Process(self.process.pid)
                if proc.cpu_percent(interval=0.1) > 90 or proc.memory_percent() > 90:
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    except:
                        pass
                    break
            except:
                break
            time.sleep(0.5)

    def stop(self):
        self.stopped.set()

# Global session management
active_sessions = {}
session_lock = Lock()

class CompilerSession:
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id = session_id
        self.temp_dir = temp_dir
        self.process = None
        self.last_activity = time.time()
        self.stdout_buffer = []
        self.stderr_buffer = []
        self.waiting_for_input = False
        self.output_thread = None

def is_interactive_code(code: str, language: str) -> bool:
    """Detect if code is likely interactive based on input patterns"""
    code_lower = code.lower()
    if language == 'cpp':
        return 'cin' in code_lower or 'getline' in code_lower
    elif language == 'csharp':
        return 'console.readline' in code_lower or 'console.read' in code_lower or 'readkey' in code_lower
    return False

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session for the given code"""
    try:
        # Enhanced C# code preprocessing
        if language == 'csharp':
            # Add Console.Out.Flush() after WriteLine statements
            code_lines = code.split('\n')
            modified_code = []
            for line in code_lines:
                modified_code.append(line)
                if 'Console.WriteLine' in line or 'Console.Write(' in line:
                    indent = len(line) - len(line.lstrip())
                    modified_code.append(' ' * indent + 'Console.Out.Flush();')

            # Add automatic flush after every Console operation
            for i, line in enumerate(code_lines):
                if 'Console.' in line and not line.strip().startswith('//'):
                    indent = len(line) - len(line.lstrip())
                    modified_code.append(' ' * indent + 'Console.Out.Flush();')

            code = '\n'.join(modified_code)

            # Ensure proper namespace structure
            if 'namespace' not in code:
                code = """using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ConsoleApplication {
""" + code + "\n}"

        # Compile the code with enhanced options
        source_file = Path(session.temp_dir) / "program.cs"
        executable = Path(session.temp_dir) / "program.exe"

        with open(source_file, 'w') as f:
            f.write(code)

        compile_cmd = [
            'mcs',
            '-optimize+',
            '-debug-',
            '-unsafe-',
            '-reference:System.Core.dll',
            '-reference:System.dll',
            str(source_file),
            '-out:' + str(executable)
        ]

        compile_process = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=20
        )

        if compile_process.returncode != 0:
            cleanup_session(session.session_id)
            return {
                'success': False,
                'error': compile_process.stderr
            }

        os.chmod(executable, 0o755)

        # Enhanced environment variables for better console handling
        env = os.environ.copy()
        env['MONO_IOMAP'] = 'all'
        env['MONO_TRACE_LISTENER'] = 'Console.Out'
        env['MONO_DEBUG'] = 'explicit-null-checks,handle-sigint'
        env['MONO_THREADS_PER_CPU'] = '2'
        env['MONO_GC_PARAMS'] = 'mode=throughput'

        run_cmd = ['mono', '--debug', str(executable)]
        session.process = subprocess.Popen(
            run_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            preexec_fn=os.setsid
        )

        # Start output monitoring thread
        def monitor_output():
            try:
                while session.process and session.process.poll() is None:
                    # Use select to check for available output
                    readable, _, _ = select.select([session.process.stdout, session.process.stderr], [], [], 0.1)

                    for stream in readable:
                        line = stream.readline()
                        if line:
                            if stream == session.process.stdout:
                                session.stdout_buffer.append(line)
                                logger.debug(f"Output received: {line.strip()}")
                                if any(prompt in line.lower() for prompt in ['input', 'enter', 'type', '?', ':', '>']):
                                    session.waiting_for_input = True
                            else:
                                session.stderr_buffer.append(line)
                                logger.debug(f"Error output: {line.strip()}")
                            session.last_activity = time.time()
            except Exception as e:
                logger.error(f"Error in monitor_output: {e}")

        session.output_thread = Thread(target=monitor_output)
        session.output_thread.daemon = True
        session.output_thread.start()

        return {
            'success': True,
            'session_id': session.session_id,
            'interactive': True
        }

    except Exception as e:
        logger.error(f"Error starting interactive session: {e}")
        cleanup_session(session.session_id)
        return {
            'success': False,
            'error': str(e)
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
            logger.debug(f"Input sent to process: {input_data}")
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
        if not session.process:
            return {'success': False, 'error': 'No active process'}

        # Check if process has ended
        if session.process.poll() is not None:
            # Get any remaining output
            remaining_out, remaining_err = session.process.communicate()
            if remaining_out:
                session.stdout_buffer.append(remaining_out)
            if remaining_err:
                session.stderr_buffer.append(remaining_err)

            output = ''.join(session.stdout_buffer)
            cleanup_session(session_id)
            return {
                'success': True,
                'output': output,
                'session_ended': True
            }

        # Return accumulated output
        output = ''.join(session.stdout_buffer)
        if output:
            logger.debug(f"Returning output: {output.strip()}")
        session.stdout_buffer = []  # Clear buffer after reading

        return {
            'success': True,
            'output': output,
            'waiting_for_input': session.waiting_for_input,
            'session_ended': False
        }

    except Exception as e:
        logger.error(f"Error getting output: {e}")
        return {'success': False, 'error': str(e)}

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

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with improved monitoring and feedback.
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

        # For C#, ensure required namespaces and basic code structure
        if language.lower() == 'csharp':
            # Validate code size
            if len(code) > 1000000:  # 1MB limit
                return {
                    'success': False,
                    'error': "Code size exceeds maximum limit (1MB). Please reduce the size of your code."
                }

            # Only add namespaces if they're not present
            required_namespaces = [
                "using System;",
                "using System.IO;",
                "using System.Collections.Generic;",
                "using System.Linq;",
                "using System.Text;",
                "using System.Threading.Tasks;"
            ]

            # Add missing namespaces only if they're not already present
            namespace_code = ""
            for namespace in required_namespaces:
                if namespace not in code:
                    namespace_code += namespace + "\n"

            # Add namespace only if code doesn't already have one
            if "namespace" not in code:
                modified_code = namespace_code + "\nnamespace ConsoleApplication {\n" + code + "\n}"
            else:
                modified_code = namespace_code + code

            # Write code to file with proper encoding
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                source_file = temp_path / "program.cs"
                executable = temp_path / "program.exe"

                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(modified_code)

                # Enhanced compilation command
                compile_cmd = [
                    'mcs',
                    '-optimize+',
                    '-debug-',
                    '-unsafe-',
                    '-reference:System.Core.dll',
                    '-reference:System.dll',
                    str(source_file),
                    '-out:' + str(executable)
                ]

                try:
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=20
                    )

                    if compile_process.returncode != 0:
                        error_msg = compile_process.stderr
                        formatted_error = format_csharp_error(error_msg)
                        return {
                            'success': False,
                            'error': formatted_error
                        }

                    os.chmod(executable, 0o755)

                    # Set up environment for mono execution
                    env = os.environ.copy()
                    env['MONO_IOMAP'] = 'all'
                    env['MONO_TRACE_LISTENER'] = 'Console.Out'
                    env['MONO_DEBUG'] = 'explicit-null-checks'
                    env['MONO_THREADS_PER_CPU'] = '2'

                    # Run the compiled program
                    process = subprocess.Popen(
                        ['mono', str(executable)],
                        stdin=subprocess.PIPE if input_data else None,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        env=env,
                        preexec_fn=os.setsid
                    )

                    monitor = ProcessMonitor(process, timeout=30)
                    monitor.start()

                    try:
                        stdout, stderr = process.communicate(
                            input=input_data,
                            timeout=30
                        )

                        # Check for any error output
                        if stderr and stderr.strip():
                            logger.error(f"Program stderr: {stderr}")
                            return {
                                'success': False,
                                'error': format_runtime_error(stderr)
                            }

                        # Check process return code
                        if process.returncode != 0:
                            error_msg = stderr if stderr else "Program exited with non-zero status"
                            logger.error(f"Program failed: {error_msg}")
                            return {
                                'success': False,
                                'error': format_runtime_error(error_msg)
                            }

                        output = stdout.strip() if stdout else ""
                        return {
                            'success': True,
                            'output': output,
                            'interactive': True if 'Console.ReadLine' in code else False
                        }

                    except subprocess.TimeoutExpired:
                        return {
                            'success': False,
                            'error': "Execution timeout after 30 seconds. For interactive programs, use Console.ReadLine() to get user input."
                        }
                    finally:
                        monitor.stop()
                        monitor.join()
                        try:
                            if process.poll() is None:
                                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                                process.wait(timeout=1)
                        except:
                            pass

                except Exception as e:
                    logger.error(f"Execution error: {e}", exc_info=True)
                    return {
                        'success': False,
                        'error': format_execution_error(str(e))
                    }

        # Check if code is interactive
        interactive = is_interactive_code(code, language)
        logger.debug(f"Code is interactive: {interactive}")

        if interactive:
            # Create a new session for interactive execution
            session_id = str(uuid.uuid4())
            temp_dir = tempfile.mkdtemp()
            session = CompilerSession(session_id, temp_dir)

            with session_lock:
                active_sessions[session_id] = session

            return start_interactive_session(session, code, language)

        # Non-interactive execution
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_file = temp_path / "program.cs"
            executable = temp_path / "program.exe"

            # Write code to file
            with open(source_file, 'w') as f:
                f.write(code)

            compile_cmd = [
                'mcs',
                '-optimize+',
                '-debug-',
                '-unsafe-',
                str(source_file),
                '-out:' + str(executable)
            ]

            try:
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=20
                )
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'error': "Compilation timeout after 20 seconds"
                }

            if compile_process.returncode != 0:
                # Enhanced error message formatting for C# compilation errors
                error_msg = compile_process.stderr
                formatted_error = format_csharp_error(error_msg)
                return {
                    'success': False,
                    'error': formatted_error
                }

            os.chmod(executable, 0o755)

            try:
                env = os.environ.copy()
                env['MONO_IOMAP'] = 'all'

                process = subprocess.Popen(
                    ['mono', '--debug', str(executable)],
                    stdin=subprocess.PIPE if input_data else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=env,
                    preexec_fn=os.setsid
                )

                monitor = ProcessMonitor(process, timeout=20)
                monitor.start()

                try:
                    stdout, stderr = process.communicate(
                        input=input_data,
                        timeout=20
                    )
                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'error': "Execution timeout after 20 seconds. Check for infinite loops."
                    }
                finally:
                    monitor.stop()
                    monitor.join()
                    try:
                        if process.poll() is None:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                            process.wait(timeout=1)
                    except:
                        pass

                if process.returncode == 0:
                    output = stdout.strip() if stdout else "No output generated. If you expected output, ensure Console.WriteLine statements are used and properly flushed."
                    return {
                        'success': True,
                        'output': output
                    }
                else:
                    error_msg = format_runtime_error(stderr) if stderr else "Program failed with no error message"
                    return {
                        'success': False,
                        'error': error_msg
                    }

            except Exception as e:
                logger.error(f"Execution error: {e}", exc_info=True)
                return {
                    'success': False,
                    'error': format_execution_error(str(e))
                }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'output': '',
            'error': "Code execution service encountered an error. Please try again."
        }

def format_csharp_error(error_msg: str) -> str:
    """Format C# compilation errors to be more user-friendly"""
    try:
        # Extract the core error message
        if "error CS" in error_msg:
            # Split the error message into parts
            parts = error_msg.split("): ")
            if len(parts) > 1:
                error_code = parts[0].split("error CS")[1].strip()
                error_desc = parts[1].strip()

                # Common error codes and their friendly messages
                error_messages = {
                    "1525": "Code structure issue. Make sure all statements are inside methods and check for missing semicolons or braces.",
                    "1002": "Syntax Error: Missing closing curly brace '}'",
                    "1001": "Syntax Error: Missing opening curly brace '{'",
                    "1513": "Error: Invalid statement. Make sure you're inside a method.",
                    "0117": "Error: Method must have a return type. Did you forget 'void' or 'int'?",
                    "0161": "Error: 'Console.WriteLine' can only be used inside a method"
                }

                friendly_msg = error_messages.get(error_code, error_desc)
                # Add line number context to help locate the issue
                line_num = error_msg.split('(')[1].split(',')[0]
                return f"Compilation Error (CS{error_code}) at line {line_num}:\n{friendly_msg}\n\nTip: Check the code structure around this line and ensure all statements are properly enclosed in methods.\n\nOriginal Error: {error_desc}"

        return error_msg
    except Exception:
        return error_msg

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors to be more user-friendly"""
    if "System.NullReferenceException" in error_msg:
        return "Runtime Error: Attempted to use a null object. Check if all your variables are initialized before use."
    elif "System.IndexOutOfRangeException" in error_msg:
        return "Runtime Error: Array index out of bounds. Make sure you're not accessing an array beyond its size."
    elif "System.DivideByZeroException" in error_msg:
        return "Runtime Error: Division by zero detected. Check your arithmetic operations."
    elif "System.StackOverflowException" in error_msg:
        return "Runtime Error: Stack overflow. This usually happens with infinite recursion."
    return error_msg

def format_execution_error(error_msg: str) -> str:
    """Format general execution errors to be more user-friendly"""
    if "access denied" in error_msg.lower():
        return "Execution Error: Permission denied. The program doesn't have required permissions."
    elif "memory" in error_msg.lower():
        return "Execution Error: Out of memory. Try reducing the size of variables or arrays."
    elif "timeout" in error_msg.lower():
        return "Execution Error: Program took too long to execute. Check for infinite loops."
    return f"Execution Error: {error_msg}"