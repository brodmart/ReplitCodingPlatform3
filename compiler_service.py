import os
import signal
import logging
import tempfile
import threading
import subprocess
import time
import importlib.util
from typing import Dict, Any, Optional, List, Union
from threading import Lock, Thread, Event
from pathlib import Path
import psutil
from datetime import datetime
import traceback
import uuid
import select
import fcntl
import errno
import re
import json
import shutil
from dataclasses import dataclass, field, asdict

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)
performance_logger = logging.getLogger('performance')
error_logger = logging.getLogger('error')

# Constants
MAX_COMPILATION_TIME = 30  # seconds
MAX_EXECUTION_TIME = 30  # seconds
MEMORY_LIMIT = 1024  # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"
CACHE_MAX_SIZE = 50  # Maximum number of cached compilations

# Initialize cache directory
os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
_compilation_cache = {}
_cache_lock = Lock()

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
class CompilerSession:
    """Manages a compilation/execution session"""
    session_id: str
    temp_dir: str
    process: Optional[subprocess.Popen] = None
    output_thread: Optional[Thread] = None
    output_buffer: List[str] = field(default_factory=list)
    waiting_for_input: bool = False
    stop_event: Event = field(default_factory=Event)
    _access_lock: Lock = field(default_factory=Lock)
    _cleanup_lock: Lock = field(default_factory=Lock)
    _input_ready: Event = field(default_factory=Event)

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
            # Check if this output contains input prompts
            lowercase_text = text.lower()
            if (any(prompt in lowercase_text for prompt in
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

    def set_waiting_for_input(self, value: bool) -> None:
        """Thread-safe method to set waiting_for_input"""
        with self._access_lock:
            prev_state = self.waiting_for_input
            self.waiting_for_input = value
            if value and not prev_state:
                self._input_ready.set()
                logger.debug(f"Session {self.session_id} is now waiting for input")
            elif not value and prev_state:
                self._input_ready.clear()
                logger.debug(f"Session {self.session_id} is no longer waiting for input")

    def wait_for_input_prompt(self, timeout: float = 5.0) -> bool:
        """Wait for input prompt to appear"""
        return self._input_ready.wait(timeout)

    def cleanup(self) -> None:
        """Clean up session resources"""
        with self._cleanup_lock:
            logger.debug(f"Starting cleanup for session {self.session_id}")
            self.stop_event.set()
            self._input_ready.set()  # Unblock any waiting threads

            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Process {self.session_id} didn't terminate, force killing")
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error killing process: {e}")

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
        temp_dir = tempfile.mkdtemp(prefix=f'compiler_{new_session_id}_')
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
    """Start an interactive session"""
    logger.info(f"Starting {language} interactive session {session.session_id}")

    if language != 'csharp':
        return {'success': False, 'error': 'Only C# is supported'}

    try:
        # Create project structure
        project_dir = Path(session.temp_dir)
        source_file = project_dir / "Program.cs"
        project_file = project_dir / "program.csproj"

        # Write project file
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

        # Write source file
        with open(source_file, 'w') as f:
            f.write(code)

        # Compile
        logger.debug("Compiling C# program")
        compile_result = subprocess.run(
            ['dotnet', 'build', str(project_file), '--nologo'],
            capture_output=True,
            text=True,
            cwd=session.temp_dir
        )

        if compile_result.returncode != 0:
            logger.error(f"Compilation failed: {compile_result.stderr}")
            return {'success': False, 'error': compile_result.stderr}

        # Start the compiled program
        executable = project_dir / "bin" / "Debug" / "net7.0" / "program.dll"
        process = subprocess.Popen(
            ['dotnet', str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            cwd=session.temp_dir
        )

        session.process = process

        def monitor_output():
            """Monitor process output"""
            try:
                while not session.stop_event.is_set() and process.poll() is None:
                    if process.stdout is None:
                        time.sleep(0.1)
                        continue

                    # Use select to check for available data
                    rlist, _, _ = select.select([process.stdout], [], [], 0.1)
                    if not rlist:
                        continue

                    line = process.stdout.readline()
                    if line:
                        cleaned = line.strip()
                        if cleaned:
                            logger.debug(f"Output received: {cleaned}")
                            session.append_output(cleaned)
                    else:
                        time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in output monitoring: {e}")

        # Start output monitoring
        session.output_thread = Thread(target=monitor_output)
        session.output_thread.daemon = True
        session.output_thread.start()

        # Wait briefly for initial output
        time.sleep(0.5)

        return {
            'success': True,
            'session_id': session.session_id,
            'interactive': True
        }

    except Exception as e:
        logger.error(f"Session start error: {traceback.format_exc()}")
        return {'success': False, 'error': str(e)}

def send_input(session_id: str, input_text: str) -> Dict[str, Any]:
    """Send input to an interactive session"""
    try:
        with session_lock:
            if session_id not in active_sessions:
                return {'success': False, 'error': 'Invalid session'}

            session = active_sessions[session_id]
            if not session.is_active():
                return {'success': False, 'error': 'Session not active'}

            # Wait for input prompt if not already waiting
            if not session.waiting_for_input:
                if not session.wait_for_input_prompt(timeout=5.0):
                    return {'success': False, 'error': 'Timeout waiting for input prompt'}

            # Ensure input ends with newline
            if not input_text.endswith('\n'):
                input_text += '\n'

            if session.process and session.process.stdin:
                session.process.stdin.write(input_text)
                session.process.stdin.flush()
                session.set_waiting_for_input(False)
                logger.debug(f"Input sent: {input_text.strip()}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Process not ready for input'}

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

def is_interactive_code(code: str, language: str) -> bool:
    """Determine if code requires interactive I/O based on language-specific patterns"""
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

importlib.util.find_spec("hashlib")
importlib.util.find_spec("dataclasses")
importlib.util.find_spec("json")
importlib.util.find_spec("re")

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

def create_isolated_environment(code: str, language: str) -> tuple[Path, str]:
    """Create isolated environment for compilation with improved project setup"""
    temp_dir = Path(tempfile.mkdtemp(prefix=f'compiler_env_{language}_'))
    project_name = "program"

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