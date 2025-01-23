import os
import signal
import logging
import tempfile
import threading
import subprocess
import time
import fcntl
import errno
import select
from typing import Dict, Any, Optional, List, Union
from threading import Lock, Thread, Event
from pathlib import Path
import psutil
from datetime import datetime
import traceback
import uuid
import shutil
from dataclasses import dataclass, field, asdict
import json
import re
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)
error_logger = logging.getLogger('error')
compiler_logger = logging.getLogger('compiler')
process_logger = logging.getLogger('process')
performance_logger = logging.getLogger('performance')
# Add new logging handler for process management
process_mgmt_logger = logging.getLogger('process_management')
process_mgmt_logger.setLevel(logging.DEBUG)

# Add new loggers for specific components
socketio_logger = logging.getLogger('socketio')
console_logger = logging.getLogger('console')
io_logger = logging.getLogger('io')
build_logger = logging.getLogger('build')
runtime_logger = logging.getLogger('runtime')
dll_logger = logging.getLogger('dll')
resource_logger = logging.getLogger('resource')


# Constants for timeouts and limits
PROCESS_SPAWN_TIMEOUT = 10  # seconds
COMPILATION_TIMEOUT = 30    # seconds
IO_TIMEOUT = 5             # seconds
BUFFER_SIZE = 4096
MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB

@dataclass
class CompilationError:
    """Structured compilation error information"""
    error_type: str
    message: str
    file: str
    line: int
    column: int
    code: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CompilationMetrics:
    """Enhanced compilation metrics tracking"""
    start_time: float
    end_time: float = 0.0
    compilation_time: float = 0.0
    execution_time: float = 0.0
    peak_memory: float = 0.0
    avg_cpu_usage: float = 0.0
    error_count: int = 0
    warning_count: int = 0
    cached: bool = False
    status_updates: List[Dict[str, Any]] = field(default_factory=list)
    successful_builds: int = 0
    total_builds: int = 0
    stage_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def start_stage(self, stage_name: str) -> None:
        """Track metrics for a specific compilation stage"""
        self.stage_metrics[stage_name] = {
            'start_time': time.time(),
            'peak_memory': 0.0,
            'cpu_usage': 0.0
        }
        self._update_system_metrics(stage_name)
        self.log_status(f"Starting {stage_name}")

    def end_stage(self, stage_name: str) -> None:
        """End tracking for a compilation stage"""
        if stage_name in self.stage_metrics:
            stage = self.stage_metrics[stage_name]
            stage['end_time'] = time.time()
            stage['duration'] = stage['end_time'] - stage['start_time']
            self._update_system_metrics(stage_name)
            self.log_status(f"Completed {stage_name} in {stage['duration']:.2f}s")

    def _update_system_metrics(self, stage_name: str) -> None:
        """Update system metrics for the current stage"""
        try:
            process = psutil.Process()
            stage = self.stage_metrics[stage_name]
            current_memory = process.memory_info().rss / (1024 * 1024)  # MB
            current_cpu = process.cpu_percent(interval=0.1)

            stage['peak_memory'] = max(stage.get('peak_memory', 0), current_memory)
            stage['cpu_usage'] = current_cpu

            # Update overall metrics
            self.peak_memory = max(self.peak_memory, current_memory)
            if not self.avg_cpu_usage:
                self.avg_cpu_usage = current_cpu
            else:
                self.avg_cpu_usage = (self.avg_cpu_usage + current_cpu) / 2
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def log_status(self, status: str) -> None:
        """Log a status update with timestamp and metrics"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        status_entry = {
            'timestamp': current_time,
            'elapsed': elapsed,
            'status': status,
            'memory_mb': psutil.Process().memory_info().rss / (1024 * 1024),
            'cpu_percent': psutil.Process().cpu_percent(interval=0.1)
        }
        self.status_updates.append(status_entry)
        performance_logger.debug(f"[{elapsed:.2f}s] {status}")

    def record_build(self, success: bool) -> None:
        """Record build attempt result"""
        self.total_builds += 1
        if success:
            self.successful_builds += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary with enhanced information"""
        total_time = self.end_time - self.start_time if self.end_time else time.time() - self.start_time
        return {
            'compilation_time': self.compilation_time,
            'execution_time': self.execution_time,
            'total_time': total_time,
            'peak_memory': self.peak_memory,
            'avg_cpu_usage': self.avg_cpu_usage,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'cached': self.cached,
            'build_success_rate': (self.successful_builds / self.total_builds * 100) if self.total_builds > 0 else 0,
            'stages': {
                name: {
                    'duration': metrics.get('duration', 0),
                    'peak_memory': metrics.get('peak_memory', 0),
                    'cpu_usage': metrics.get('cpu_usage', 0)
                }
                for name, metrics in self.stage_metrics.items()
            }
        }

