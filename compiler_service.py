import subprocess
import tempfile
import os
import logging
import traceback
import signal
from typing import Dict, Optional, Any
from pathlib import Path
import psutil
import time
import shutil
from threading import Lock, Thread, Event
import select
import io
import hashlib
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 60    # seconds, increased from 30
MAX_EXECUTION_TIME = 30     # seconds, increased from 15
MEMORY_LIMIT = 1024        # MB, increased from 512
COMPILER_CACHE_DIR = "/tmp/compiler_cache"
CACHE_MAX_SIZE = 50      # Maximum number of cached compilations

# Initialize cache directory
os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
_compilation_cache = {}
_cache_lock = Lock()

def get_code_hash(code: str, language: str) -> str:
    """Generate a unique hash for the code and language"""
    hasher = hashlib.sha256()
    hasher.update(f"{code}{language}".encode())
    return hasher.hexdigest()

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with optimized performance and enhanced error handling
    """
    metrics = {'start_time': time.time()}
    logger.info(f"Starting compile_and_run for {language}")

    if not code or not language:
        return {
            'success': False,
            'error': "No code or language specified",
            'metrics': metrics
        }

    # Check if code is interactive
    if is_interactive_code(code, language):
        logger.info("Detected interactive code, starting interactive session")
        session_id = str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp(prefix='compile_', dir=COMPILER_CACHE_DIR)
        session = CompilerSession(session_id, temp_dir)

        with session_lock:
            active_sessions[session_id] = session

        try:
            result = start_interactive_session(session, code, language)
            if result['success']:
                result['interactive'] = True
                result['session_id'] = session_id
            else:
                cleanup_session(session_id)
            return result
        except Exception as e:
            cleanup_session(session_id)
            return {
                'success': False,
                'error': str(e),
                'metrics': metrics
            }

    # Create a unique temporary directory for this compilation
    temp_dir = tempfile.mkdtemp(prefix='compile_', dir=COMPILER_CACHE_DIR)
    temp_path = Path(temp_dir)

    try:
        if language == 'cpp':
            # Set up C++ compilation
            source_file = temp_path / "program.cpp"
            executable = temp_path / "program"

            # Write source code with proper encoding
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Enhanced compilation command with optimizations
            compile_cmd = [
                'g++',
                '-std=c++17',  # Use modern C++
                '-O2',         # Optimize
                '-Wall',       # Enable warnings
                str(source_file),
                '-o',
                str(executable)
            ]

            try:
                # Compile with proper resource limits
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': f"Compilation Error: {compile_process.stderr}",
                        'metrics': metrics
                    }

                # Set executable permissions
                executable.chmod(0o755)

                # Run the compiled program
                run_process = subprocess.run(
                    [str(executable)],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME
                )

                if run_process.returncode != 0:
                    return {
                        'success': False,
                        'error': f"Runtime Error: {run_process.stderr}",
                        'metrics': metrics
                    }

                return {
                    'success': True,
                    'output': run_process.stdout,
                    'metrics': metrics
                }

            except subprocess.TimeoutExpired as e:
                phase = "compilation" if time.time() - metrics['start_time'] < MAX_COMPILATION_TIME else "execution"
                return {
                    'success': False,
                    'error': f"{phase.capitalize()} timed out",
                    'metrics': metrics
                }

        elif language == 'csharp':
            # Set up C# project structure
            source_file = temp_path / "Program.cs"
            project_file = temp_path / "program.csproj"

            # Write source code with proper encoding
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Create optimized project file
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
  </PropertyGroup>
</Project>"""
            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            try:
                # Compile using optimized build command
                compile_cmd = [
                    'dotnet', 'build',
                    str(project_file),
                    '--configuration', 'Release',
                    '--nologo',
                    '/p:GenerateFullPaths=true',
                    '/consoleloggerparameters:NoSummary'
                ]

                logger.info("Building project...")
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(temp_path)
                )

                metrics['compilation_time'] = time.time() - metrics['start_time']

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr),
                        'metrics': metrics
                    }

                # Run the compiled program
                dll_path = temp_path / "bin" / "Release" / "net7.0" / "program.dll"
                if not dll_path.exists():
                    return {
                        'success': False,
                        'error': "Build succeeded but no executable found",
                        'metrics': metrics
                    }

                logger.info("Running program...")
                run_process = subprocess.run(
                    ['dotnet', str(dll_path)],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path),
                    env={**os.environ, 'DOTNET_CONSOLE_ENCODING': 'utf-8'}
                )

                metrics['execution_time'] = time.time() - (metrics['start_time'] + metrics['compilation_time'])
                metrics['total_time'] = time.time() - metrics['start_time']

                if run_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_runtime_error(run_process.stderr),
                        'metrics': metrics
                    }

                return {
                    'success': True,
                    'output': run_process.stdout,
                    'metrics': metrics
                }

            except subprocess.TimeoutExpired as e:
                phase = "compilation" if time.time() - metrics['start_time'] < MAX_COMPILATION_TIME else "execution"
                error_msg = f"{phase.capitalize()} timed out after {MAX_COMPILATION_TIME if phase == 'compilation' else MAX_EXECUTION_TIME} seconds"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'metrics': metrics
                }

        else:
            return {
                'success': False,
                'error': f"Unsupported language: {language}",
                'metrics': metrics
            }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'metrics': metrics
        }
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_path)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp_path}: {e}")

