import os
import pty
import select
import subprocess
import tempfile
import logging
import traceback
import signal
import json
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
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('compiler.log'),
        logging.StreamHandler()
    ]
)
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
        self.metrics = CompilationMetrics(time.time()) # Initialize metrics here
        self.error_tracker = ErrorTracker()



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

    # Normalize line endings and whitespace while preserving prompts
    cleaned = re.sub(r'\r\n?|\n\r', '\n', cleaned)  # Normalize line endings
    cleaned = re.sub(r'^\s*\n', '', cleaned)  # Remove empty lines at start
    cleaned = re.sub(r'\n\s*$', '\n', cleaned)  # Clean trailing whitespace
    cleaned = re.sub(r'\s*=\s*$', '', cleaned)  # Remove trailing equals signs
    cleaned = re.sub(r'[\n\r]+', '\n', cleaned)  # Collapse multiple newlines

    # Preserve important prompts
    cleaned = re.sub(r'(?<=:)\s+(?=\w)', ' ', cleaned)  # Normalize spacing after colons
    cleaned = re.sub(r'(?<=[>:])\s+$', ' ', cleaned)  # Keep space after prompts

    # Clean up remaining control characters while preserving prompts
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
                                # Handle partial lines
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
                                            # Common input patterns for both C++ and C#
                                            input_patterns = [
                                                'input', 'enter', 'type', '?', ':', '>',
                                                'choice', 'select', 'press', 'continue',
                                                'cin', 'Console.ReadLine', 'ReadKey'
                                            ]

                                            # Get recent output for context (last line is most important)
                                            recent_output = cleaned.lower()

                                            # Improved prompt detection
                                            is_input_prompt = (
                                                any(pattern in recent_output for pattern in input_patterns) or
                                                recent_output.rstrip().endswith(':') or
                                                recent_output.rstrip().endswith('> ') or
                                                (recent_output.count('\n') == 0 and
                                                 any(char in recent_output for char in '?:>'))
                                            )

                                            if is_input_prompt:
                                                session.waiting_for_input = True
                                                logger.debug(f"Input prompt detected: {cleaned}")

                        except Exception as e:
                            logger.error(f"Error processing output: {e}")
                            continue
                except (OSError, IOError) as e:
                    if e.errno != errno.EAGAIN:
                        logger.error(f"Error reading from PTY: {e}")
                        break
                    continue

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

