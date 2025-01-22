import os
import pty
import select
import subprocess
import tempfile
import logging
import traceback
import signal
from typing import Dict, Optional, Any, List, Union
from pathlib import Path
import psutil
import time
import shutil
from threading import Lock, Thread, Event
import hashlib
import uuid
import fcntl
import termios
import struct
import errno
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 30    # seconds
MAX_EXECUTION_TIME = 30     # seconds
MEMORY_LIMIT = 1024        # MB
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

class CompilerSession:
    """Enhanced session handler for interactive compilation."""
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id: str = session_id
        self.temp_dir: str = temp_dir
        self.process: Optional[subprocess.Popen] = None
        self.last_activity: float = time.time()
        self.stdout_buffer: List[str] = []
        self.stderr_buffer: List[str] = []
        self.waiting_for_input: bool = False
        self.output_thread: Optional[Thread] = None
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.partial_line: str = ""  # Buffer for partial output lines

def create_pty() -> tuple[int, int]:
    """Create a new PTY pair with proper settings"""
    master_fd, slave_fd = pty.openpty()

    # Set raw mode on the master side
    term_attrs = termios.tcgetattr(master_fd)
    term_attrs[3] = term_attrs[3] & ~(termios.ECHO | termios.ICANON)  # Turn off ECHO and ICANON
    term_attrs[0] = term_attrs[0] | termios.BRKINT | termios.PARMRK  # Enable break and parity signals
    termios.tcsetattr(master_fd, termios.TCSANOW, term_attrs)

    # Set window size to ensure proper output formatting
    winsize = struct.pack("HHHH", 24, 80, 0, 0)  # rows, cols, xpixel, ypixel
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    # Set non-blocking mode
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    return master_fd, slave_fd

def clean_terminal_output(output: str) -> str:
    """Clean terminal control sequences from output with enhanced pattern matching"""
    # Remove ANSI color codes and control sequences
    cleaned = re.sub(r'\x1b\[[0-9;]*[mGKHf]', '', output)  # Enhanced ANSI pattern
    cleaned = re.sub(r'\x1b\[\??[0-9;]*[A-Za-z]', '', cleaned)  # Additional controls
    cleaned = re.sub(r'\x1b[=>]', '', cleaned)  # Terminal mode sequences

    # Clean C#-specific artifacts
    cleaned = re.sub(r'Microsoft.+?Copyright.+?\n', '', cleaned, flags=re.MULTILINE | re.DOTALL)
    cleaned = re.sub(r'Build started.+?Build succeeded.+?\n', '', cleaned, flags=re.MULTILINE | re.DOTALL)
    cleaned = re.sub(r'\[0K', '', cleaned)  # Remove EL (Erase in Line) sequences

    # Normalize line endings and whitespace
    cleaned = re.sub(r'\r\n?|\n\r', '\n', cleaned)  # Normalize line endings
    cleaned = re.sub(r'^\s*\n', '', cleaned)  # Remove empty lines at start
    cleaned = re.sub(r'\n\s*$', '\n', cleaned)  # Clean trailing whitespace
    cleaned = re.sub(r'\s*=\s*$', '', cleaned)  # Remove trailing equals signs
    cleaned = re.sub(r'[\n\r]+', '\n', cleaned)  # Collapse multiple newlines
    cleaned = re.sub(r'(?<=:)\s+(?=\w)', ' ', cleaned)  # Normalize spacing after colons

    # Handle C# specific prompt patterns
    cleaned = re.sub(r'Press any key to continue[.]*', '', cleaned)
    cleaned = re.sub(r'Type.+?to exit[.]*', '', cleaned)
    cleaned = re.sub(r'Microsoft \(R\).+?Runtime.+?\n', '', cleaned, flags=re.MULTILINE)

    # Clean up remaining control characters
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

    return cleaned.strip()

