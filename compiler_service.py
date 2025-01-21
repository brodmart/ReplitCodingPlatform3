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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 30  # seconds
MAX_EXECUTION_TIME = 15    # seconds
MEMORY_LIMIT = 512        # MB
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

    # Create a unique temporary directory for this compilation
    temp_dir = tempfile.mkdtemp(prefix='compile_', dir=COMPILER_CACHE_DIR)
    temp_path = Path(temp_dir)

    try:
        if language == 'csharp':
            # Set up C# project structure
            source_file = temp_path / "Program.cs"
            project_file = temp_path / "program.csproj"

            # Write source code
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
                # First restore packages
                logger.info("Restoring NuGet packages...")
                restore_cmd = ['dotnet', 'restore', str(project_file)]
                restore_process = subprocess.run(
                    restore_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(temp_path)
                )

                if restore_process.returncode != 0:
                    logger.error(f"Package restore failed: {restore_process.stderr}")
                    return {
                        'success': False,
                        'error': f"Package restore failed: {restore_process.stderr}",
                        'metrics': metrics
                    }

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
                    logger.error(f"Compilation failed: {compile_process.stderr}")
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr),
                        'metrics': metrics
                    }

                # Run the compiled program
                dll_path = temp_path / "bin" / "Release" / "net7.0" / "program.dll"
                if not dll_path.exists():
                    logger.error(f"No executable found in {dll_path.parent}")
                    return {
                        'success': False,
                        'error': "Build succeeded but no executable found",
                        'metrics': metrics
                    }

                logger.info("Running program...")
                run_cmd = ['dotnet', str(dll_path)]
                run_process = subprocess.run(
                    run_cmd,
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path)
                )

                metrics['execution_time'] = time.time() - (metrics['start_time'] + metrics['compilation_time'])
                metrics['total_time'] = time.time() - metrics['start_time']

                if run_process.returncode != 0:
                    logger.error(f"Execution failed: {run_process.stderr}")
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

# Initialize session management
active_sessions = {}
session_lock = Lock()

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
        return 'cin' in code_lower or 'getline' in code_lower
    elif language == 'csharp':
        return 'console.readline' in code_lower or 'console.read' in code_lower or 'readkey' in code_lower
    return False  # Default case for unsupported languages

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session for the given code"""
    try:
        logger.debug(f"Starting interactive session for {language}")
        process = None

        # Set up files
        source_file = Path(session.temp_dir) / f"program.{language.lower()}"
        executable = Path(session.temp_dir) / ("program.exe" if language == "csharp" else "program")

        # Enhanced C# code preprocessing
        if language == 'csharp':
            # Don't wrap if code already contains namespace/class definition
            if 'namespace' in code or 'class Program' in code:
                modified_code = code
            else:
                modified_code = f"""using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Globalization;

namespace ConsoleApplication {{
    class Program {{
        static void Main(string[] args) {{
            try {{
                CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
                {code}
            }}
            catch (Exception e) {{
                Console.WriteLine($"Runtime Error: {{e.Message}}");
            }}
        }}
    }}
}}"""

            # Write the code with proper encoding
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(modified_code)

            # Enhanced compilation command with proper references
            compile_cmd = [
                'dotnet',
                'build',
                str(source_file),
                '-o',
                str(executable.parent),
                '/p:GenerateFullPaths=true',
                '/consoleloggerparameters:NoSummary'
            ]

            try:
                start_time = time.time()
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60  # Increased timeout for larger codebases
                )
                compilation_time = time.time() - start_time

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr)
                    }

                # Set executable permissions
                os.chmod(executable, 0o755)

                # Enhanced environment for better console handling
                env = os.environ.copy()
                env['MONO_IOMAP'] = 'all'
                env['MONO_TRACE_LISTENER'] = 'Console.Out'
                env['MONO_DEBUG'] = 'handle-sigint'
                env['MONO_THREADS_PER_CPU'] = '2'
                env['MONO_GC_PARAMS'] = 'mode=throughput'
                env['TERM'] = 'xterm'
                env['COLUMNS'] = '80'
                env['LINES'] = '25'

                # Run with dotnet, using Popen for interactive I/O
                process = subprocess.Popen(
                    ['dotnet', str(executable)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=env,
                    preexec_fn=os.setsid
                )

                session.process = process

                # Set up process monitor
                monitor = ProcessMonitor(process, timeout=300)  # Increased timeout for larger programs
                monitor.start()

                # Start monitoring thread for real-time output
                def monitor_output():
                    try:
                        while process.poll() is None:
                            readable, _, _ = select.select(
                                [process.stdout, process.stderr], [], [], 0.1)

                            for stream in readable:
                                line = stream.readline()
                                if line:
                                    if stream == process.stdout:
                                        session.stdout_buffer.append(line)
                                        logger.debug(f"Output: {line.strip()}")

                                        # Enhanced input prompt detection
                                        if any(prompt in line.lower() for prompt in [
                                            'input', 'enter', 'type', '?', ':', '>',
                                            'choix', 'votre choix', 'choisir', 'entrer',
                                            'saisir', 'tapez', 'press', 'continue'
                                        ]):
                                            session.waiting_for_input = True
                                            logger.debug("Waiting for input")
                                    else:
                                        session.stderr_buffer.append(line)
                                        logger.debug(f"Error: {line.strip()}")
                                    session.last_activity = time.time()

                    except Exception as e:
                        logger.error(f"Error in monitor_output: {e}")
                    finally:
                        monitor.stop()
                        cleanup_session(session.session_id)

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
                if process:
                    cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': "Compilation timeout"
                }
            except Exception as e:
                if process:
                    cleanup_session(session.session_id)
                logger.error(f"Error executing C# code: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }

        elif language == 'cpp':
            # C++ specific implementation
            return {
                'success': False,
                'error': "C++ interactive mode not implemented"
            }

    except Exception as e:
        logger.error(f"Error in start_interactive_session: {e}")
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