def format_csharp_error(error_msg: str) -> str:
    """Format C# compilation errors to be more user-friendly"""
    try:
        if "error CS" in error_msg:
            error_parts = error_msg.split(": ", 1)
            if len(error_parts) > 1:
                error_description = error_parts[1].strip()
                return f"Compilation Error: {error_description}"
        return f"Compilation Error: {error_msg}"
    except Exception as e:
        logger.error(f"Error formatting C# error message: {str(e)}")
        return f"Compilation Error: {error_msg}"

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors to be more user-friendly"""
    try:
        if not error_msg:
            return "Unknown runtime error occurred"

        common_errors = {
            "System.NullReferenceException": "Attempted to use a null object",
            "System.IndexOutOfRangeException": "Array index out of bounds",
            "System.DivideByZeroException": "Division by zero detected",
            "System.InvalidOperationException": "Invalid operation",
            "System.ArgumentException": "Invalid argument provided",
            "System.FormatException": "Invalid format"
        }

        for error_type, message in common_errors.items():
            if error_type in error_msg:
                return f"Runtime Error: {message}"

        return f"Runtime Error: {error_msg}"
    except Exception:
        return f"Runtime Error: {error_msg}"

class CompilerSession:
    """Session handler for interactive compilation."""
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id = session_id
        self.temp_dir = temp_dir
        self.process: Optional[subprocess.Popen] = None
        self.last_activity = time.time()
        self.stdout_buffer: list[str] = []
        self.stderr_buffer: list[str] = []
        self.waiting_for_input = False
        self.output_thread: Optional[Thread] = None

def is_interactive_code(code: str, language: str) -> bool:
    """Detect if code is likely interactive based on input patterns"""
    code_lower = code.lower()
    if language == 'cpp':
        return 'cin' in code_lower or 'getline' in code_lower or 'cout' in code_lower
    elif language == 'csharp':
        return ('console.readline' in code_lower or 
                'console.read' in code_lower or 
                'console.write' in code_lower or
                'readkey' in code_lower)
    return False

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session for the given code"""
    try:
        logger.debug(f"Starting interactive session for {language}")

        if language == 'cpp':
            # Write code to temp file
            source_file = Path(session.temp_dir) / "program.cpp"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Compile C++ code
            executable = Path(session.temp_dir) / "program"
            compile_process = subprocess.run(
                ['g++', '-std=c++17', str(source_file), '-o', str(executable)],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME
            )

            if compile_process.returncode != 0:
                return {
                    'success': False,
                    'error': f"Compilation Error: {compile_process.stderr}"
                }

            # Make executable
            executable.chmod(0o755)

            # Start interactive process
            process = subprocess.Popen(
                [str(executable)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffering
                cwd=str(session.temp_dir)
            )

            session.process = process

            # Start output monitoring thread
            def monitor_output():
                while process.poll() is None:
                    readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

                    for stream in readable:
                        char = stream.read(1)
                        if char:
                            if stream == process.stdout:
                                session.stdout_buffer.append(char)
                                # Check for input prompts
                                recent_output = ''.join(session.stdout_buffer[-100:])
                                if any(prompt in recent_output.lower() for prompt in [
                                    'input', 'enter', 'type', '?', ':', '>',
                                    'choice', 'select', 'press', 'continue'
                                ]):
                                    session.waiting_for_input = True
                            else:
                                session.stderr_buffer.append(char)
                            session.last_activity = time.time()

            session.output_thread = Thread(target=monitor_output)
            session.output_thread.daemon = True
            session.output_thread.start()

            return {
                'success': True,
                'session_id': session.session_id,
                'interactive': True
            }

        elif language == 'csharp':
            # Don't wrap code that already has a Program class
            if 'class Program' in code:
                modified_code = code
            else:
                modified_code = f"""using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Globalization;
using System.Text;

{code}"""

            # Write code to temp file
            source_file = Path(session.temp_dir) / "Program.cs"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(modified_code)

            # Create project file for proper console app with console input support
            project_file = Path(session.temp_dir) / "program.csproj"
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>"""
            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            try:
                # Compile with enhanced settings for console I/O
                start_time = time.time()
                compile_process = subprocess.run(
                    ['dotnet', 'build', str(project_file),
                     '--configuration', 'Release',
                     '--nologo',
                     '/p:GenerateFullPaths=true',
                     '/consoleloggerparameters:NoSummary'],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(session.temp_dir)
                )
                compilation_time = time.time() - start_time

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr)
                    }

                # Run with enhanced interactive I/O settings
                dll_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / "program.dll"
                process = subprocess.Popen(
                    ['dotnet', str(dll_path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffering
                    cwd=str(session.temp_dir),
                    env={**os.environ, 'DOTNET_CONSOLE_ENCODING': 'utf-8'}
                )

                session.process = process

                # Start output monitoring thread with improved prompt detection
                def monitor_output():
                    while process.poll() is None:
                        readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

                        for stream in readable:
                            char = stream.read(1)
                            if char:
                                if stream == process.stdout:
                                    session.stdout_buffer.append(char)
                                    # Enhanced prompt detection for both languages
                                    recent_output = ''.join(session.stdout_buffer[-100:])
                                    if any(prompt in recent_output.lower() for prompt in [
                                        'input', 'enter', 'type', '?', ':', '>',
                                        'choice', 'select', 'press', 'continue',
                                        'choix', 'votre choix', 'entrer'
                                    ]):
                                        session.waiting_for_input = True
                                else:
                                    session.stderr_buffer.append(char)
                                session.last_activity = time.time()

                session.output_thread = Thread(target=monitor_output)
                session.output_thread.daemon = True
                session.output_thread.start()

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True,
                    'compilation_time': compilation_time
                }

            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'error': f"Compilation timed out after {MAX_COMPILATION_TIME} seconds"
                }

        else:
            return {
                'success': False,
                'error': f"Interactive mode not supported for {language}"
            }

    except Exception as e:
        logger.error(f"Error in start_interactive_session: {e}")
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

class CompilationMetrics:
    """Track compilation and execution metrics"""
    def __init__(self):
        self.start_time = time.time()
        self.compilation_time = 0.0
        self.execution_time = 0.0
        self.peak_memory = 0
        self.status_updates = []

    def log_status(self, status: str):
        current_time = time.time() - self.start_time
        self.status_updates.append((current_time, status))
        logger.debug(f"[{current_time:.2f}s] {status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'compilation_time': self.compilation_time,
            'execution_time': self.execution_time,
            'peak_memory': self.peak_memory,
            'total_time': time.time() - self.start_time,
            'status_updates': self.status_updates
        }

class ProcessMonitor(Thread):
    def __init__(self, process, timeout=30, memory_limit_mb=512):
        super().__init__()
        self.process = process
        self.timeout = timeout
        self.memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        self.metrics = CompilationMetrics()
        self.stopped = Event()

    def run(self):
        while not self.stopped.is_set():
            try:
                if time.time() - self.metrics.start_time > self.timeout:
                    self.metrics.log_status("Process timed out")
                    self._terminate_process()
                    break

                if self.process.poll() is not None:
                    break

                proc = psutil.Process(self.process.pid)
                memory_info = proc.memory_info()
                cpu_percent = proc.cpu_percent(interval=0.1)

                self.metrics.peak_memory = max(self.metrics.peak_memory, memory_info.rss)

                if memory_info.rss > self.memory_limit:
                    self.metrics.log_status(f"Memory limit exceeded: {memory_info.rss / (1024*1024):.1f}MB")
                    self._terminate_process()
                    break

                if cpu_percent > 90:
                    self.metrics.log_status(f"High CPU usage: {cpu_percent}%")

            except Exception as e:
                logger.error(f"Monitor error: {str(e)}")
                break
            time.sleep(0.1)

    def _terminate_process(self):
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except:
            if self.process.poll() is None:                self.process.terminate()
    def stop(self):
        self.stopped.set()
        self._terminate_process()

# Initialize session management
active_sessions = {}
session_lock = Lock()