def monitor_output(process: subprocess.Popen, session: CompilerSession, chunk_size: int = 1024) -> None:
    """Enhanced output monitoring with proper buffer handling"""
    try:
        while process.poll() is None:
            readable = []
            if session.master_fd is not None:
                try:
                    readable, _, _ = select.select([session.master_fd], [], [], 0.1)
                except select.error:
                    break

            for fd in readable:
                try:
                    data = os.read(fd, chunk_size)
                    if data:
                        try:
                            decoded = data.decode('utf-8', errors='replace')
                            # Combine with any partial line from previous read
                            full_data = session.partial_line + decoded

                            # Split into lines, keeping the last partial line
                            lines = full_data.splitlines(True)  # Keep line endings
                            if lines:
                                if not full_data.endswith('\n'):
                                    session.partial_line = lines[-1]
                                    lines = lines[:-1]
                                else:
                                    session.partial_line = ""

                            # Process complete lines with enhanced input detection
                            for line in lines:
                                cleaned = clean_terminal_output(line)
                                if cleaned:  # Only append non-empty output
                                    session.stdout_buffer.append(cleaned)
                                    logger.debug(f"Raw output received: {cleaned}")

                                    # Enhanced input prompt detection
                                    if not session.waiting_for_input:
                                        # Get recent output for context
                                        recent_output = ''.join(session.stdout_buffer[-3:]).lower()

                                        # Common input patterns
                                        input_patterns = [
                                            'input', 'enter', 'type', '?', ':', '>',
                                            'choice', 'select', 'press', 'continue',
                                            'name', 'age', 'value'
                                        ]

                                        # Check for input patterns
                                        is_input_prompt = (
                                            any(pattern in recent_output for pattern in input_patterns) or
                                            recent_output.rstrip().endswith(':') or
                                            recent_output.rstrip().endswith('> ') or
                                            (recent_output.count('\n') == 0 and 
                                             any(char in recent_output for char in '?:>'))
                                        )

                                        if is_input_prompt:
                                            session.waiting_for_input = True
                                            logger.debug(f"Input prompt detected in: {recent_output}")

                        except Exception as e:
                            logger.error(f"Error processing output: {e}")
                            continue
                except (OSError, IOError) as e:
                    if e.errno != errno.EAGAIN:
                        logger.error(f"Error reading from PTY: {e}")
                        break
                    continue

            # Check stderr separately using read instead of read1
            if process.stderr:
                try:
                    stderr_data = process.stderr.read(chunk_size)
                    if stderr_data:
                        try:
                            decoded = stderr_data.decode('utf-8', errors='replace')
                            cleaned = clean_terminal_output(decoded)
                            if cleaned:  # Only append non-empty output
                                session.stderr_buffer.append(cleaned)
                                logger.debug(f"Stderr received: {cleaned}")
                        except Exception as e:
                            logger.error(f"Error processing stderr: {e}")
                except Exception as e:
                    logger.error(f"Error reading stderr: {e}")

            time.sleep(0.05)  # Small delay to prevent CPU overuse
            session.last_activity = time.time()

    except Exception as e:
        logger.error(f"Error in monitor_output: {traceback.format_exc()}")
    finally:
        # Process any remaining partial line
        if session.partial_line:
            cleaned = clean_terminal_output(session.partial_line)
            if cleaned:
                session.stdout_buffer.append(cleaned)
                logger.debug(f"Final partial line: {cleaned}")

        # Ensure we collect any remaining output
        try:
            if session.master_fd is not None:
                while True:
                    try:
                        data = os.read(session.master_fd, chunk_size)
                        if data:
                            decoded = data.decode('utf-8', errors='replace')
                            cleaned = clean_terminal_output(decoded)
                            if cleaned:  # Only append non-empty output
                                session.stdout_buffer.append(cleaned)
                                logger.debug(f"Final output received: {cleaned}")
                    except (OSError, IOError):
                        break
        except Exception as e:
            logger.error(f"Error collecting final output: {e}")

        if session.master_fd is not None:
            try:
                os.close(session.master_fd)
                logger.debug("Closed master PTY in monitor_output")
            except:
                pass

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with improved isolation and I/O handling"""
    try:
        logger.info(f"Starting interactive session for {language}")
        logger.debug(f"Session ID: {session.session_id}")

        # Create isolated environment
        temp_dir, project_name = create_isolated_environment(code, language)
        session.temp_dir = str(temp_dir)

        if language == 'cpp':
            # Write code to temp file
            source_file = Path(session.temp_dir) / "program.cpp"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Enhanced compilation command with better error handling
            executable = Path(session.temp_dir) / "program"
            compile_process = subprocess.run(
                ['g++', '-std=c++17', '-O2', '-Wall', str(source_file), '-o', str(executable)],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME
            )

            if compile_process.returncode != 0:
                error_msg = compile_process.stderr
                logger.error(f"C++ compilation failed: {error_msg}")
                cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': f"Compilation Error: {error_msg}"
                }

            executable.chmod(0o755)

            # Create PTY for interactive I/O
            master_fd, slave_fd = create_pty()
            session.master_fd = master_fd
            session.slave_fd = slave_fd
            logger.debug(f"PTY created: master_fd={master_fd}, slave_fd={slave_fd}")

            # Start the program with PTY support
            try:
                process = subprocess.Popen(
                    [str(executable)],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    text=True,
                    cwd=str(session.temp_dir),
                    env={"TERM": "xterm-256color"}
                )

                os.close(slave_fd)  # Close slave fd after process start
                session.process = process
                logger.debug(f"Process started with PID: {process.pid}")

                # Start output monitoring
                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()
                logger.debug("Output monitoring thread started")

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True
                }

            except Exception as e:
                logger.error(f"Error starting C++ process: {e}")
                cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': f"Process Error: {str(e)}"
                }

        elif language == 'csharp':
            try:
                project_file = Path(session.temp_dir) / f"{project_name}.csproj"

                # Compile with better error handling
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

                if compile_process.returncode != 0:
                    error_msg = compile_process.stderr
                    logger.error(f"C# compilation failed: {error_msg}")
                    cleanup_session(session.session_id)
                    return {
                        'success': False,
                        'error': f"Compilation Error: {error_msg}"
                    }

                # Create PTY for interactive I/O
                master_fd, slave_fd = create_pty()
                session.master_fd = master_fd
                session.slave_fd = slave_fd
                logger.debug(f"PTY created for C#: master_fd={master_fd}, slave_fd={slave_fd}")

                # Start the program with PTY support
                dll_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / f"{project_name}.dll"
                process = subprocess.Popen(
                    ['dotnet', str(dll_path)],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    text=True,
                    cwd=str(session.temp_dir),
                    env={
                        **os.environ,
                        'DOTNET_CONSOLE_ENCODING': 'utf-8',
                        'TERM': 'xterm-256color',
                        'DOTNET_SYSTEM_CONSOLE_ALLOW_ANSI_COLOR_REDIRECTION': 'true'
                    }
                )

                time.sleep(0.5)

                os.close(slave_fd)  # Close slave fd after process start
                session.process = process
                logger.debug(f"C# Process started with PID: {process.pid}")

                # Start output monitoring
                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()
                logger.debug("Output monitoring thread started")

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True
                }

            except subprocess.TimeoutExpired:
                cleanup_session(session.session_id)
                logger.error("C# compilation timed out")
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
        if session.session_id in active_sessions:
            cleanup_session(session.session_id)
        logger.error(f"Error in start_interactive_session: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

def send_input(session_id: str, input_data: str) -> Dict[str, Any]:
    """Send input to an interactive session with improved error handling"""
    if session_id not in active_sessions:
        logger.error(f"Invalid session ID: {session_id}")
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    logger.debug(f"Sending input to session {session_id}: {input_data}")

    try:
        if session.process and session.process.poll() is None:
            if session.master_fd is not None:
                input_bytes = (input_data + '\n').encode('utf-8')
                bytes_written = os.write(session.master_fd, input_bytes)
                session.waiting_for_input = False
                logger.debug(f"Input sent to process: {input_data} ({bytes_written} bytes)")
                return {'success': True}
            else:
                logger.error("PTY not available")
                return {'success': False, 'error': 'PTY not available'}
        else:
            logger.error("Process not running")
            return {'success': False, 'error': 'Process not running'}
    except Exception as e:
        logger.error(f"Error sending input: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from an interactive session with improved error handling"""
    if session_id not in active_sessions:
        logger.error(f"Invalid session ID: {session_id}")
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    try:
        if not session.process:
            logger.error("No active process")
            return {'success': False, 'error': 'No active process'}

        # Ensure we give the process time to produce output
        time.sleep(0.1)

        # Check if process has ended
        if session.process.poll() is not None:
            output = ''.join(session.stdout_buffer)
            logger.debug(f"Process ended, final output: {output}")
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
        # Keep the buffer for context but remove already processed output
        if len(session.stdout_buffer) > 10:
            session.stdout_buffer = session.stdout_buffer[-10:]

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
    """Clean up resources for a session with proper PTY cleanup"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        logger.debug(f"Cleaning up session {session_id}")
        try:
            if session.process and session.process.poll() is None:
                try:
                    group_id = os.getpgid(session.process.pid)
                    os.killpg(group_id, signal.SIGTERM)
                    logger.debug(f"Sent SIGTERM to process group {group_id}")
                except:
                    session.process.terminate()
                    logger.debug("Sent terminate signal to process")

                try:
                    session.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    session.process.kill()
                    session.process.wait()
                    logger.debug("Process killed after timeout")

            if session.master_fd is not None:
                try:
                    os.close(session.master_fd)
                    logger.debug("Closed master PTY")
                except:
                    pass

            if os.path.exists(session.temp_dir):
                shutil.rmtree(session.temp_dir, ignore_errors=True)
                logger.debug(f"Removed temporary directory: {session.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
        finally:
            with session_lock:
                del active_sessions[session_id]
                logger.debug(f"Removed session {session_id} from active_sessions")

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

# Initialize session management
active_sessions = {}
session_lock = Lock()

def create_isolated_environment(code: str, language: str) -> tuple[Path, str]:
    """Create an isolated environment for compilation and execution"""
    # Create unique directory for this compilation
    unique_id = str(uuid.uuid4())[:8]  # Use shorter ID for path length
    temp_dir = Path(COMPILER_CACHE_DIR) / f"compile_{unique_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if language == 'csharp':
        # Create isolated project structure
        project_name = f"Project_{unique_id}"
        source_file = temp_dir / "Program.cs"
        project_file = temp_dir / f"{project_name}.csproj"

        # Write source code
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Create optimized project file
        project_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <AssemblyName>{project_name}</AssemblyName>
    <RootNamespace>{project_name}</RootNamespace>
  </PropertyGroup>
</Project>"""
        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(project_content)

        return temp_dir, project_name

    elif language == 'cpp':
        # Create isolated C++ environment
        source_file = temp_dir / "program.cpp"
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)
        return temp_dir, "program"
    else:
        raise ValueError(f"Unsupported language: {language}")


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

    try:
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
                logger.error(f"Error in interactive session: {str(e)}\n{traceback.format_exc()}")
                cleanup_session(session_id)
                return {
                    'success': False,
                    'error': f"Interactive session error: {str(e)}",
                    'metrics': metrics
                }

        # Create isolated environment for compilation
        temp_dir, project_name = create_isolated_environment(code, language)

        if language == 'cpp':
            # Set up C++ compilation
            source_file = os.path.join(temp_dir, "program.cpp")
            executable = os.path.join(temp_dir, "program")

            # Enhanced compilation command with optimizations
            compile_cmd = [
                'g++',
                '-std=c++17',  # Use modern C++
                '-O2',         # Optimize
                '-Wall',       # Enable warnings
                '-pipe',
                source_file,
                '-o',
                executable
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
                os.chmod(executable, 0o755)

                # Run the compiled program
                run_process = subprocess.run(
                    [executable],
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
            try:
                project_file = os.path.join(temp_dir, f"{project_name}.csproj")

                # Compile with better error handling
                compile_cmd = [
                    'dotnet', 'build',
                    project_file,
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
                    cwd=temp_dir
                )

                if compile_process.returncode != 0:
                    logger.error(f"C# compilation failed: {compile_process.stderr}")
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr),
                        'metrics': metrics
                    }

                # Run the compiled program
                dll_path = os.path.join(temp_dir, "bin", "Release", "net7.0", f"{project_name}.dll")
                if not os.path.exists(dll_path):
                    logger.error(f"DLL not found at {dll_path}")
                    return {
                        'success': False,
                        'error': "Build succeeded but executable not found",
                        'metrics': metrics
                    }

                logger.info("Running program...")
                run_process = subprocess.run(
                    ['dotnet', dll_path],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=temp_dir,
                    env={**os.environ, 'DOTNET_CONSOLE_ENCODING': 'utf-8'}
                )

                if run_process.returncode != 0:
                    logger.error(f"C# runtime error: {run_process.stderr}")
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

            except subprocess.TimeoutExpired:
                phase = "compilation" if time.time() - metrics['start_time'] < MAX_COMPILATION_TIME else "execution"
                error_msg = f"{phase.capitalize()} timed out after {MAX_COMPILATION_TIME if phase == 'compilation' else MAX_EXECUTION_TIME} seconds"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'metrics': metrics
                }
            except Exception as e:
                logger.error(f"Unexpected C# error: {str(e)}\n{traceback.format_exc()}")
                return {
                    'success': False,
                    'error': f"Unexpected error: {str(e)}",
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
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")

def format_csharp_error(error_msg: str) -> str:
    """Enhanced error message formatting for C# compiler errors"""
    if not error_msg:
        return "Unknown error occurred"

    error_lines = []

    # Split into lines and process each one
    for line in error_msg.splitlines():
        # Look for compiler error pattern: file(line,col): error CSxxxx: message
        if "error CS" in line:
            try:
                # Extract error code and message
                error_parts = line.split("error CS")
                if len(error_parts) > 1:
                    error_code = error_parts[1].split(':', 1)[0]
                    error_message = error_parts[1].split(':', 1)[1].strip()
                    # Clean up the file path and line numbers
                    error_message = re.sub(r'\[.+?\]', '', error_message)
                    error_lines.append(f"Compilation Error (CS{error_code}): {error_message}")
            except Exception as e:
                logger.error(f"Error parsing compiler message: {e}")
                error_lines.append(f"Compilation Error: {line.strip()}")

        # Also capture build errors that don't follow the CS#### pattern
        elif any(pattern in line.lower() for pattern in ["error:", "fatal error:", "build failed"]):
            error_lines.append(f"Compilation Error: {line.strip()}")

    # If no specific error was found, include the original message
    if not error_lines:
        # Look for any error-like content in the original message
        general_error = re.search(r'(?:error|exception|failed).*$', error_msg, re.IGNORECASE | re.MULTILINE)
        if general_error:
            error_lines.append(f"Compilation Error: {general_error.group(0).strip()}")
        else:
            error_lines.append(error_msg.strip())

    return "\n".join(error_lines)

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors with improved detail capture"""
    if not error_msg:
        return "Unknown runtime error occurred"

    error_lines = []
    stack_trace = []

    for line in error_msg.splitlines():
        # Capture exception type and message
        if "Exception:" in line:
            exception_match = re.search(r'([a-zA-Z.]+Exception:)\s*(.+)', line)
            if exception_match:
                exc_type, exc_msg = exception_match.groups()
                exc_type = exc_type.split('.')[-1]  # Get just the exception name
                error_lines.append(f"Runtime Error ({exc_type.rstrip(':')}) - {exc_msg.strip()}")

        # Capture stack trace information (limit to 3 lines)
        elif line.strip().startswith("at ") and len(stack_trace) < 3:
            # Clean up stack trace line
            trace_line = re.sub(r'at\s+', '', line.strip())
            trace_line = re.sub(r'\s+in\s+.+?:\w+\s*$', '', trace_line)
            stack_trace.append(f"Location: {trace_line}")

    # If no exception was found, look for other error indicators
    if not error_lines:
        for line in error_msg.splitlines():
            if any(pattern in line.lower() for pattern in ["error", "failed", "fault", "invalid"]):
                error_lines.append(f"Runtime Error: {line.strip()}")
                break

    # Combine error message with relevant stack trace
    result = error_lines + stack_trace if error_lines else ["Runtime Error: " + error_msg.strip()]
    return "\n".join(result)

def is_interactive_code(code: str, language: str) -> bool:
    """Determine if code requires interactive I/O based on language-specific patterns."""
    code = code.lower()

    if language == 'cpp':
        # Check for common C++ input patterns
        return any(pattern in code for pattern in [
            'cin', 'getline',
            'std::cin', 'std::getline',
            'scanf', 'gets', 'fgets'
        ])
    elif language == 'csharp':
        # Check for common C# input patterns
        return any(pattern in code for pattern in [
            'console.read', 'console.readline',
            'console.in', 'console.keyavailable',
            'console.readkey'
        ])
    return False

# Adding enhanced isolation support
import uuid
import shutil
from pathlib import Path

def create_isolated_environment(code: str, language: str) -> tuple[Path, str]:
    """Create an isolated environment for compilation and execution"""
    # Create unique directory for this compilation
    unique_id = str(uuid.uuid4())[:8]  # Use shorter ID for path length
    temp_dir = Path(COMPILER_CACHE_DIR) / f"compile_{unique_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if language == 'csharp':
        # Create isolated project structure
        project_name = f"Project_{unique_id}"
        source_file = temp_dir / "Program.cs"
        project_file = temp_dir / f"{project_name}.csproj"

        # Write source code
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Create optimized project file
        project_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <AssemblyName>{project_name}</AssemblyName>
    <RootNamespace>{project_name}</RootNamespace>
  </PropertyGroup>
</Project>"""
        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(project_content)

        return temp_dir, project_name

    elif language == 'cpp':
        # Create isolated C++ environment
        source_file = temp_dir / "program.cpp"
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)
        return temp_dir, "program"
    else:
        raise ValueError(f"Unsupported language: {language}")

