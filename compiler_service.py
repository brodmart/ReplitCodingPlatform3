"""
Compiler service for code execution and testing.
Enhanced for large code files and interactive console support with detailed logging.
"""
import os
import subprocess
import logging
import tempfile
import traceback
import signal
import psutil
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
import time
from threading import Thread, Event, Lock
import select
import io
import shutil

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s'
)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 60
MAX_EXECUTION_TIME = 30
MEMORY_LIMIT = 1024  # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"

# Ensure compiler cache directory exists with proper permissions
os.makedirs(COMPILER_CACHE_DIR, mode=0o755, exist_ok=True)

def compile_csharp(source_file: Path, executable: Path, metrics: Dict) -> Tuple[bool, str]:
    """Compile C# code with detailed error logging"""
    try:
        logger.debug(f"Setting up C# project in directory: {source_file.parent}")

        # Create project structure
        project_dir = source_file.parent
        project_file = project_dir / "temp.csproj"

        # Enhanced project file with proper settings
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
    <PublishReadyToRun>true</PublishReadyToRun>
    <SelfContained>false</SelfContained>
    <DebugType>embedded</DebugType>
  </PropertyGroup>
</Project>"""

        logger.debug(f"Creating project file: {project_file}")
        with open(project_file, 'w') as f:
            f.write(project_content)

        # Log source code size
        source_size = os.path.getsize(source_file)
        logger.debug(f"Source code size: {source_size} bytes")

        compile_cmd = [
            'dotnet',
            'build',
            str(project_file),
            '-o',
            str(executable.parent),
            '/p:GenerateFullPaths=true',
            '/consoleloggerparameters:NoSummary',
            '/p:DebugSymbols=false',
            '/p:DebugType=None'
        ]

        logger.debug(f"Starting C# compilation with command: {' '.join(compile_cmd)}")
        compile_start = time.time()

        try:
            # Set up enhanced compilation environment
            env = os.environ.copy()
            env.update({
                'DOTNET_CLI_HOME': str(project_dir),
                'DOTNET_NOLOGO': '1',
                'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
                'DOTNET_ROLL_FORWARD': 'Major',
                'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT': '1'
            })

            compile_process = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=str(project_dir),
                env=env
            )

            compile_time = time.time() - compile_start
            metrics['compilation_time'] = compile_time
            logger.debug(f"Compilation completed in {compile_time:.2f}s")

            if compile_process.returncode != 0:
                error_msg = compile_process.stderr if compile_process.stderr else "Unknown compilation error occurred"
                logger.error(f"Compilation failed with return code {compile_process.returncode}")
                logger.error(f"Compilation error: {error_msg}")
                return False, format_csharp_error(error_msg)

            logger.debug("Compilation successful")
            return True, ""

        except subprocess.TimeoutExpired:
            error_msg = f"Compilation timed out after {MAX_COMPILATION_TIME} seconds"
            logger.error(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Fatal compilation error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def format_csharp_error(error_msg: str) -> str:
    """Format C# compilation errors to be more user-friendly"""
    try:
        if "error CS" in error_msg:
            parts = error_msg.split("): ")
            if len(parts) > 1:
                error_code = parts[0].split("error CS")[1].strip()
                error_desc = parts[1].strip()
                line_num = error_msg.split('(')[1].split(',')[0]

                common_errors = {
                    "1525": "Code structure issue. Check for missing semicolons or braces.",
                    "1002": "Missing closing curly brace '}'",
                    "1001": "Missing opening curly brace '{'",
                    "0117": "Method must have a return type. Did you forget 'void' or 'int'?",
                    "0161": "'Console.WriteLine' can only be used inside a method",
                    "0103": "Name does not exist in current context. Check for typos.",
                    "0234": "Missing using directive or assembly reference",
                    "0246": "Missing required namespace declaration"
                }

                friendly_msg = common_errors.get(error_code, error_desc)
                return f"Line {line_num}: {friendly_msg}"

        return error_msg
    except:
        return error_msg

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run code with enhanced error handling and logging"""
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        return {
            'success': False,
            'error': "No code or language specified",
            'metrics': metrics
        }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'csharp':
                # Set up project structure
                project_dir = Path(temp_dir)
                source_file = project_dir / "Program.cs"
                executable = project_dir / "bin/Debug/net7.0/program"

                logger.debug(f"Writing code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                success, error_msg = compile_csharp(source_file, executable, metrics)

                if not success:
                    return {
                        'success': False,
                        'error': error_msg,
                        'metrics': metrics
                    }

                try:
                    run_cmd = ['dotnet', str(executable)]
                    logger.debug(f"Running with command: {' '.join(run_cmd)}")

                    run_process = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        env={
                            'DOTNET_CLI_HOME': temp_dir,
                            'DOTNET_NOLOGO': '1',
                            'DOTNET_CLI_TELEMETRY_OPTOUT': '1'
                        }
                    )

                    metrics['execution_time'] = time.time() - metrics['start_time'] - metrics['compilation_time']

                    if run_process.returncode != 0:
                        logger.error(f"Execution failed with return code {run_process.returncode}")
                        logger.error(f"Error output: {run_process.stderr}")
                        return {
                            'success': False,
                            'error': format_runtime_error(run_process.stderr),
                            'metrics': metrics
                        }

                    logger.debug("Execution completed successfully")
                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'metrics': metrics
                    }

                except subprocess.TimeoutExpired:
                    error_msg = f"Execution timed out after {MAX_EXECUTION_TIME} seconds"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'metrics': metrics
                    }

            return {
                'success': False,
                'error': f"Unsupported language: {language}"
            }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"An unexpected error occurred: {str(e)}",
            'metrics': metrics
        }

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors to be more user-friendly"""
    try:
        common_errors = {
            "System.NullReferenceException": "Attempted to use a null object. Check if all variables are initialized.",
            "System.IndexOutOfRangeException": "Array index out of bounds. Check array access.",
            "System.DivideByZeroException": "Division by zero detected.",
            "System.StackOverflowException": "Stack overflow. Check for infinite recursion.",
            "System.OutOfMemoryException": "Out of memory. Reduce data size or optimize memory usage."
        }

        for error_type, message in common_errors.items():
            if error_type in error_msg:
                return f"Runtime Error: {message}"

        return f"Runtime Error: {error_msg}"
    except:
        return f"Runtime Error: {error_msg}"


def format_execution_error(error_msg: str) -> str:
    """Format general execution errors to be more user-friendly"""
    if "access denied" in error_msg.lower():
        return "Execution Error: Permission denied. The program doesn't have required permissions."
    elif "memory" in error_msg.lower():
        return "Execution Error: Out of memory. Try reducing the size of variables or arrays."
    elif "timeout" in error_msg.lower():
        return "Execution Error: Program took too long to execute. Check for infinite loops."
    return f"Execution Error: {error_msg}"

# Global session management
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
    return False

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
            if self.process.poll() is None:
                self.process.terminate()

    def stop(self):
        self.stopped.set()
        self._terminate_process()