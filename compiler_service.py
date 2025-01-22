import os
import pty
import select
import signal
import logging
import tempfile
import threading
import subprocess
from typing import Dict, Any, Optional, List, Union
from threading import Lock, Thread, Event
from pathlib import Path
import psutil
import time
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
import hashlib
import fcntl
import termios
import struct
import errno
import re
import json
import traceback
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
                    handlers=[
                        logging.FileHandler('compiler.log'),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# Add specialized loggers for different aspects
compilation_logger = logging.getLogger('compiler.compilation')
performance_logger = logging.getLogger('compiler.performance')
error_logger = logging.getLogger('compiler.error')

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

    def add_error(self, error: CompilationError):
        """Add and analyze a new compilation error with enhanced recommendations"""
        self.errors.append(error)
        error_logger.error(f"Compilation error: {error.to_dict()}")
        self._update_patterns(error)

        # Log recommendations
        if error.code in self.recommendations:
            recommendations = self.recommendations[error.code]
            error_logger.info(f"Recommendations for error {error.code}:")
            for i, rec in enumerate(recommendations, 1):
                error_logger.info(f"  {i}. {rec}")

        # Track error trends
        pattern = f"{error.error_type}:{error.code}"
        if pattern not in self._error_trends:
            self._error_trends[pattern] = []
        self._error_trends[pattern].append(datetime.fromisoformat(error.timestamp))
        self._analyze_frequent_patterns(pattern)

    def _update_patterns(self, error: CompilationError):
        """Update error pattern statistics with enhanced tracking"""
        pattern = f"{error.error_type}:{error.code}"
        self._error_patterns[pattern] = self._error_patterns.get(pattern, 0) + 1

        if self._error_patterns[pattern] > 5:
            error_logger.warning(f"Frequent error pattern detected: {pattern}")
            self._analyze_frequent_patterns(pattern)
            self._suggest_automated_fixes(error)

    def _suggest_automated_fixes(self, error: CompilationError):
        """Suggest automated fixes based on error patterns"""
        if error.code == 'CS0103':  # Undefined variable
            error_logger.info("Automated fix suggestion: You might want to declare the variable first")
            error_logger.info("Example: var undefinedVariable = \"your value\";")
        elif error.code == 'CS1513':  # Missing closing brace
            error_logger.info("Automated fix suggestion: Add missing closing brace '}'")
        elif error.code == 'CS0117':  # No member found
            error_logger.info("Automated fix suggestion: Check class member visibility (public/private)")

    def _analyze_frequent_patterns(self, pattern: str):
        """Analyze frequency of error patterns with enhanced analytics"""
        if pattern not in self._error_trends:
            return

        timestamps = self._error_trends[pattern]
        if len(timestamps) < 2:
            return

        # Calculate time differences between consecutive errors
        time_diffs = [(t2 - t1).total_seconds() for t1, t2 in zip(timestamps[:-1], timestamps[1:])]
        avg_time_between_errors = sum(time_diffs) / len(time_diffs) if time_diffs else 0

        if avg_time_between_errors < 60:  # Less than 1 minute between errors
            error_logger.critical(f"High-frequency error pattern detected: {pattern}")
            self._recommend_fixes(pattern)

            # Check for potential infinite loops or recursion
            if len(timestamps) > 10 and avg_time_between_errors < 1:
                error_logger.critical("Possible infinite loop or recursion detected!")

    def _recommend_fixes(self, pattern: str):
        """Provide recommendations based on error patterns with enhanced suggestions"""
        common_fixes = {
            'CS0103': "Check for undefined variables and ensure all variables are declared before use",
            'CS0117': "Verify method names and ensure they exist in the referenced class",
            'CS0234': "Check namespace references and using statements",
            'CS0246': "Verify all required dependencies are properly referenced",
            'CS1002': "Check for missing semicolons",
            'CS1513': "Check for missing closing braces",
            'CS1525': "Check for invalid syntax or missing operators",
            'CS0116': "All methods must have a return type",
            'CS0165': "Use of unassigned local variable",
            'CS0428': "Cannot convert method group to non-delegate type",
            'CS0161': "Not all code paths return a value",
            'CS0219': "Variable is assigned but never used",
            'CS0105': "Using directive appeared previously",
            'CS0168': "Variable declared but never used"
        }

        error_code = pattern.split(':')[1]
        if error_code in common_fixes:
            error_logger.info(f"Recommended fix for {error_code}: {common_fixes[error_code]}")

            # Additional context-specific recommendations
            if error_code == 'CS0103':
                error_logger.info("Additional context:")
                error_logger.info("1. Check variable scope - ensure it's declared in the current context")
                error_logger.info("2. Verify variable name casing - C# is case-sensitive")
                error_logger.info("3. If it's a class member, ensure proper access modifiers")
        else:
            error_logger.info(f"No specific recommendation available for error code: {error_code}")

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive error analysis summary with enhanced details"""
        frequent_patterns = {k: v for k, v in self._error_patterns.items() if v > 1}
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
            'frequent_patterns': frequent_patterns,
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

@dataclass
class CompilerSession:
    """Manages a single compilation/execution session with improved resource handling"""
    session_id: str
    temp_dir: str
    process: Optional[subprocess.Popen] = None
    master_fd: Optional[int] = None
    slave_fd: Optional[int] = None
    output_thread: Optional[Thread] = None
    output_buffer: List[str] = field(default_factory=list)
    waiting_for_input: bool = False
    last_activity: Event = field(default_factory=Event)
    stop_event: Event = field(default_factory=Event)
    metrics: CompilationMetrics = field(default_factory=lambda: CompilationMetrics(time.time()))
    error_tracker: ErrorTracker = field(default_factory=ErrorTracker)
    _buffer: str = ""
    _partial_line: str = ""
    _streams_closed: bool = False
    _cleanup_lock: Lock = field(default_factory=Lock)
    _access_lock: Lock = field(default_factory=Lock)

    def is_active(self) -> bool:
        """Check if the session is still active"""
        with self._access_lock:
            return (self.process is not None and 
                    self.process.poll() is None and 
                    not self.stop_event.is_set())

    def append_output(self, text: str) -> None:
        """Thread-safe method to append output"""
        with self._access_lock:
            self.output_buffer.append(text)

    def get_output(self) -> List[str]:
        """Thread-safe method to get output"""
        with self._access_lock:
            return self.output_buffer.copy()

    def set_waiting_for_input(self, value: bool) -> None:
        """Thread-safe method to set waiting_for_input"""
        with self._access_lock:
            self.waiting_for_input = value

    def cleanup(self) -> None:
        """Cleanup session resources with improved file descriptor handling"""
        with self._cleanup_lock:
            if self._streams_closed:
                return

            logger.debug(f"Starting cleanup for session {self.session_id}")
            self.stop_event.set()

            # Terminate process if still running
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    except OSError as e:
                        logger.error(f"Error killing process group: {e}")

            # Close PTY file descriptors
            for fd in (self.master_fd, self.slave_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as e:
                        if e.errno != errno.EBADF:
                            logger.error(f"Error closing file descriptor {fd}: {e}")

            # Close process streams
            if self.process:
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except Exception as e:
                            logger.error(f"Error closing process stream: {e}")

            # Wait for output thread to finish
            if self.output_thread and self.output_thread.is_alive():
                try:
                    self.output_thread.join(timeout=2)
                except Exception as e:
                    logger.error(f"Error joining output thread: {e}")

            # Clean up temp directory
            if os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                except OSError as e:
                    logger.error(f"Failed to remove temp directory: {e}")

            self._streams_closed = True
            logger.debug(f"Session {self.session_id} cleaned up successfully")

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

        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        temp_dir = tempfile.mkdtemp(prefix=f'compiler_session_{new_session_id}_')
        session = CompilerSession(new_session_id, temp_dir)
        active_sessions[new_session_id] = session
        return session

def cleanup_session(session_id: str) -> None:
    """Clean up resources for a session"""
    with session_lock:
        if session_id in active_sessions:
            session = active_sessions[session_id]
            session.cleanup()
            del active_sessions[session_id]

def cleanup_inactive_sessions() -> None:
    """Clean up inactive sessions"""
    with session_lock:
        inactive = [sid for sid, session in active_sessions.items() 
                   if not session.is_active()]
        for session_id in inactive:
            cleanup_session(session_id)

def create_pty() -> tuple[int, int]:
    """Create a new PTY pair with proper settings"""
    master_fd, slave_fd = pty.openpty()

    # Set raw mode on the master side
    term_attrs = termios.tcgetattr(master_fd)
    term_attrs[3] = term_attrs[3] & ~(termios.ECHO | termios.ICANON)
    term_attrs[0] = term_attrs[0] | termios.BRKINT | termios.PARMRK
    termios.tcsetattr(master_fd, termios.TCSANOW, term_attrs)

    # Set window size
    winsize = struct.pack("HHHH", 24, 80, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    # Set non-blocking mode
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    return master_fd, slave_fd

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

def monitor_output(process: subprocess.Popen, session: CompilerSession, chunk_size: int = 1024) -> None:
    """Monitor process output with improved input detection and resource handling"""
    def check_for_input_prompt(text: str) -> bool:
        """Check if text contains input prompt indicators with improved pattern matching"""
        if not text:
            return False

        text = text.lower()
        # Immediate indicators that almost always indicate input
        if any(x in text for x in ('cin', 'readline', 'readkey', 'read-line', 'input')):
            return True

        # Common input patterns with weights
        input_patterns = {
            r'\b(enter|type|input)\b': 2,  # Strong indicators
            r'[?:>]$': 1,                  # End of line indicators
            r'\bname\b': 1,                # Context-specific indicator
            r'\bchoice\b': 1,              # Interactive prompts
        }

        score = 0
        for pattern, weight in input_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                score += weight

        return score >= 1  # Return true if we have enough confidence

    try:
        buffer = ""
        while not session.stop_event.is_set() and process.poll() is None:
            if session.master_fd is None:
                break

            try:
                readable, _, _ = select.select([session.master_fd], [], [], 0.1)

                for fd in readable:
                    try:
                        data = os.read(fd, chunk_size)
                        if not data:
                            continue

                        decoded = data.decode('utf-8', errors='replace')
                        buffer += decoded

                        # Check buffer before processing for early input detection
                        if not session.waiting_for_input and check_for_input_prompt(buffer):
                            session.set_waiting_for_input(True)
                            logger.debug(f"Early input prompt detected in buffer: {buffer}")

                        # Process complete lines
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            cleaned = clean_terminal_output(line)
                            if cleaned:
                                session.append_output(cleaned)
                                logger.debug(f"Output received: {cleaned}")

                                # Check for input prompt in complete line
                                if not session.waiting_for_input and check_for_input_prompt(cleaned):
                                    session.set_waiting_for_input(True)
                                    logger.debug(f"Input prompt detected in line: {cleaned}")

                        # Check remaining buffer for input prompt
                        if buffer and not session.waiting_for_input:
                            cleaned_buffer = clean_terminal_output(buffer)
                            if cleaned_buffer and check_for_input_prompt(cleaned_buffer):
                                session.set_waiting_for_input(True)
                                logger.debug(f"Input prompt detected in partial buffer: {cleaned_buffer}")

                    except (OSError, IOError) as e:
                        if e.errno != errno.EAGAIN:
                            logger.error(f"Error reading from PTY: {e}")
                            return
                        continue

            except (select.error, OSError) as e:
                logger.error(f"Select error: {e}")
                break

            time.sleep(0.05)
            session.last_activity.set()

    except Exception as e:
        logger.error(f"Error in monitor_output: {traceback.format_exc()}")

    finally:
        # Process any remaining buffer
        if buffer:
            cleaned = clean_terminal_output(buffer)
            if cleaned:
                session.append_output(cleaned)
                if not session.waiting_for_input and check_for_input_prompt(cleaned):
                    session.set_waiting_for_input(True)
                logger.debug(f"Final buffer processed: {cleaned}")

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with improved error handling and logging"""
    try:
        logger.info(f"Starting interactive session for {language}")
        logger.debug(f"Session ID: {session.session_id}")

        if language not in ('csharp', 'cpp'):
            return {
                'success': False,
                'error': f"Interactive mode not supported for {language}",
                'metrics': session.metrics.to_dict()
            }

        # Create isolated environment
        logger.info("Creating isolated environment")
        temp_dir, project_name = create_isolated_environment(code, language)
        session.temp_dir = str(temp_dir)

        if language == 'csharp':
            try:
                project_file = Path(session.temp_dir) / f"{project_name}.csproj"
                compile_cmd = [
                    'dotnet', 'build',
                    str(project_file),
                    '--configuration', 'Release',
                    '--nologo',
                    '/p:GenerateFullPaths=true',
                    '/consoleloggerparameters:NoSummary;Verbosity=detailed'
                ]

                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(session.temp_dir)
                )

                if compile_process.returncode != 0:
                    errors = parse_csharp_errors(compile_process.stderr or compile_process.stdout)
                    for error in errors:
                        session.error_tracker.add_error(error)
                    error_summary = session.error_tracker.get_summary()
                    session.cleanup()
                    return {
                        'success': False,
                        'error': json.dumps(error_summary, indent=2),
                        'metrics': session.metrics.to_dict()
                    }

                dll_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / f"{project_name}.dll"
                master_fd, slave_fd = create_pty()
                session.master_fd = master_fd
                session.slave_fd = slave_fd

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

                os.close(slave_fd)
                session.process = process

                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True,
                    'metrics': session.metrics.to_dict()
                }

            except subprocess.TimeoutExpired:
                session.cleanup()
                return {
                    'success': False,
                    'error': f"Compilation timed out after {MAX_COMPILATION_TIME} seconds",
                    'metrics': session.metrics.to_dict()
                }

        elif language == 'cpp':
            source_file = Path(session.temp_dir) / "program.cpp"
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            executable = Path(session.temp_dir) / "program"
            compile_process = subprocess.run(
                ['g++', '-std=c++17', '-O2', '-Wall', str(source_file), '-o', str(executable)],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME
            )

            if compile_process.returncode != 0:
                error_msg = compile_process.stderr
                session.cleanup()
                return {
                    'success': False,
                    'error': f"Compilation Error: {error_msg}",
                    'metrics': session.metrics.to_dict()
                }

            executable.chmod(0o755)
            master_fd, slave_fd = create_pty()
            session.master_fd = master_fd
            session.slave_fd = slave_fd

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

                os.close(slave_fd)
                session.process = process

                session.output_thread = Thread(target=monitor_output, args=(process, session))
                session.output_thread.daemon = True
                session.output_thread.start()

                return {
                    'success': True,
                    'session_id': session.session_id,
                    'interactive': True,
                    'metrics': session.metrics.to_dict()
                }

            except Exception as e:
                logger.error(f"Error starting C++ process: {e}")
                session.cleanup()
                return {
                    'success': False,
                    'error': f"Process Error: {str(e)}",
                    'metrics': session.metrics.to_dict()
                }

    except Exception as e:
        if session and session.session_id in active_sessions:
            session.cleanup()
        logger.error(f"Error in start_interactive_session: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'metrics': session.metrics.to_dict() if session else {}
        }

