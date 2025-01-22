import os
import subprocess
import tempfile
import logging
import traceback
from typing import Dict, Optional, Any, List, Tuple
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import hashlib
import shutil
from threading import Lock
import psutil
import re
import pty
import uuid
import signal
import fcntl
import termios
import struct
import select
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
MAX_COMPILATION_TIME = 20
MAX_EXECUTION_TIME = 5
MEMORY_LIMIT = 512
MAX_PARALLEL_COMPILATIONS = min(os.cpu_count() or 4, 8)
CACHE_DIR = "/tmp/compiler_cache"
CACHE_SIZE_LIMIT = 1024 * 1024 * 1024

# Initialize cache
os.makedirs(CACHE_DIR, exist_ok=True)
cache_lock = Lock()

# Active interactive sessions
active_sessions = {}
session_lock = Lock()

class InteractiveSession:
    def __init__(self, process, master_fd, slave_fd):
        self.process = process
        self.master_fd = master_fd
        self.slave_fd = slave_fd
        self.stdout_buffer = []
        self.stderr_buffer = []
        self.waiting_for_input = False
        self.last_activity = time.time()
        self.partial_line = ""
        self.input_patterns = {
            'cpp': [
                'cin', 'std::cin', 'getline', 'scanf',
                'enter', 'input', '?', ':'
            ],
            'csharp': [
                'Console.Read', 'Console.ReadLine',
                'ReadKey', 'enter', 'input', '?', ':'
            ]
        }
        self.output_buffer_size = 8192
        self.encoding = 'utf-8'

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced compile and run function with interactive session support"""
    logger.info(f"Starting compile_and_run for {language}")

    if not code:
        return {
            'success': False,
            'error': "No code provided"
        }

    try:
        # Check if code is interactive
        if is_interactive_code(code, language):
            logger.info("Detected interactive code, starting interactive session")
            return start_interactive_session(code, language)

        # Non-interactive compilation and execution
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if language == 'cpp':
                source_file = temp_path / "program.cpp"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile with optimizations and warning flags
                compile_process = subprocess.run(
                    ['g++', '-std=c++17', '-Wall', '-O2', str(source_file), '-o', str(temp_path / "program")],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_cpp_error(compile_process.stderr)
                    }

                process = subprocess.run(
                    [str(temp_path / "program")],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME
                )

            elif language == 'csharp':
                logger.debug("Starting C# compilation process")
                source_file = temp_path / "Program.cs"
                logger.debug(f"Writing source to: {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Create optimized project file
                project_file = temp_path / "program.csproj"
                logger.debug(f"Creating project file: {project_file}")
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
                logger.debug("Project file created successfully")

                # Compile C# code
                logger.debug("Starting dotnet build process")
                compile_process = subprocess.run(
                    ['dotnet', 'build', str(project_file), '--nologo', '-c', 'Release', '-v', 'd'],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                logger.debug(f"Build process completed with return code: {compile_process.returncode}")
                if compile_process.stdout:
                    logger.debug(f"Build output: {compile_process.stdout}")
                if compile_process.stderr:
                    logger.debug(f"Build errors: {compile_process.stderr}")

                if compile_process.returncode != 0:
                    error_msg = format_csharp_error(compile_process.stderr)
                    logger.error(f"C# compilation failed: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg
                    }

                logger.debug("Starting program execution")
                process = subprocess.run(
                    ['dotnet', 'run', '--project', str(project_file), '--no-build'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path)
                )

            if process.returncode != 0:
                return {
                    'success': False,
                    'error': process.stderr
                }

            return {
                'success': True,
                'output': process.stdout
            }

    except subprocess.TimeoutExpired as e:
        logger.error(f"Process timed out: {str(e)}")
        return {
            'success': False,
            'error': "Process timed out"
        }
    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def start_interactive_session(code: str, language: str) -> Dict[str, Any]:
    """Enhanced interactive session startup"""
    logger.info(f"Starting interactive session for {language}")

    try:
        session_id = str(uuid.uuid4())
        logger.debug(f"Session ID: {session_id}")

        # Create PTY with proper terminal settings
        master_fd, slave_fd = pty.openpty()
        logger.debug(f"PTY created for {language}: master_fd={master_fd}, slave_fd={slave_fd}")

        # Set terminal size and attributes
        term_size = struct.pack('HHHH', 24, 80, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, term_size)

        # Set raw mode for better input handling
        attr = termios.tcgetattr(slave_fd)
        attr[0] = attr[0] & ~termios.ICRNL  # Don't translate CR to NL on input
        attr[1] = attr[1] & ~termios.ONLCR  # Don't translate NL to CRNL on output
        attr[3] = attr[3] & ~(termios.ICANON | termios.ECHO)  # Raw mode
        termios.tcsetattr(slave_fd, termios.TCSANOW, attr)

        # Create a unique temporary directory for this session
        unique_dir = os.path.join(CACHE_DIR, f"session_{session_id}")
        os.makedirs(unique_dir, exist_ok=True)
        logger.debug(f"Created session directory: {unique_dir}")

        with tempfile.TemporaryDirectory(dir=unique_dir) as temp_dir:
            temp_path = Path(temp_dir)
            unique_id = hashlib.md5(code.encode()).hexdigest()[:8]

            if language == 'cpp':
                source_file = temp_path / f"program_{unique_id}.cpp"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile with optimizations and warning flags
                compile_process = subprocess.run(
                    ['g++', '-std=c++17', '-Wall', '-O2', str(source_file), '-o', str(temp_path / f"program_{unique_id}")],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_cpp_error(compile_process.stderr)
                    }

                process = subprocess.Popen(
                    [str(temp_path / f"program_{unique_id}")],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True
                )
                logger.debug(f"C++ Process started with PID: {process.pid}")

            elif language == 'csharp':
                # Create unique namespace for this session to avoid conflicts
                namespace_name = f"InteractiveSession_{unique_id}"

                # Modify the code to use the unique namespace
                code_lines = code.split('\n')
                modified_code = []
                namespace_added = False

                for line in code_lines:
                    if 'class Program' in line and not namespace_added:
                        modified_code.extend([
                            f"namespace {namespace_name} {{",
                            line
                        ])
                        namespace_added = True
                    else:
                        modified_code.append(line)

                if namespace_added:
                    modified_code.append("}")  # Close namespace

                source_file = temp_path / "Program.cs"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(modified_code))

                # Create optimized project file with unique assembly name
                project_file = temp_path / "program.csproj"
                project_content = f"""<Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <OutputType>Exe</OutputType>
                    <TargetFramework>net7.0</TargetFramework>
                    <ImplicitUsings>enable</ImplicitUsings>
                    <Nullable>enable</Nullable>
                    <PublishReadyToRun>true</PublishReadyToRun>
                    <RootNamespace>{namespace_name}</RootNamespace>
                    <AssemblyName>{namespace_name}</AssemblyName>
                  </PropertyGroup>
                </Project>"""

                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                # Compile C# code
                compile_process = subprocess.run(
                    ['dotnet', 'build', str(project_file), '--nologo', '-c', 'Release'],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(temp_path)
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr)
                    }

                process = subprocess.Popen(
                    ['dotnet', 'run', '--project', str(project_file), '--no-build'],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=str(temp_path)
                )
                logger.debug(f"C# Process started with PID: {process.pid}")

            else:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

            # Create and store session
            session = InteractiveSession(process, master_fd, slave_fd)
            session.language = language  # Store language for pattern matching
            with session_lock:
                active_sessions[session_id] = session

            # Start output monitoring in a separate thread
            monitor_thread = threading.Thread(
                target=monitor_output,
                args=(session_id,),
                daemon=True
            )
            monitor_thread.start()
            logger.debug("Output monitoring thread started")

            return {
                'success': True,
                'interactive': True,
                'session_id': session_id
            }

    except Exception as e:
        logger.error(f"Error starting interactive session: {str(e)}\n{traceback.format_exc()}")
        if 'session_id' in locals() and session_id in active_sessions:
            cleanup_session(session_id)
        return {
            'success': False,
            'error': str(e)
        }

def handle_interactive_session(session_id: str, action: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """Handle interactive session actions"""
    try:
        with session_lock:
            session = active_sessions.get(session_id)
            if not session:
                return {
                    'success': False,
                    'error': "Session not found"
                }

        if action == 'get_output':
            output = ''.join(session.stdout_buffer)
            session.stdout_buffer.clear()
            return {
                'success': True,
                'output': output,
                'waiting_for_input': session.waiting_for_input
            }

        elif action == 'send_input':
            if not input_data:
                return {
                    'success': False,
                    'error': "No input data provided"
                }

            try:
                os.write(session.master_fd, input_data.encode())
                session.waiting_for_input = False
                return {'success': True}
            except OSError as e:
                logger.error(f"Error sending input: {e}")
                return {
                    'success': False,
                    'error': "Failed to send input"
                }

        elif action == 'terminate':
            cleanup_session(session_id)
            return {'success': True}

        return {
            'success': False,
            'error': f"Unknown action: {action}"
        }

    except Exception as e:
        logger.error(f"Error handling interactive session: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def monitor_output(session_id: str):
    """Enhanced output monitoring for interactive sessions"""
    chunk_size = 1024
    try:
        with session_lock:
            session = active_sessions.get(session_id)
            if not session:
                return

        while True:
            try:
                # Check if process is still running
                if session.process.poll() is not None:
                    cleanup_session(session_id)
                    break

                # Read output from master PTY with timeout
                ready, _, _ = select.select([session.master_fd], [], [], 0.1)
                if not ready:
                    continue

                data = os.read(session.master_fd, chunk_size)
                if data:
                    try:
                        # Process output with improved encoding handling
                        decoded = data.decode(session.encoding, errors='replace')
                        session.partial_line += decoded

                        # Process complete lines
                        if '\n' in session.partial_line or '\r' in session.partial_line:
                            lines = session.partial_line.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                            session.partial_line = lines[-1]  # Keep incomplete line
                            complete_lines = lines[:-1]  # Process complete lines

                            for line in complete_lines:
                                if line.strip():  # Only process non-empty lines
                                    session.stdout_buffer.append(line + '\n')

                            # Trim buffer if it gets too large
                            if len(session.stdout_buffer) > session.output_buffer_size:
                                session.stdout_buffer = session.stdout_buffer[-session.output_buffer_size:]

                        # Check for input prompts in both partial and complete lines
                        current_text = session.partial_line
                        if not session.waiting_for_input:
                            # Get language-specific patterns
                            patterns = session.input_patterns.get(
                                getattr(session, 'language', ''), 
                                session.input_patterns['csharp']  # Default to C# patterns
                            )

                            # Check for input patterns
                            if any(pattern.lower() in current_text.lower() for pattern in patterns):
                                session.waiting_for_input = True
                                logger.debug(f"Input prompt detected: {current_text}")

                    except Exception as e:
                        logger.error(f"Error processing output: {e}")
                        continue

            except (OSError, IOError) as e:
                if e.errno == 5:  # Input/output error, usually due to closed PTY
                    cleanup_session(session_id)
                    break
                logger.error(f"Error reading from PTY: {e}")
                continue

    except Exception as e:
        logger.error(f"Error in monitor_output: {e}")
        cleanup_session(session_id)

def cleanup_session(session_id: str):
    """Clean up an interactive session"""
    try:
        with session_lock:
            session = active_sessions.pop(session_id, None)
            if session:
                try:
                    session.process.terminate()
                    session.process.wait(timeout=1)
                except:
                    try:
                        session.process.kill()
                    except:
                        pass

                try:
                    os.close(session.master_fd)
                except:
                    pass
                try:
                    os.close(session.slave_fd)
                except:
                    pass

    except Exception as e:
        logger.error(f"Error cleaning up session {session_id}: {e}")

def is_interactive_code(code: str, language: str) -> bool:
    """Check if code contains interactive I/O operations"""
    code = code.lower()

    if language == 'cpp':
        return any(pattern in code for pattern in [
            'cin', 'getline',
            'std::cin', 'std::getline',
            'scanf', 'gets', 'fgets'
        ])
    elif language == 'csharp':
        return any(pattern in code for pattern in [
            'console.read', 'console.readline',
            'console.in', 'console.keyavailable',
            'console.readkey'
        ])
    return False

def format_cpp_error(error_msg: str) -> str:
    """Format C++ error messages"""
    if not error_msg:
        return "Unknown C++ compilation error"

    # Extract relevant error information
    error_lines = []
    for line in error_msg.splitlines():
        if ': error:' in line or ': fatal error:' in line:
            # Remove file paths for cleaner output
            cleaned = re.sub(r'^.*?:', '', line).strip()
            error_lines.append(f"Compilation Error: {cleaned}")

    return "\n".join(error_lines) if error_lines else error_msg.strip()

def format_csharp_error(error_msg: str) -> str:
    """Format C# error messages with improved detail"""
    if not error_msg:
        return "Unknown C# compilation error"

    logger.debug(f"Formatting C# error message: {error_msg}")

    # Extract relevant error information
    error_lines = []
    for line in error_msg.splitlines():
        if "error CS" in line:
            # Extract error code and message
            match = re.search(r'error (CS\d+):\s*(.+?)(\[|$)', line)
            if match:
                error_code, message = match.group(1), match.group(2)
                error_lines.append(f"Compilation Error ({error_code}): {message.strip()}")
            else:
                # If regex doesn't match, include the whole error line
                error_lines.append(f"Compilation Error: {line.strip()}")
        elif "Unhandled exception" in line:
            error_lines.append("Runtime Error: Program crashed during execution")
        elif "Build FAILED" in line or "error MSB" in line:
            # Include MSBuild errors
            error_lines.append(f"Build Error: {line.strip()}")

    formatted_error = "\n".join(error_lines) if error_lines else error_msg.strip()
    logger.debug(f"Formatted error message: {formatted_error}")
    return formatted_error

