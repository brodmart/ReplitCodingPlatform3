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

def compile_and_run(code: Optional[str] = None, 
                   language: Optional[str] = None,
                   input_data: Optional[str] = None,
                   session_id: Optional[str] = None,
                   action: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced compile and run function with interactive session support"""

    if session_id and action:
        return handle_interactive_session(session_id, action, input_data)

    if not code:
        return {
            'success': False,
            'error': "No code provided"
        }

    try:
        # Check if code is interactive
        if is_interactive_code(code, language):
            logger.info("Starting compile_and_run for interactive code")
            return start_interactive_session(code, language)

        # Non-interactive compilation and execution
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if language == 'cpp':
                source_file = temp_path / "program.cpp"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                executable = temp_path / "program"
                compile_process = subprocess.run(
                    ['g++', '-std=c++17', '-Wall', '-O3', str(source_file), '-o', str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_cpp_error(compile_process.stderr)
                    }

                run_process = subprocess.run(
                    [str(executable)],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME
                )

            elif language == 'csharp':
                source_file = temp_path / "Program.cs"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                compile_process = subprocess.run(
                    ['dotnet', 'build', str(source_file), '--nologo', '-o', str(temp_path)],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr)
                    }

                run_process = subprocess.run(
                    ['dotnet', 'run', '--project', str(source_file), '--no-build'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path)
                )

            if run_process.returncode != 0:
                return {
                    'success': False,
                    'error': run_process.stderr or "Execution failed"
                }

            return {
                'success': True,
                'output': run_process.stdout
            }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': "Execution timed out"
        }
    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def start_interactive_session(code: str, language: str) -> Dict[str, Any]:
    """Start an interactive session with proper PTY handling"""
    logger.info(f"Starting interactive session for {language}")

    try:
        session_id = str(uuid.uuid4())

        # Create PTY
        master_fd, slave_fd = pty.openpty()
        # Set terminal size
        term_size = struct.pack('HHHH', 24, 80, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, term_size)

        with tempfile.TemporaryDirectory(dir=CACHE_DIR) as temp_dir:
            temp_path = Path(temp_dir)

            if language == 'cpp':
                # Compile C++ code
                source_file = temp_path / "program.cpp"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                compile_process = subprocess.run(
                    ['g++', '-std=c++17', str(source_file), '-o', str(temp_path / "program")],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_cpp_error(compile_process.stderr)
                    }

                # Start the program
                process = subprocess.Popen(
                    [str(temp_path / "program")],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True
                )

            elif language == 'csharp':
                # Set up C# project
                source_file = temp_path / "Program.cs"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile C# code
                compile_process = subprocess.run(
                    ['dotnet', 'build', str(source_file), '--nologo', '-o', str(temp_path)],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(compile_process.stderr)
                    }

                # Start the program
                process = subprocess.Popen(
                    ['dotnet', 'run', '--project', str(source_file), '--no-build'],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=str(temp_path)
                )

            else:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

            # Create and store session
            session = InteractiveSession(process, master_fd, slave_fd)
            with session_lock:
                active_sessions[session_id] = session

            # Start output monitoring in a separate thread
            monitor_thread = threading.Thread(
                target=monitor_output,
                args=(session_id,),
                daemon=True
            )
            monitor_thread.start()

            return {
                'success': True,
                'interactive': True,
                'session_id': session_id
            }

    except Exception as e:
        logger.error(f"Error starting interactive session: {e}")
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
    """Monitor output from an interactive session"""
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

                # Read output from master PTY
                ready, _, _ = select.select([session.master_fd], [], [], 0.1)
                if not ready:
                    continue

                data = os.read(session.master_fd, chunk_size)
                if data:
                    try:
                        decoded = data.decode('utf-8', errors='replace')
                        session.stdout_buffer.append(decoded)

                        # Check for input prompts
                        if not session.waiting_for_input:
                            if any(pattern in decoded.lower() for pattern in [
                                'input', 'enter', '?', ':', 'cin', 'readline'
                            ]):
                                session.waiting_for_input = True

                    except Exception as e:
                        logger.error(f"Error processing output: {e}")
                        continue

            except (OSError, IOError) as e:
                logger.error(f"Error reading from PTY: {e}")
                cleanup_session(session_id)
                break

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
    """Format C# error messages"""
    if not error_msg:
        return "Unknown C# compilation error"

    # Extract relevant error information
    error_lines = []
    for line in error_msg.splitlines():
        if "error CS" in line:
            # Extract just the error message
            parts = line.split(': ', 1)
            if len(parts) > 1:
                error_lines.append(f"Compilation Error: {parts[1].strip()}")
        elif "Unhandled exception" in line:
            error_lines.append("Runtime Error: Program crashed during execution")

    return "\n".join(error_lines) if error_lines else error_msg.strip()

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