def start_interactive_session(session: CompilerSession, code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with improved error handling and logging"""
    try:
        logger.info("=== Interactive Session Initialization ===")
        logger.info(f"1. Starting interactive session for {language}")
        logger.debug(f"1.1 Session ID: {session.session_id}")
        logger.debug(f"1.2 Code preview:\n{code[:200]}...")  # Log first 200 chars of code

        # Create isolated environment
        logger.info("2. Creating isolated environment")
        temp_dir, project_name = create_isolated_environment(code, language)
        session.temp_dir = str(temp_dir)
        logger.debug(f"2.1 Temporary directory created: {temp_dir}")

        if language == 'csharp':
            try:
                project_file = Path(session.temp_dir) / f"{project_name}.csproj"
                logger.info("3. Starting C# compilation")
                logger.debug(f"3.1 Project file: {project_file}")

                # Enhanced compilation command with better error handling
                compile_cmd = [
                    'dotnet', 'build',
                    str(project_file),
                    '--configuration', 'Release',
                    '--nologo',
                    '/p:GenerateFullPaths=true',
                    '/consoleloggerparameters:NoSummary;Verbosity=detailed'
                ]
                logger.debug(f"3.2 Compilation command: {' '.join(compile_cmd)}")

                # Run compilation with timeout
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(session.temp_dir)
                )

                # Log compilation output for debugging
                logger.debug(f"3.3 Compilation stdout:\n{compile_process.stdout}")
                logger.debug(f"3.4 Compilation stderr:\n{compile_process.stderr}")

                if compile_process.returncode != 0:
                    errors = parse_csharp_errors(compile_process.stderr or compile_process.stdout)
                    for error in errors:
                        session.error_tracker.add_error(error)
                    error_summary = session.error_tracker.get_summary()
                    logger.error("4. Compilation failed")
                    logger.error(f"4.1 Error summary: {json.dumps(error_summary, indent=2)}")
                    cleanup_session(session.session_id)
                    return {
                        'success': False,
                        'error': json.dumps(error_summary, indent=2),
                        'metrics': session.metrics.to_dict()
                    }

                logger.info("4. Compilation successful")
                dll_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / f"{project_name}.dll"
                logger.debug(f"4.1 DLL path: {dll_path}")

                # Create PTY for interactive I/O
                logger.info("5. Setting up interactive console")
                master_fd, slave_fd = create_pty()
                session.master_fd = master_fd
                session.slave_fd = slave_fd
                logger.debug(f"5.1 PTY created: master_fd={master_fd}, slave_fd={slave_fd}")

                # Start the program with PTY support
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
                    'interactive': True,
                    'metrics': session.metrics.to_dict()
                }

            except subprocess.TimeoutExpired:
                cleanup_session(session.session_id)
                logger.error("C# compilation timed out")
                return {
                    'success': False,
                    'error': f"Compilation timed out after {MAX_COMPILATION_TIME} seconds",
                    'metrics': session.metrics.to_dict()
                }

        elif language == 'cpp':
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
                    'error': f"Compilation Error: {error_msg}",
                    'metrics': session.metrics.to_dict()
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
                    'interactive': True,
                    'metrics': session.metrics.to_dict()
                }

            except Exception as e:
                logger.error(f"Error starting C++ process: {e}")
                cleanup_session(session.session_id)
                return {
                    'success': False,
                    'error': f"Process Error: {str(e)}",
                    'metrics': session.metrics.to_dict()
                }

        else:
            return {
                'success': False,
                'error': f"Interactive mode not supported for {language}",
                'metrics': session.metrics.to_dict()
            }

    except Exception as e:
        if session and session.session_id in active_sessions:
            cleanup_session(session.session_id)
        logger.error(f"Error in start_interactive_session: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'metrics': session.metrics.to_dict() if session else {}
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
            session.metrics.end_time = time.time()
            cleanup_session(session_id)
            return {
                'success': True,
                'output': output,
                'session_ended': True,
                'metrics': session.metrics.to_dict()
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
            'session_ended': False,
            'metrics': session.metrics.to_dict()
        }

    except Exception as e:
        logger.error(f"Error getting output: {str(e)}")
        return {'success': False, 'error': str(e)}

# Add active_sessions at the top level after other imports
active_sessions: Dict[str, CompilerSession] = {}
session_lock = Lock()

def cleanup_session(session_id: str) -> None:
    """Clean up resources for a session with proper PTY cleanup"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        logger.debug(f"Cleaning up session {session_id}")
        try:
            # Cleanup process
            if session.process and session.process.poll() is None:
                try:
                    session.process.terminate()
                    session.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(session.process.pid), signal.SIGKILL)
                session.process = None

            # Close PTY file descriptors
            if session.master_fd is not None:
                try:
                    os.close(session.master_fd)
                except OSError:
                    pass
                session.master_fd = None
            if session.slave_fd is not None:
                try:
                    os.close(session.slave_fd)
                except OSError:
                    pass
                session.slave_fd = None

            # Stop output monitoring thread
            if session.output_thread and session.output_thread.is_alive():
                # Signal thread to stop
                session.output_thread.join(timeout=1)
                session.output_thread = None

            # Cleanup temp directory
            if session.temp_dir and os.path.exists(session.temp_dir):
                try:
                    shutil.rmtree(session.temp_dir)
                except OSError as e:
                    logger.error(f"Error cleaning up temp directory: {e}")

            # Remove from active sessions
            del active_sessions[session_id]
            logger.debug(f"Session {session_id} cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")
            # Ensure session is removed from active sessions even if cleanup fails
            if session_id in active_sessions:
                del active_sessions[session_id]