def get_cache_key(code: str) -> str:
    """Generate a unique cache key for the code"""
    return hashlib.sha256(code.encode()).hexdigest()

def cleanup_old_cache():
    """Remove old cache entries when size limit is exceeded"""
    try:
        with cache_lock:
            total_size = 0
            cache_entries = []

            # Get all cache entries with their timestamps
            cache_dir = Path(CACHE_DIR)
            for entry in cache_dir.iterdir():
                if entry.is_dir():
                    try:
                        size = sum(f.stat().st_size for f in entry.rglob('*'))
                        mtime = entry.stat().st_mtime
                        cache_entries.append((entry, size, mtime))
                        total_size += size
                    except OSError as e:
                        logger.warning(f"Error processing cache entry {entry}: {e}")
                        continue

            # If size limit exceeded, remove oldest entries
            if total_size > CACHE_SIZE_LIMIT:
                # Sort by access time (oldest first)
                cache_entries.sort(key=lambda x: x[2])

                # Remove entries until we're under the limit
                for entry_path, entry_size, _ in cache_entries:
                    if total_size <= CACHE_SIZE_LIMIT:
                        break
                    try:
                        if entry_path.exists():
                            shutil.rmtree(str(entry_path))
                            total_size -= entry_size
                    except OSError as e:
                        logger.warning(f"Failed to remove cache entry {entry_path}: {e}")
                        continue

    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")