@dataclass
class CompilerSession:
    """Manages a compilation/execution session"""
    session_id: str
    temp_dir: str
    process: Optional[subprocess.Popen] = None
    output_thread: Optional[Thread] = None
    output_buffer: List[str] = field(default_factory=list)
    waiting_for_input: bool = False
    stop_event: Event = field(default_factory=Event)
    master_fd: Optional[int] = None
    slave_fd: Optional[int] = None
    _access_lock: Lock = field(default_factory=Lock)
    _cleanup_lock: Lock = field(default_factory=Lock)
    _input_ready: Event = field(default_factory=Event)
    _last_input: Optional[str] = None

    def __post_init__(self):
        """Initialize the PTY after instance creation"""
        try:
            import pty
            self.master_fd, self.slave_fd = pty.openpty()
            # Set non-blocking mode on master
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            logger.debug(f"PTY initialized for session {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to initialize PTY: {e}")
            self.cleanup()
            raise

    def is_active(self) -> bool:
        """Check if the session is still active"""
        with self._access_lock:
            if self.process is None:
                return False
            try:
                # Check if process is still running
                if self.process.poll() is None:
                    # Check if process is zombie
                    if psutil.Process(self.process.pid).status() == psutil.STATUS_ZOMBIE:
                        logger.warning(f"Zombie process detected for session {self.session_id}")
                        return False
                    return not self.stop_event.is_set()
                return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False

    def append_output(self, text: str) -> None:
        """Thread-safe method to append output"""
        with self._access_lock:
            if len(''.join(self.output_buffer)) + len(text) > MAX_OUTPUT_SIZE:
                logger.warning("Output buffer size limit reached")
                self.stop_event.set()
                return

            self.output_buffer.append(text)
            lowercase_text = text.lower()
            # Don't treat echo of our last input as a prompt
            if (self._last_input is None or text.strip() != self._last_input.strip()) and \
               (any(prompt in lowercase_text for prompt in
                    ['input', 'enter', '?', ':', 'type', 'name']) or
                text.strip().endswith(':')):
                self.waiting_for_input = True
                self._input_ready.set()
                logger.debug(f"Input prompt detected: {text}")

    def get_output(self) -> List[str]:
        """Thread-safe method to get output"""
        with self._access_lock:
            output = self.output_buffer.copy()
            self.output_buffer.clear()
            return output

    def wait_for_input_prompt(self, timeout: float = 5.0) -> bool:
        """Wait for input prompt to appear"""
        return self._input_ready.wait(timeout)

    def set_last_input(self, input_text: str) -> None:
        """Set the last input to avoid echo detection as prompt"""
        self._last_input = input_text

    def cleanup(self) -> None:
        """Clean up session resources"""
        with self._cleanup_lock:
            logger.info(f"Starting cleanup for session {self.session_id}")
            self.stop_event.set()
            self._input_ready.set()

            # Clean up process
            if self.process:
                try:
                    if self.process.poll() is None:
                        try:
                            # Try getting the process group
                            pgid = os.getpgid(self.process.pid)
                            # Try graceful termination first
                            os.killpg(pgid, signal.SIGTERM)

                            # Wait for process to terminate
                            for _ in range(20):  # Wait up to 2 seconds
                                if self.process.poll() is not None:
                                    break
                                time.sleep(0.1)

                            # If still running, force kill
                            if self.process.poll() is None:
                                os.killpg(pgid, signal.SIGKILL)
                                self.process.wait(timeout=1)
                        except ProcessLookupError:
                            logger.debug(f"Process {self.process.pid} already terminated")
                        except Exception as e:
                            logger.error(f"Error during process cleanup: {e}")
                            # Fallback: try to kill just the process
                            try:
                                self.process.kill()
                                self.process.wait(timeout=1)
                            except Exception as kill_error:
                                logger.error(f"Failed to kill process: {kill_error}")
                except Exception as e:
                    logger.error(f"Error in process cleanup: {e}")

            # Clean up file descriptors
            for fd in [self.master_fd, self.slave_fd]:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as e:
                        if e.errno != errno.EBADF:  # Ignore "bad file descriptor" errors
                            logger.error(f"Error closing fd {fd}: {e}")

            # Clean up temp directory
            try:
                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning temp directory: {e}")

# Global session management
active_sessions: Dict[str, CompilerSession] = {}
session_lock = Lock()

def get_or_create_session(session_id: Optional[str] = None) -> CompilerSession:
    """Get existing session or create new one"""
    with session_lock:
        if session_id and session_id in active_sessions:
            session = active_sessions[session_id]
            if session.is_active():
                return session
            else:
                cleanup_session(session_id)

        new_session_id = session_id or str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp(prefix=f'compiler_test_{new_session_id}_')
        session = CompilerSession(new_session_id, temp_dir)
        active_sessions[new_session_id] = session
        return session