# Constants for timeouts and intervals
MAX_COMPILATION_TIME = 30  # seconds
MAX_SESSION_LIFETIME = 3600  # 1 hour
CLEANUP_INTERVAL = 300  # 5 minutes

def create_isolated_environment(code: str, language: str) -> tuple[Path, str]:
    """Create an isolated environment for compilation and execution"""
    logger.debug(f"Creating isolated environment for {language}")

    # Create temp directory with unique prefix for each compilation
    temp_dir = Path(tempfile.mkdtemp(prefix='compiler_cache/compile_'))
    logger.debug(f"Created temp directory: {temp_dir}")

    if language == 'csharp':
        # Generate unique project name
        project_name = f"Project_{temp_dir.name.split('_')[-1]}"

        # Write source code
        source_file = temp_dir / "Program.cs"
        logger.debug(f"Writing C# source code to {source_file}")
        with open(source_file, 'w', encoding='utf-8') as f:
            # Wrap code in namespace to avoid conflicts
            wrapped_code = f"""namespace {project_name}
{{
    public class Program
    {{
        {code}
    }}
}}"""
            f.write(wrapped_code)
        logger.debug("Source code written successfully")

        # Create project file
        project_file = temp_dir / f"{project_name}.csproj"
        logger.debug(f"Creating project file: {project_file}")
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Program.cs" />
  </ItemGroup>
</Project>"""
        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(project_content)
        logger.debug("Project file created successfully")

        return temp_dir, project_name

    elif language == 'cpp':
        # Write source code
        source_file = temp_dir / "program.cpp"
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)
        return temp_dir, "program"
    else:
        raise ValueError(f"Unsupported language: {language}")

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
        # Create or get session
        session = None
        if session_id:
            with session_lock:
                if session_id in active_sessions:
                    session = active_sessions[session_id]
                else:
                    temp_dir = tempfile.mkdtemp(prefix=f'compiler_session_{session_id}_')
                    session = CompilerSession(session_id, temp_dir)
                    active_sessions[session_id] = session
        else:
            # Generate new session ID for interactive code
            session_id = str(uuid.uuid4())
            temp_dir = tempfile.mkdtemp(prefix=f'compiler_session_{session_id}_')
            session = CompilerSession(session_id, temp_dir)
            with session_lock:
                active_sessions[session_id] = session

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

def format_csharp_error(error_output: str) -> List[CompilationError]:
    """Enhanced C# error parsing with improved pattern matching"""
    errors = []

    # More comprehensive error pattern matching
    patterns = [
        r'(.*?)\((\d+),(\d+)\):\s*(warning|error)\s*(CS\d+):\s*(.+?)(?=\[|$)',  # Standard format
        r'(.*?):\s*(warning|error)\s*(CS\d+):\s*(.+)',  # Alternate format
        r'Unhandled\s+Exception:\s*([^:]+):\s*(.+)'  # Runtime exception format
    ]

    for line in error_output.splitlines():
        line = line.strip()
        if not line:
            continue

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    if len(match.groups()) == 6:  # Standard format
                        file_path, line_num, col_num, level, code, message = match.groups()
                        error = CompilationError(
                            error_type=level,
                            message=message.strip(),
                            file=os.path.basename(file_path),
                            line=int(line_num),
                            column=int(col_num),
                            code=code
                        )
                    elif len(match.groups()) == 4:  # Alternate format
                        file_path, level, code, message = match.groups()
                        error = CompilationError(
                            error_type=level,
                            message=message.strip(),
                            file=os.path.basename(file_path) if file_path else "unknown",
                            line=0,
                            column=0,
                            code=code
                        )
                    else:  # Runtime exception
                        exc_type, message = match.groups()
                        error = CompilationError(
                            error_type="runtime_error",
                            message=message.strip(),
                            file="runtime",
                            line=0,
                            column=0,
                            code=exc_type.replace(".", "_")
                        )
                    errors.append(error)
                    error_logger.error(f"Compilation {error.error_type}: {error.to_dict()}")
                except Exception as e:
                    error_logger.error(f"Error parsing compilation output: {e}")
                break

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