class ParallelCompilationManager:
    """Manage parallel compilation resources and execution"""
    def __init__(self, max_workers: int = MAX_PARALLEL_COMPILATIONS):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures: List[Future] = []
        self.results: Dict[int, Dict[str, Any]] = {}

    def submit_compilation(self, idx: int, code: str, language: str):
        """Submit a compilation task"""
        future = self.executor.submit(self._compile_single, idx, code, language)
        self.futures.append(future)

    def _compile_single(self, idx: int, code: str, language: str) -> Tuple[int, Dict[str, Any]]:
        """Compile a single file with resource management"""
        start_time = time.time()
        try:
            # Monitor and limit resource usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss

            # Use optimized compilation settings
            env = os.environ.copy()
            env.update({
                'DOTNET_MULTILEVEL_LOOKUP': '0',
                'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1',
                'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
                'DOTNET_ReadyToRun': '1',
                'DOTNET_TC_QuickJitForLoops': '1',
                'DOTNET_GCHeapCount': str(min(os.cpu_count() or 2, 4)),
                'DOTNET_GCHighMemPercent': '85',
                'DOTNET_GCNoAffinitize': '1',
                'DOTNET_TieredPGO': '1'
            })

            result = compile_and_run(code, language, env)

            # Add resource usage metrics
            current_memory = process.memory_info().rss
            result['metrics'].update({
                'memory_usage': (current_memory - initial_memory) / (1024 * 1024),  # MB
                'total_time': time.time() - start_time
            })

            return idx, result

        except Exception as e:
            logger.error(f"Failed to compile file {idx}: {e}")
            return idx, {
                'success': False,
                'error': f"Compilation failed: {str(e)}",
                'metrics': {
                    'compilation_time': time.time() - start_time,
                    'execution_time': 0,
                    'total_time': time.time() - start_time
                }
            }

    def wait_for_completions(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Wait for all compilations to complete and return results"""
        try:
            for future in as_completed(self.futures, timeout=timeout):
                try:
                    idx, result = future.result()
                    self.results[idx] = result
                except Exception as e:
                    logger.error(f"Error in parallel compilation: {e}")
        finally:
            self.executor.shutdown(wait=False)

        # Return results in original order
        return [self.results.get(i, {
            'success': False,
            'error': 'Compilation task not completed',
            'metrics': {}
        }) for i in range(len(self.futures))]

def compile_and_run_parallel(codes: List[str], language: str = 'csharp') -> List[Dict[str, Any]]:
    """
    Optimized parallel compilation with improved resource management
    """
    if not codes:
        return []

    if language != 'csharp':
        return [{'success': False, 'error': f'Language {language} not supported for parallel compilation'}] * len(codes)

    logger.info(f"Starting parallel compilation for {len(codes)} files")
    start_time = time.time()

    try:
        manager = ParallelCompilationManager()

        # Submit all compilation tasks
        for idx, code in enumerate(codes):
            manager.submit_compilation(idx, code, language)

        # Wait for results with timeout
        timeout = max(MAX_COMPILATION_TIME * len(codes) / MAX_PARALLEL_COMPILATIONS, MAX_COMPILATION_TIME)
        results = manager.wait_for_completions(timeout=timeout)

        total_time = time.time() - start_time
        logger.info(f"Parallel compilation completed in {total_time:.2f}s")

        return results

    except Exception as e:
        logger.error(f"Parallel compilation failed: {e}")
        return [{'success': False, 'error': str(e)}] * len(codes)


def get_template(language: str) -> str:
    """Get the template code for a given programming language.

    Args:
        language (str): The programming language identifier ('cpp' or 'csharp')

    Returns:
        str: The template code for the specified language
    """
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

class Program {
    static void Main() {
        // Your code here
        Console.WriteLine("Hello World!");
    }
}"""
    }
    return templates.get(language.lower(), '')