def cleanup_session(session_id: str) -> None:
    """Clean up session resources"""
    with session_lock:
        if session_id in active_sessions:
            session = active_sessions[session_id]
            session.cleanup()
            del active_sessions[session_id]
            logger.debug(f"Session {session_id} cleaned up")

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with improved process management and error handling"""
    socketio_logger.info(f"[SOCKET] Starting interactive session {session.session_id}")
    console_logger.info(f"[CONSOLE] Initializing console for session {session.session_id}")
    build_logger.info(f"[BUILD] Starting build process for session {session.session_id}")

    if language != 'csharp':
        return {'success': False, 'error': 'Only C# is supported'}

    try:
        # Set up project structure
        project_dir = Path(session.temp_dir)
        source_file = project_dir / "Program.cs"
        project_file = project_dir / "program.csproj"

        build_logger.debug(f"[BUILD] Creating project structure in {project_dir}")
        build_logger.debug(f"[BUILD] Source file: {source_file}")
        build_logger.debug(f"[BUILD] Project file: {project_file}")

        # Write project file with optimized settings
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
            <PropertyGroup>
                <OutputType>Exe</OutputType>
                <TargetFramework>net7.0</TargetFramework>
                <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
                <SelfContained>false</SelfContained>
                <UseAppHost>false</UseAppHost>
                <DebugType>portable</DebugType>
                <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
            </PropertyGroup>
        </Project>"""

        with open(project_file, 'w') as f:
            f.write(project_content)
            build_logger.debug("[BUILD] Project file created successfully")

        # Write source file
        with open(source_file, 'w') as f:
            f.write(code)
            build_logger.debug("[BUILD] Source file written successfully")

        # Compile with timeout and enhanced error handling
        build_logger.info("[BUILD] Starting compilation process")
        runtime_logger.debug(f"[RUNTIME] Environment setup: DOTNET_ROOT={os.environ.get('DOTNET_ROOT')}")

        try:
            compile_result = subprocess.run(
                ['dotnet', 'build', str(project_file), '--nologo', '-c', 'Release', '-v', 'detailed'],
                capture_output=True,
                text=True,
                timeout=COMPILATION_TIMEOUT,
                cwd=session.temp_dir,
                env={
                    **os.environ,
                    'DOTNET_ROOT': '/nix/store/4k08ckhym1bcwnsk52j201a80l2xrkhp-dotnet-sdk-7.0.410',
                    'DOTNET_CLI_HOME': session.temp_dir
                }
            )

            build_logger.debug(f"[BUILD] Compilation output: {compile_result.stdout}")
            if compile_result.stderr:
                build_logger.error(f"[BUILD] Compilation stderr: {compile_result.stderr}")
            build_logger.debug(f"[BUILD] Compilation return code: {compile_result.returncode}")

            if compile_result.returncode == 0:
                build_logger.info("[BUILD] Build successful")
            else:
                build_logger.error("[BUILD] Build failed")
                return {'success': False, 'error': compile_result.stderr}

        except subprocess.TimeoutExpired:
            build_logger.error("[BUILD] Compilation timed out")
            return {'success': False, 'error': 'Compilation timed out'}

        # Verify DLL location and existence
        dll_path = project_dir / "bin" / "Release" / "net7.0" / "linux-x64" / "program.dll"
        dll_logger.debug(f"[DLL] Looking for compiled DLL at: {dll_path}")

        if not os.path.exists(dll_path):
            dll_logger.error(f"[DLL] DLL not found at expected path: {dll_path}")
            # List contents of bin directory
            bin_dir = project_dir / "bin"
            if os.path.exists(bin_dir):
                dll_logger.debug("[DLL] Directory contents:")
                for root, dirs, files in os.walk(bin_dir):
                    dll_logger.debug(f"[DLL] Dir {root}: {files}")
            return {'success': False, 'error': 'Compiled DLL not found'}

        # PTY and process setup logging
        runtime_logger.info("[RUNTIME] Initializing process environment")
        resource_logger.debug(f"[RESOURCE] Process resources:")
        resource_logger.debug(f"[RESOURCE] - Working directory: {session.temp_dir}")
        resource_logger.debug(f"[RESOURCE] - Master FD: {session.master_fd}")
        resource_logger.debug(f"[RESOURCE] - Slave FD: {session.slave_fd}")

        def monitor_output():
            """Monitor process output with improved error handling"""
            buffer = ""
            io_logger.info("[IO] Starting output monitoring")
            try:
                while not session.stop_event.is_set() and session.process and session.process.poll() is None:
                    try:
                        rlist, _, _ = select.select([session.master_fd], [], [], 0.1)
                        if not rlist:
                            continue

                        chunk = os.read(session.master_fd, BUFFER_SIZE).decode(errors='replace')
                        io_logger.debug(f"[IO] Raw output: {chunk.strip()}")
                        buffer += chunk

                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            cleaned = clean_terminal_output(line)
                            if cleaned:
                                io_logger.debug(f"[IO] Cleaned output: {cleaned}")
                                session.append_output(cleaned + '\n')

                    except (OSError, IOError) as e:
                        if e.errno != errno.EAGAIN:
                            io_logger.error(f"[IO] Read error: {e}")
                            break
                        continue
                    except Exception as e:
                        io_logger.error(f"[IO] Monitor error: {e}")
                        break

                if buffer:  # Process remaining buffer
                    cleaned = clean_terminal_output(buffer)
                    if cleaned:
                        io_logger.debug(f"[IO] Final output: {cleaned}")
                        session.append_output(cleaned + '\n')

            except Exception as e:
                io_logger.error(f"[IO] Fatal error: {traceback.format_exc()}")
            finally:
                io_logger.info("[IO] Output monitoring stopped")
                session.stop_event.set()

        # Process startup with detailed logging
        try:
            console_logger.info("[EXEC] Starting dotnet process")
            process = subprocess.Popen(
                ['dotnet', str(dll_path)],
                stdin=session.slave_fd,
                stdout=session.slave_fd,
                stderr=session.slave_fd,
                preexec_fn=os.setsid,
                cwd=session.temp_dir,
                env={
                    **os.environ,
                    'DOTNET_ROOT': '/nix/store/4k08ckhym1bcwnsk52j201a80l2xrkhp-dotnet-sdk-7.0.410',
                    'DOTNET_CLI_HOME': session.temp_dir,
                    'DOTNET_NOLOGO': 'true',
                    'DOTNET_CLI_TELEMETRY_OPTOUT': 'true'
                }
            )

            session.process = process
            console_logger.info(f"[EXEC] Process started with PID {process.pid}")
            process_mgmt_logger.debug(f"[EXEC] Process state: active={session.is_active()}")

        except Exception as e:
            console_logger.error(f"[EXEC] Process start failed: {str(e)}")
            console_logger.error(f"[EXEC] Stack trace: {traceback.format_exc()}")
            return {'success': False, 'error': f'Failed to start process: {str(e)}'}

        # Start output monitoring
        session.output_thread = Thread(target=monitor_output)
        session.output_thread.daemon = True
        session.output_thread.start()
        io_logger.info("[IO] Monitoring thread started")

        # Process verification
        if process.poll() is not None:
            console_logger.error("[EXEC] Process terminated immediately")
            return {'success': False, 'error': 'Process failed to start'}

        # Final setup and return
        initial_output = session.get_output()
        console_logger.info("[EXEC] Interactive session initialized")
        socketio_logger.info(f"[SOCKET] Session {session.session_id} ready")

        return {
            'success': True,
            'session_id': session.session_id,
            'interactive': True,
            'output': '\n'.join(initial_output),
            'waiting_for_input': session.waiting_for_input
        }

    except Exception as e:
        console_logger.error(f"[EXEC] Session initialization failed: {e}")
        socketio_logger.error(f"[SOCKET] Session {session.session_id} failed")
        return {'success': False, 'error': str(e)}