# Update the start_interactive_session function to use isolated environment
def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with improved isolation and I/O handling"""
    try:
        logger.info(f"Starting interactive session for {language}")
        logger.debug(f"Session ID: {session.session_id}")

        # Create isolated environment
        temp_dir, project_name = create_isolated_environment(code, language)
        session.temp_dir = str(temp_dir)

        if language == 'cpp':
            # Write code to temp file
            source_file = Path(session.temp_dir) / "program.cpp"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Enhanced compilation command with better error handling
            executable = Path(session.temp_dir) / "program"
            compile_process = subprocess.run(
                ['g++', '-std=c++17', '-O2', '-Wall', str(source_file), '-o', str(executable)],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME
            )

            if compile_process.returncode != 0:
                error_msg = compile_process.stderr
                logger.error(f"C++ compilation failed: {error_msg}")
                cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': f"Compilation Error: {error_msg}"
                }

            executable.chmod(0o755)

            # Create PTY for interactive I/O
            master_fd, slave_fd = create_pty()
            session.master_fd = master_fd
            session.slave_fd = slave_fd
            logger.debug(f"PTY created: master_fd={master_fd}, slave_fd={slave_fd}")

            # Start the program with PTY support
            try:
                process = subprocess.Popen(
                    [str(executable)],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    text=True,
                    cwd=str(session.temp_dir),
                    env={"TERM": "xterm-256color"}
                )

                os.close(slave_fd)  # Close slave fd after process start
                session.process = process
                logger.debug(f"Process started with PID: {process.pid}")

                # Start output monitoring
                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()
                logger.debug("Output monitoring thread started")

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True
                }

            except Exception as e:
                logger.error(f"Error starting C++ process: {e}")
                cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': f"Process Error: {str(e)}"
                }

        elif language == 'csharp':
            try:
                project_file = Path(session.temp_dir) / f"{project_name}.csproj"

                # Compile with better error handling
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

                if compile_process.returncode != 0:
                    error_msg = compile_process.stderr
                    logger.error(f"C# compilation failed: {error_msg}")
                    cleanup_session(session.session_id)
                    return {
                        'success': False,
                        'error': f"Compilation Error: {error_msg}"
                    }

                # Create PTY for interactive I/O
                master_fd, slave_fd = create_pty()
                session.master_fd = master_fd
                session.slave_fd = slave_fd
                logger.debug(f"PTY created for C#: master_fd={master_fd}, slave_fd={slave_fd}")

                # Start the program with PTY support
                dll_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / f"{project_name}.dll"
                process = subprocess.Popen(
                    ['dotnet', str(dll_path)],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    text=True,
                    cwd=str(session.temp_dir),
                    env={
                        **os.environ,
                        'DOTNET_CONSOLE_ENCODING': 'utf-8',
                        'TERM': 'xterm-256color',
                        'DOTNET_SYSTEM_CONSOLE_ALLOW_ANSI_COLOR_REDIRECTION': 'true'
                    }
                )

                time.sleep(0.5)

                os.close(slave_fd)  # Close slave fd after process start
                session.process = process
                logger.debug(f"C# Process started with PID: {process.pid}")

                # Start output monitoring
                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()
                logger.debug("Output monitoring thread started")

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True
                }

            except subprocess.TimeoutExpired:
                cleanup_session(session.session_id)
                logger.error("C# compilation timed out")
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
        if session.session_id in active_sessions:
            cleanup_session(session.session_id)
        logger.error(f"Error in start_interactive_session: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

def send_input(session_id: str, input_data: str) -> Dict[str, Any]:
    """Send input to an interactive session with improved error handling"""
    if session_id not in active_sessions:
        logger.error(f"Invalid session ID: {session_id}")
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    logger.debug(f"Sending input to session {session_id}: {input_data}")

    try:
        if session.process and session.process.poll() is None:
            if session.master_fd is not None:
                input_bytes = (input_data + '\n').encode('utf-8')
                bytes_written = os.write(session.master_fd, input_bytes)
                session.waiting_for_input = False
                logger.debug(f"Input sent to process: {input_data} ({bytes_written} bytes)")
                return {'success': True}
            else:
                logger.error("PTY not available")
                return {'success': False, 'error': 'PTY not available'}
        else:
            logger.error("Process not running")
            return {'success': False, 'error': 'Process not running'}
    except Exception as e:
        logger.error(f"Error sending input: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from an interactive session with improved error handling"""
    if session_id not in active_sessions:
        logger.error(f"Invalid session ID: {session_id}")
        return {'success': False, 'error': 'Invalid session'}

    session = active_sessions[session_id]
    try:
        if not session.process:
            logger.error("No active process")
            return {'success': False, 'error': 'No active process'}

        # Ensure we give the process time to produce output
        time.sleep(0.1)

        # Check if process has ended
        if session.process.poll() is not None:
            output = ''.join(session.stdout_buffer)
            logger.debug(f"Process ended, final output: {output}")
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
        # Keep the buffer for context but remove already processed output
        if len(session.stdout_buffer) > 10:
            session.stdout_buffer = session.stdout_buffer[-10:]

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
    """Clean up resources for a session with proper PTY cleanup"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        logger.debug(f"Cleaning up session {session_id}")
        try:
            if session.process and session.process.poll() is None:
                try:
                    group_id = os.getpgid(session.process.pid)
                    os.killpg(group_id, signal.SIGTERM)
                    logger.debug(f"Sent SIGTERM to process group {group_id}")
                except:
                    session.process.terminate()
                    logger.debug("Sent terminate signal to process")

                try:
                    session.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    session.process.kill()
                    session.process.wait()
                    logger.debug("Process killed after timeout")

            if session.master_fd is not None:
                try:
                    os.close(session.master_fd)
                    logger.debug("Closed master PTY")
                except:
                    pass

            if os.path.exists(session.temp_dir):
                shutil.rmtree(session.temp_dir, ignore_errors=True)
                logger.debug(f"Removed temporary directory: {session.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
        finally:
            with session_lock:
                del active_sessions[session_id]
                logger.debug(f"Removed session {session_id} from active_sessions")

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

# Initialize session management
active_sessions = {}
session_lock = Lock()

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

    try:
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
                logger.error(f"Error in interactive session: {str(e)}\n{traceback.format_exc()}")
                cleanup_session(session_id)
                return {
                    'success': False,
                    'error': f"Interactive session error: {str(e)}",
                    'metrics': metrics
                }

        # Create isolated environment for compilation
        temp_dir, project_name = create_isolated_environment(code, language)

        if language == 'cpp':
            # Set up C++ compilation
            source_file = os.path.join(temp_dir, "program.cpp")
            executable = os.path.join(temp_dir, "program")

            # Enhanced compilation command with optimizations
            compile_cmd = [
                'g++',
                '-std=c++17',  # Use modern C++
                '-O2',         # Optimize
                '-Wall',       # Enable warnings
                '-pipe',
                source_file,
                '-o',
                executable
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
                os.chmod(executable, 0o755)

                # Run the compiled program
                run_process = subprocess.run(
                    [executable],
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
            try:
                project_file = os.path.join(temp_dir, f"{project_name}.csproj")

                # Compile with better error handling
                compile_cmd = [
                    'dotnet', 'build',
                    project_file,
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
                    cwd=temp_dir
                )

                if compile_process.returncode != 0:
                    logger.error(f"C# compilation failed: {compile_process.stderr}")
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr),
                        'metrics': metrics
                    }

                # Run the compiled program
                dll_path = os.path.join(temp_dir, "bin", "Release", "net7.0", f"{project_name}.dll")
                if not os.path.exists(dll_path):
                    logger.error(f"DLL not found at {dll_path}")
                    return {
                        'success': False,
                        'error': "Build succeeded but executable not found",
                        'metrics': metrics
                    }

                logger.info("Running program...")
                run_process = subprocess.run(
                    ['dotnet', dll_path],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=temp_dir,
                    env={**os.environ, 'DOTNET_CONSOLE_ENCODING': 'utf-8'}
                )

                if run_process.returncode != 0:
                    logger.error(f"C# runtime error: {run_process.stderr}")
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

            except subprocess.TimeoutExpired:
                phase = "compilation" if time.time() - metrics['start_time'] < MAX_COMPILATION_TIME else "execution"
                error_msg = f"{phase.capitalize()} timed out after {MAX_COMPILATION_TIME if phase == 'compilation' else MAX_EXECUTION_TIME} seconds"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'metrics': metrics
                }
            except Exception as e:
                logger.error(f"Unexpected C# error: {str(e)}\n{traceback.format_exc()}")
                return {
                    'success': False,
                    'error': f"Unexpected error: {str(e)}",
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
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")