def send_input(session_id: str, input_text: str) -> Dict[str, Any]:
    """Send input to an interactive session with improved synchronization"""
    try:
        with session_lock:
            if session_id not in active_sessions:
                logger.error(f"Invalid session ID: {session_id}")
                return {'success': False, 'error': 'Invalid session ID'}

            session = active_sessions[session_id]
            if not session.is_active():
                logger.error("Process not running")
                return {'success': False, 'error': 'Process not running'}

            # Ensure input ends with newline
            if not input_text.endswith('\n'):
                input_text += '\n'

            # Write to master PTY with proper locking
            with session._access_lock:
                if session.master_fd is not None:
                    try:
                        bytes_written = os.write(session.master_fd, input_text.encode())
                        if bytes_written > 0:
                            logger.debug(f"Input sent: {input_text.strip()} ({bytes_written} bytes)")
                            session.set_waiting_for_input(False)
                            return {'success': True}
                        else:
                            logger.error("Failed to write input (0 bytes written)")
                            return {'success': False, 'error': 'Failed to write input'}
                    except OSError as e:
                        logger.error(f"Error writing to PTY: {e}")
                        if e.errno == errno.EBADF:
                            session.cleanup()  # Clean up session if file descriptor is invalid
                            return {'success': False, 'error': f'Failed to send input: {str(e)}'}
                else:
                    logger.error("No PTY master file descriptor available")
                    return {'success': False, 'error': "No PTY master file descriptor available"}

    except Exception as e:
        logger.error(f"Error sending input: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from an interactive session with improved synchronization"""
    try:
        with session_lock:
            if session_id not in active_sessions:
                logger.error(f"Invalid session ID: {session_id}")
                return {'success': False, 'error': 'Invalid session ID'}

            session = active_sessions[session_id]
            if not session.is_active():
                return {'success': False, 'error': 'Process not running'}

            # Wait briefly for output
            time.sleep(0.1)

            # Get output with proper locking
            with session._access_lock:
                output_lines = session.get_output()
                # Keep last few lines in buffer for context
                if output_lines:
                    session.output_buffer = output_lines[-5:]

                # Format output
                output_text = '\n'.join(output_lines) if output_lines else ""

                # Check if process has ended
                if session.process and session.process.poll() is not None:
                    logger.debug(f"Process ended with code: {session.process.poll()}")
                    session.cleanup()  # Ensure cleanup happens when process ends
                    return {
                        'success': True,
                        'output': output_text,
                        'session_ended': True
                    }

                return {
                    'success': True,
                    'output': output_text,
                    'waiting_for_input': session.waiting_for_input,
                    'session_ended': False
                }

    except Exception as e:
        logger.error(f"Error getting output: {str(e)}")
        return {'success': False, 'error': str(e)}

# Add active_sessions at the top level after other imports
active_sessions: Dict[str, CompilerSession] = {}
session_lock = Lock()

def cleanup_session(session_id: str) -> None:
    """Clean up resources for a session with proper PTY cleanup"""
    with session_lock:
        if session_id in active_sessions:
            session = active_sessions[session_id]

            # Stop the monitoring thread
            session.stop_event.set()

            # Close process if it's still running
            if session.process and session.process.poll() is None:
                try:
                    session.process.terminate()
                    session.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(session.process.pid), signal.SIGKILL)
                    except OSError as e:
                        logger.error(f"Error killing process group: {e}")

            # Properly close file descriptors
            for fd in (session.master_fd, session.slave_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as e:
                        if e.errno != errno.EBADF:  # Ignore already closed file descriptors
                            logger.error(f"Error closing file descriptor {fd}: {e}")

            # Close process file descriptors
            if session.process:
                for stream in (session.process.stdin, session.process.stdout, session.process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except Exception as e:
                            logger.error(f"Error closing process stream: {e}")

            # Wait for output thread to finish
            if session.output_thread and session.output_thread.is_alive():
                session.output_thread.join(timeout=2)

            # Clean up temporary directory
            if os.path.exists(session.temp_dir):
                try:
                    shutil.rmtree(session.temp_dir)
                except OSError as e:
                    logger.error(f"Failed to remove temp directory: {e}")

            # Remove from active sessions
            del active_sessions[session_id]
            logger.debug(f"Session {session_id} cleaned up successfully")


# Constants for timeouts and intervals
MAX_COMPILATION_TIME = 30  # seconds
MAX_SESSION_LIFETIME = 3600  # 1 hour
CLEANUP_INTERVAL = 300  # 5 minutes

def create_isolated_environment(code: str, language: str) -> tuple[Path, str]:
    """Create isolated environment for compilation with improved project setup"""
    temp_dir = Path(tempfile.mkdtemp(prefix=f'compiler_env_{language}_'))
    project_name = "ConsoleApp"

    if language == 'csharp':
        # Create source file
        source_file = temp_dir / "Program.cs"
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Create optimized project file
        project_file = temp_dir / f"{project_name}.csproj"
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

        logger.debug(f"Created C# project in {temp_dir}")

    elif language == 'cpp':
        source_file = temp_dir / "program.cpp"
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)
        logger.debug(f"Created C++ project in {temp_dir}")

    return temp_dir, project_name

MAX_COMPILATION_TIME = 30  # Maximum time allowed for compilation in seconds

def parse_csharp_errors(error_output: str) -> List[CompilationError]:
    """Parse C# compiler error messages with improved error detection"""
    errors = []
    for line in error_output.splitlines():
        if ": error CS" in line:
            try:
                # Parse error line (format: file(line,col): error CSxxxx: message)
                parts = line.split(': error CS')
                if len(parts) != 2:
                    continue

                location, error_part = parts
                error_code, message = error_part.split(': ', 1)

                # Parse location
                loc_match = re.match(r'.*?\((\d+),(\d+)\)', location)
                if loc_match:
                    line_num, col = map(int, loc_match.groups())
                else:
                    line_num, col = 0, 0

                errors.append(CompilationError(
                    error_type="compilation",
                    message=message.strip(),
                    file=location.split('(')[0],
                    line=line_num,
                    column=col,
                    code=f"CS{error_code}"
                ))
            except Exception as e:
                logger.error(f"Error parsing compiler output: {e}")
                continue

    return errors

def compile_and_run(code: str, language: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with optional session tracking for interactive mode

    Args:
        code: Source code to compile and run
        language: Programming language ('cpp' or 'csharp') 
        session_id: Optional session ID for interactive sessions

    Returns:
        Dictionary containing compilation/execution results and session info
    """
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
        if session and session.session_id in active_sessions:
            cleanup_session(session.session_id)
        return {
            'success': False,
            'error': str(e)
        }

def cleanup_compilation_files(temp_dir: Union[str, Path]) -> None:
    """Clean up temporary compilation files with enhanced logging"""
    try:
        if isinstance(temp_dir, str):
            temp_dir = Path(temp_dir)

        if temp_dir.exists():
            # Log directory size before cleanup
            total_size = sum(f.stat().st_size for f in temp_dir.glob('**/*') if f.is_file())
            logger.debug(f"Cleaning up directory {temp_dir} (size: {total_size/1024:.1f}KB)")

            # Remove all files and subdirectories
            shutil.rmtree(temp_dir)
            logger.debug(f"Successfully removed directory {temp_dir}")
    except Exception as e:
        logger.error(f"Error during cleanup of {temp_dir}: {e}")

def format_csharp_error(error_output: str) -> Dict[str, Any]:
    """Format C# compiler error output into structured data"""
    logger.debug(f"Raw error output:\n{error_output}")

    error_info = {
        'error_type': 'CompilerError',
        'message': error_output,
        'file': '',
        'line': 0,
        'column': 0,
        'code': '',
        'timestamp': datetime.now().isoformat()
    }

    try:
        # Look for error patterns like: (line,col): error CS#### message
        match = re.search(r'\((\d+),(\d+)\):\s*error\s*(CS\d+):\s*(.+)', error_output)
        if match:
            error_info.update({
                'line': int(match.group(1)),
                'column': int(match.group(2)),
                'code': match.group(3),
                'message': match.group(4)
            })
            logger.debug(f"Parsed error details: {error_info}")
    except Exception as e:
        logger.error(f"Error parsing compiler output: {e}")

    return error_info

def parse_csharp_errors(error_output: str) -> List[CompilationError]:
    """Parse C# compiler errors into structured format"""
    errors = []
    try:
        # Split output into lines and look for error patterns
        error_lines = error_output.split('\n')
        for line in error_lines:
            # Skip empty lines and warnings
            if not line.strip() or 'warning' in line.lower():
                continue

            # Parse error line
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

def get_template(language: str) -> str:
    """Get the template code for a given programming language."""
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

namespace ConsoleApp 
{
    class Program 
    {
        static void Main(string[] args) 
        {
            try 
            {
                // Your code here
                Console.WriteLine("Hello World!");
            }
            catch (Exception e) 
            {
                Console.WriteLine($"Error: {e.Message}");
            }
        }
    }
}"""
    }
    return templates.get(language.lower(), '')

def parse_csharp_errors(error_output: str) -> List[CompilationError]:
    """Parse C# compiler errors into a list of CompilationError objects"""
    errors = []
    lines = error_output.splitlines()
    for line in lines:
        match = re.match(r"(.+)\((\d+),(\d+)\):\s+error\s+CS(\d+):\s+(.*)", line)
        if match:
            file, line_num, col_num, code, message = match.groups()
            errors.append(CompilationError(
                error_type="CompilerError",
                message=message.strip(),
                file=file.strip(),
                line=int(line_num),
                column=int(col_num),
                code=f"CS{code}"
            ))
    return errors

MAX_COMPILATION_TIME = 30    # seconds
MAX_EXECUTION_TIME = 30     # seconds
MEMORY_LIMIT = 1024        # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"
CACHE_MAX_SIZE = 50      # Maximum number of cached compilations

# Initialize cache directory
os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
_compilation_cache = {}
_cache_lock = Lock()

import uuid