def compile_and_run(code: str, language: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run code with optional session tracking for interactive mode"""
    logger.debug(f"Starting compilation for code length: {len(code)}, language: {language}")

    if not code:
        return {
            'success': False,
            'error': "No code provided"
        }

    try:
        session = get_or_create_session(session_id)
        return start_interactive_session(session, code, language)

    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        if 'session' in locals() and session.session_id in active_sessions:
            cleanup_session(session.session_id)
        return {
            'success': False,
            'error': str(e)
        }

def send_input(session_id: str, input_text: str) -> Dict[str, Any]:
    """Send input to an interactive session with improved handling"""
    try:
        with session_lock:
            if session_id not in active_sessions:
                return {'success': False, 'error': 'Invalid session'}

            session = active_sessions[session_id]
            if not session.is_active():
                return {'success': False, 'error': 'Session not active'}

            # Wait for input prompt if not already waiting
            if not session.waiting_for_input:
                logger.debug("Waiting for input prompt...")
                if not session.wait_for_input_prompt(timeout=5.0):
                    return {'success': False, 'error': 'Timeout waiting for input prompt'}

            # Ensure input ends with newline
            if not input_text.endswith('\n'):
                input_text += '\n'

            # Set last input to avoid echo detection as prompt
            session.set_last_input(input_text.strip())

            try:
                os.write(session.master_fd, input_text.encode())
                session.waiting_for_input = False
                logger.debug(f"Input sent: {input_text.strip()}")

                # Wait briefly for output processing
                time.sleep(0.1)

                # Check if process is still running
                if session.process.poll() is not None:
                    logger.debug("Process completed after input")
                    remaining_output = session.get_output()
                    return {
                        'success': True,
                        'output': '\n'.join(remaining_output),
                        'waiting_for_input': False,
                        'completed': True
                    }

                return {'success': True}
            except Exception as e:
                logger.error(f"Error sending input: {e}")
                return {'success': False, 'error': str(e)}

    except Exception as e:
        logger.error(f"Send input error: {e}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from an interactive session"""
    try:
        with session_lock:
            if session_id not in active_sessions:
                return {'success': False, 'error': 'Invalid session'}

            session = active_sessions[session_id]
            if not session.is_active():
                return {'success': False, 'error': 'Session not active'}

            output_lines = session.get_output()
            output_text = '\n'.join(output_lines) if output_lines else ""

            return {
                'success': True,
                'output': output_text,
                'waiting_for_input': session.waiting_for_input
            }

    except Exception as e:
        logger.error(f"Get output error: {e}")
        return {'success': False, 'error': str(e)}


import hashlib
from dataclasses import dataclass, field, asdict
import json
import re
import logging

@dataclass
class CompilationMetrics:
    """Enhanced compilation metrics tracking"""
    start_time: float
    end_time: float = 0.0
    compilation_time: float = 0.0
    execution_time: float = 0.0
    peak_memory: float = 0.0
    avg_cpu_usage: float = 0.0
    error_count: int = 0
    warning_count: int = 0
    cached: bool = False
    status_updates: List[Dict[str, Any]] = field(default_factory=list)
    successful_builds: int = 0
    total_builds: int = 0
    stage_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def start_stage(self, stage_name: str) -> None:
        """Track metrics for a specific compilation stage"""
        self.stage_metrics[stage_name] = {
            'start_time': time.time(),
            'peak_memory': 0.0,
            'cpu_usage': 0.0
        }
        self._update_system_metrics(stage_name)
        self.log_status(f"Starting {stage_name}")

    def end_stage(self, stage_name: str) -> None:
        """End tracking for a compilation stage"""
        if stage_name in self.stage_metrics:
            stage = self.stage_metrics[stage_name]
            stage['end_time'] = time.time()
            stage['duration'] = stage['end_time'] - stage['start_time']
            self._update_system_metrics(stage_name)
            self.log_status(f"Completed {stage_name} in {stage['duration']:.2f}s")

    def _update_system_metrics(self, stage_name: str) -> None:
        """Update system metrics for the current stage"""
        try:
            process = psutil.Process()
            stage = self.stage_metrics[stage_name]
            current_memory = process.memory_info().rss / (1024 * 1024)  # MB
            current_cpu = process.cpu_percent(interval=0.1)

            stage['peak_memory'] = max(stage.get('peak_memory', 0), current_memory)
            stage['cpu_usage'] = current_cpu

            # Update overall metrics
            self.peak_memory = max(self.peak_memory, current_memory)
            if not self.avg_cpu_usage:
                self.avg_cpu_usage = current_cpu
            else:
                self.avg_cpu_usage = (self.avg_cpu_usage + current_cpu) / 2
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def log_status(self, status: str) -> None:
        """Log a status update with timestamp and metrics"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        status_entry = {
            'timestamp': current_time,
            'elapsed': elapsed,
            'status': status,
            'memory_mb': psutil.Process().memory_info().rss / (1024 * 1024),
            'cpu_percent': psutil.Process().cpu_percent(interval=0.1)
        }
        self.status_updates.append(status_entry)
        performance_logger.debug(f"[{elapsed:.2f}s] {status}")

    def record_build(self, success: bool) -> None:
        """Record build attempt result"""
        self.total_builds += 1
        if success:
            self.successful_builds += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary with enhanced information"""
        total_time = self.end_time - self.start_time if self.end_time else time.time() - self.start_time
        return {
            'compilation_time': self.compilation_time,
            'execution_time': self.execution_time,
            'total_time': total_time,
            'peak_memory': self.peak_memory,
            'avg_cpu_usage': self.avg_cpu_usage,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'cached': self.cached,
            'build_success_rate': (self.successful_builds / self.total_builds * 100) if self.total_builds > 0 else 0,
            'stages': {
                name: {
                    'duration': metrics.get('duration', 0),
                    'peak_memory': metrics.get('peak_memory', 0),
                    'cpu_usage': metrics.get('cpu_usage', 0)
                }
                for name, metrics in self.stage_metrics.items()
            }
        }


class ErrorTracker:
    """Track and analyze compilation errors with trend analysis"""
    def __init__(self):
        self.errors: List[CompilationError] = []
        self._error_patterns: Dict[str, int] = {}
        self._error_trends: Dict[str, List[datetime]] = {}
        self.recommendations: Dict[str, List[str]] = {
            'CS0103': [
                "Ensure all variables are declared before use",
                "Check for typos in variable names",
                "Verify the variable is accessible in the current scope"
            ],
            'CS0117': [
                "Verify the method name exists in the referenced class",
                "Check for case sensitivity in method names",
                "Ensure you're calling a public method"
            ],
            'CS0234': [
                "Verify namespace references",
                "Check 'using' statements",
                "Ensure required assemblies are referenced"
            ],
            'CS1513': [
                "Check for missing closing braces '}'",
                "Ensure all blocks are properly closed",
                "Verify code block structure"
            ],
            'CS1002': [
                "Add missing semicolon at the end of the statement",
                "Check for missing statement terminators",
                "Review line endings"
            ]
        }

    def add_error(self, error: CompilationError) -> None:
        """Add and analyze a new compilation error with enhanced recommendations"""
        self.errors.append(error)
        error_logger.error(f"Compilation error: {error.to_dict()}")
        self._update_patterns(error)

        # Log        # Log recommendations
        if error.code in self.recommendations:
            recommendations = self.recommendations[error.code]
            error_logger.info(f"Recommendations for error {error.code}:")
            for i, rec in enumerate(recommendations, 1):
                error_logger.info(f"  {i}. {rec}")

    def _update_patterns(self, error: CompilationError) -> None:
        """Update error pattern statistics"""
        pattern = f"{error.error_type}:{error.code}"
        self._error_patterns[pattern] = self._error_patterns.get(pattern, 0) + 1

        if self._error_patterns[pattern] > 5:
            error_logger.warning(f"Frequent error pattern detected: {pattern}")
            self._suggest_automated_fixes(error)

    def _suggest_automated_fixes(self, error: CompilationError) -> None:
        """Suggest automated fixes based on error patterns"""
        if error.code == 'CS0103':  # Undefined variable
            error_logger.info("Automated fix suggestion: You might want to declare the variable first")
            error_logger.info("Example: var undefinedVariable = \"your value\";")
        elif error.code == 'CS1513':  # Missing closing brace
            error_logger.info("Automated fix suggestion: Add missing closing brace '}'")
        elif error.code == 'CS0117':  # No member found
            error_logger.info("Automated fix suggestion: Check class member visibility (public/private)")

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive error analysis summary"""
        recent_errors = sorted(self.errors, key=lambda x: x.timestamp, reverse=True)[:5]
        error_categories = {}

        for error in self.errors:
            category = error.error_type
            if category not in error_categories:
                error_categories[category] = 0
            error_categories[category] += 1

        return {
            'total_errors': len(self.errors),
            'error_patterns': self._error_patterns,
            'most_common': max(self._error_patterns.items(), key=lambda x: x[1]) if self._error_patterns else None,
            'recent_errors': [e.to_dict() for e in recent_errors],
            'error_categories': error_categories,
            'recommendations': {
                code: self.recommendations[code]
                for code in set(error.code for error in self.errors)
                if code in self.recommendations
            }
        }

def get_code_hash(code: str, language: str) -> str:
    """Generate a unique hash for the code and language"""
    hasher = hashlib.sha256()
    hasher.update(f"{code}{language}".encode())
    return hasher.hexdigest()

def is_interactive_code(code: str, language: str) -> bool:
    """Determine if code requires interactive I/O"""
    code = code.lower()
    if language == 'cpp':
        return any(pattern in code for pattern in [
            'cin', 'getline', 'std::cin', 'std::getline',
            'scanf', 'gets', 'fgets'
        ])
    elif language == 'csharp':
        return any(pattern in code for pattern in [
            'console.read', 'console.readline',
            'console.in', 'console.keyavailable',
            'console.readkey'
        ])
    return False

def clean_terminal_output(output: str) -> str:
    """Clean terminal control sequences from output"""
    # Remove ANSI codes
    cleaned = re.sub(r'\x1b\[[0-9;]*[mGKHf]', '', output)
    cleaned = re.sub(r'\x1b\[\??[0-9;]*[A-Za-z]', '', cleaned)
    cleaned = re.sub(r'\x1b[=>]', '', cleaned)

    # Clean up other control characters while preserving prompts
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

    # Normalize line endings
    cleaned = re.sub(r'\r\n?|\n\r', '\n', cleaned)
    cleaned = re.sub(r'^\s*\n', '', cleaned)
    cleaned = re.sub(r'\n\s*$', '\n', cleaned)

    return cleaned.strip()

def parse_csharp_errors(error_output: str) -> List[CompilationError]:
    """Parse C# compiler errors into structured format"""
    errors = []
    try:
        error_lines = error_output.split('\n')
        for line in error_lines:
            if not line.strip() or 'warning' in line.lower():
                continue

            match = re.search(r'(.+?)\((\d+),(\d+)\):\s*error\s*(CS\d+):\s*(.+)', line)
            if match:
                errors.append(CompilationError(
                    error_type='CompilerError',
                    message=match.group(5),
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    code=match.group(4)
                ))
                logger.debug(f"Found error: {errors[-1]}")

    except Exception as e:
        logger.error(f"Error parsing compiler errors: {e}")

    return errors

def get_template(language: str) -> str:
    """Get the template code for a given programming language"""
    templates = {
        'cpp': """#include <iostream>
#include <string>
using namespace std;

int main() {
    // Your code here
    cout << "Hello World!" << endl;
    return 0;
}""",
        'csharp': """using System;

namespace ConsoleApp {
    class Program {
        static void Main() {
            try {
                // Your code here
                Console.WriteLine("Hello World!");
            }
            catch (Exception e) {
                Console.WriteLine($"Error: {e.Message}");
            }
        }
    }
}"""
    }
    return templates.get(language.lower(), '')

import logging
from datetime import datetime
import resource

# Configure enhanced logging
logger = logging.getLogger('compiler_service')
logger.setLevel(logging.DEBUG)
resource_logger = logging.getLogger('resource')
event_logger = logging.getLogger('event')

@contextmanager
def process_monitoring():
    """Context manager for monitoring process creation and resources"""
    start_time = time.time()
    start_resources = resource.getrusage(resource.RUSAGE_SELF)
    process_logger.info(f"Starting process monitoring at {datetime.now().isoformat()}")
    process_logger.debug(f"Initial resource state: {psutil.Process().memory_info()}")

    try:
        yield
    finally:
        end_time = time.time()
        end_resources = resource.getrusage(resource.RUSAGE_SELF)
        duration = end_time - start_time

        process_logger.info(f"Process monitoring completed. Duration: {duration:.2f}s")
        resource_logger.info(f"Resource delta: "
                           f"CPU: {end_resources.ru_utime - start_resources.ru_utime:.2f}s, "
                           f"Memory: {psutil.Process().memory_info().rss / 1024 / 1024:.1f}MB")

def log_process_state(process: subprocess.Popen, context: str):
    """Log detailed process state"""
    if process is None:
        process_logger.error(f"[{context}] Process is None")
        return

    try:
        psutil_proc = psutil.Process(process.pid)
        process_logger.info(
            f"[{context}] Process State: "
            f"PID={process.pid}, "
            f"Status={psutil_proc.status()}, "
            f"CPU={psutil_proc.cpu_percent()}%, "
            f"Memory={psutil_proc.memory_info().rss / 1024 / 1024:.1f}MB, "
            f"Threads={psutil_proc.num_threads()}"
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        process_logger.error(f"[{context}] Failed to get process state: {str(e)}")

def compile_and_run_csharp(code: str, session_id: str) -> Dict[str, Any]:
    """Compile and run C# code with enhanced process and event monitoring"""
    process_logger.info(f"[{session_id}] Starting C# compilation process")
    event_logger.info(f"[{session_id}] Compilation event started")

    metrics = CompilationMetrics(start_time=time.time())
    process = None

    try:
        with process_monitoring():
            # Create project structure
            process_logger.debug(f"[{session_id}] Creating project environment")
            temp_dir = Path(tempfile.mkdtemp(prefix=f'compiler_{session_id}_'))
            process_logger.info(f"[{session_id}] Created temp directory: {temp_dir}")

            # Write project files
            source_file = temp_dir / "Program.cs"
            project_file = temp_dir / "program.csproj"

            process_logger.debug(f"[{session_id}] Writing project files")
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
                <PropertyGroup>
                    <OutputType>Exe</OutputType>
                    <TargetFramework>net7.0</TargetFramework>
                    <ImplicitUsings>enable</ImplicitUsings>
                    <Nullable>enable</Nullable>
                </PropertyGroup>
            </Project>"""

            with open(project_file, 'w') as f:
                f.write(project_content)
            with open(source_file, 'w') as f:
                f.write(code)

            process_logger.info(f"[{session_id}] Project files written successfully")

            # Compile
            event_logger.info(f"[{session_id}] Starting compilation")
            compile_result = subprocess.run(
                ['dotnet', 'build', str(project_file), '--nologo'],
                capture_output=True,
                text=True,
                cwd=str(temp_dir)
            )

            process_logger.info(f"[{session_id}] Compilation completed with return code: {compile_result.returncode}")

            if compile_result.returncode != 0:
                error_msg = compile_result.stderr
                process_logger.error(f"[{session_id}] Compilation failed: {error_msg}")
                return {'success': False, 'error': error_msg}

            # Start the compiled program
            executable = temp_dir / "bin" / "Debug" / "net7.0" / "program.dll"

            if not executable.exists():
                error_msg = f"Executable not found at {executable}"
                process_logger.error(f"[{session_id}] {error_msg}")
                return {'success': False, 'error': error_msg}

            event_logger.info(f"[{session_id}] Starting program execution")
            process = subprocess.Popen(
                ['dotnet', str(executable)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(temp_dir)
            )

            process_logger.info(f"[{session_id}] Process started with PID: {process.pid}")
            log_process_state(process, f"{session_id} - Initial State")

            # Monitor initial output
            try:
                readable, _, _ = select.select([process.stdout], [], [], 5.0)

                if not readable:
                    process_logger.warning(f"[{session_id}] No initial output received in 5s")
                    initial_output = ""
                else:
                    initial_output = process.stdout.readline().strip()
                    process_logger.info(f"[{session_id}] Initial output received: {initial_output}")

                # Verify process is still running
                log_process_state(process, f"{session_id} - Post Initial Output")

                if process.poll() is not None:
                    exit_code = process.poll()
                    error_output = process.stderr.read()
                    process_logger.error(
                        f"[{session_id}] Process ended prematurely. "
                        f"Exit code: {exit_code}, Error: {error_output}"
                    )
                    return {
                        'success': False,
                        'error': f"Process ended with code {exit_code}: {error_output}"
                    }

            except Exception as e:
                process_logger.error(f"[{session_id}] Error reading initial output: {str(e)}")
                if process and process.poll() is None:
                    log_process_state(process, f"{session_id} - Error State")
                return {'success': False, 'error': str(e)}

            process_logger.info(f"[{session_id}] Successfully started interactive session")
            event_logger.info(f"[{session_id}] Compilation and execution successful")

            return {
                'success': True,
                'session_id': session_id,
                'interactive': True,
                'output': initial_output,
                'waiting_for_input': bool(initial_output)
            }

    except Exception as e:
        process_logger.error(f"[{session_id}] Critical error: {str(e)}", exc_info=True)
        if process and process.poll() is None:
            log_process_state(process, f"{session_id} - Error State")
        return {'success': False, 'error': str(e)}

    finally:
        event_logger.info(f"[{session_id}] Compilation process complete")
        metrics.end_time = time.time()
        resource_logger.info(
            f"[{session_id}] Final metrics: "
            f"Duration={metrics.end_time - metrics.start_time:.2f}s, "
            f"Peak Memory={metrics.peak_memory:.1f}MB, "
            f"Avg CPU={metrics.avg_cpu_usage:.1f}%"
        )

def is_interactive_code(code: str, language: str) -> bool:
    """Determine if code requires interactive I/O"""
    code = code.lower()
    if language == 'cpp':
        return any(pattern in code for pattern in [
            'cin', 'getline', 'std::cin', 'std::getline',
            'scanf', 'gets', 'fgets'
        ])
    elif language == 'csharp':
        return any(pattern in code for pattern in [
            'console.read', 'console.readline',
            'console.in', 'console.keyavailable',
            'console.readkey'
        ])
    return False

def clean_terminal_output(output: str) -> str:
    """Clean terminal control sequences from output"""
    # Remove ANSI codes
    cleaned = re.sub(r'\x1b\[[0-9;]*[mGKHf]', '', output)
    cleaned = re.sub(r'\x1b\[\??[0-9;]*[A-Za-z]', '', cleaned)
    cleaned = re.sub(r'\x1b[=>]', '', cleaned)

    # Clean up other control characters while preserving prompts
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

    # Normalize line endings
    cleaned = re.sub(r'\r\n?|\n\r', '\n', cleaned)
    cleaned = re.sub(r'^\s*\n', '', cleaned)
    cleaned = re.sub(r'\n\s*$', '\n', cleaned)

    return cleaned.strip()

def parse_csharp_errors(error_output: str) -> List[CompilationError]:
    """Parse C# compiler errors into structured format"""
    errors = []
    try:
        error_lines = error_output.split('\n')
        for line in error_lines:
            if not line.strip() or 'warning' in line.lower():
                continue

            match = re.search(r'(.+?)\((\d+),(\d+)\):\s*error\s*(CS\d+):\s*(.+)', line)
            if match:
                errors.append(CompilationError(
                    error_type='CompilerError',
                    message=match.group(5),
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    code=match.group(4)
                ))
                logger.debug(f"Found error: {errors[-1]}")

    except Exception as e:
        logger.error(f"Error parsing compiler errors: {e}")

    return errors

def get_code_hash(code: str, language: str) -> str:
    """Generate a unique hash for the code and language"""
    hasher = hashlib.sha256()
    hasher.update(f"{code}{language}".encode())
    return hasher.hexdigest()

def get_template(language: str) -> str:
    """Get the template code for a given programming language"""
    templates = {
        'cpp': """#include <iostream>
#include <string>
using namespace std;

int main() {
    // Your code here
    cout << "Hello World!" << endl;
    return 0;
}""",
        'csharp': """using System;

namespace ConsoleApp {
    class Program {
        static void Main() {
            try {
                // Your code here
                Console.WriteLine("Hello World!");
            }
            catch (Exception e) {
                Console.WriteLine($"Error: {e.Message}");
            }
        }
    }
}"""
    }
    return templates.get(language.lower(), '')

# Add new socket state tracking
_socket_connections = {}
_socket_lock = Lock()

def track_socket_connection(sid: str, state: str):
    """Track socket connection state with timing"""
    with _socket_lock:
        now = datetime.now().isoformat()
        if sid not in _socket_connections:
            _socket_connections[sid] = []
        _socket_connections[sid].append({
            'state': state,
            'timestamp': now
        })
        socketio_logger.info(f"[SOCKET] {sid}: {state} at {now}")

def handle_compile_request(sid: str, data: Dict[str, Any]) -> None:
    """Handle compilation request with enhanced error handling and socket state tracking"""
    try:
        track_socket_connection(sid, 'compile_start')
        socketio_logger.info(f"[SOCKET] Starting compilation for {sid}")

        code = data.get('code', '')
        if not code:
            socketio_logger.error(f"[SOCKET] Empty code received from {sid}")
            return {'success': False, 'error': 'No code provided'}

        # Start compilation in thread to avoid blocking socket
        thread = Thread(target=_handle_compile_thread, args=(sid, code))
        thread.daemon = True
        thread.start()

        socketio_logger.debug(f"[SOCKET] Compilation thread started for {sid}")

    except Exception as e:
        socketio_logger.error(f"[SOCKET] Compilation request failed for {sid}: {str(e)}")
        track_socket_connection(sid, f'compile_error: {str(e)}')
        return {'success': False, 'error': str(e)}

def _handle_compile_thread(sid: str, code: str) -> None:
    """Handle compilation in separate thread"""
    try:
        # Start compilation
        result = compile_and_run(code, 'csharp')

        if result['success']:
            socketio_logger.info(f"[SOCKET] Compilation successful for {sid}")
            track_socket_connection(sid, 'compile_success')
        else:
            socketio_logger.error(f"[SOCKET] Compilation failed for {sid}: {result.get('error')}")
            track_socket_connection(sid, f'compile_failed: {result.get("error")}')

    except Exception as e:
        socketio_logger.error(f"[SOCKET] Compilation thread error for {sid}: {str(e)}")
        track_socket_connection(sid, f'compile_thread_error: {str(e)}')

def handle_socket_disconnect(sid: str) -> None:
    """Handle socket disconnection with cleanup"""
    try:
        socketio_logger.info(f"[SOCKET] Client disconnecting: {sid}")
        track_socket_connection(sid, 'disconnected')

        # Cleanup any active sessions
        if sid in _socket_connections:
            cleanup_session(sid)
            with _socket_lock:
                del _socket_connections[sid]

        socketio_logger.info(f"[SOCKET] Cleanup completed for {sid}")

    except Exception as e:
        socketio_logger.error(f"[SOCKET] Disconnect handling failed for {sid}: {str(e)}")

def handle_socket_error(sid: str, error: Any) -> None:
    """Handle socket errors with logging"""
    socketio_logger.error(f"[SOCKET] Error for {sid}: {str(error)}")
    track_socket_connection(sid, f'socket_error: {str(error)}')