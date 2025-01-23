import os
import subprocess
import logging
import pty
import select
import uuid
from threading import Lock

# Basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Simple session management
active_sessions = {}
session_lock = Lock()

class InteractiveSession:
    def __init__(self, process, master_fd, slave_fd):
        self.process = process
        self.master_fd = master_fd
        self.slave_fd = slave_fd
        self.output_buffer = []
        self.waiting_for_input = False
        self.input_patterns = ['Console.Read', 'Console.ReadLine', 'Enter']

def compile_and_run(code: str, language: str = 'csharp', session_id: str = None) -> dict:
    """Simplified compilation and execution function"""
    if not code:
        return {'success': False, 'error': "No code provided"}

    if language != 'csharp':
        return {'success': False, 'error': "Only C# is supported"}

    try:
        session_id = session_id or str(uuid.uuid4())
        master_fd, slave_fd = pty.openpty()

        # Create C# project and compile
        with open('Program.cs', 'w') as f:
            f.write(code)

        # Simple project file
        with open('program.csproj', 'w') as f:
            f.write("""<Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup>
                <OutputType>Exe</OutputType>
                <TargetFramework>net7.0</TargetFramework>
              </PropertyGroup>
            </Project>""")

        # Compile
        compile_result = subprocess.run(
            ['dotnet', 'build', 'program.csproj', '--nologo'],
            capture_output=True,
            text=True
        )

        if compile_result.returncode != 0:
            return {'success': False, 'error': compile_result.stderr}

        # Run the compiled program
        process = subprocess.Popen(
            ['dotnet', 'run', '--no-build'],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True
        )

        # Create and store session
        session = InteractiveSession(process, master_fd, slave_fd)
        with session_lock:
            active_sessions[session_id] = session

        return {
            'success': True,
            'session_id': session_id,
            'interactive': True
        }

    except Exception as e:
        logger.error(f"Error in compile_and_run: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> dict:
    """Get output from the session"""
    try:
        with session_lock:
            session = active_sessions.get(session_id)
            if not session:
                return {'success': False, 'error': "Session not found"}

        # Read output with timeout
        ready, _, _ = select.select([session.master_fd], [], [], 0.1)
        output = ''

        if ready:
            try:
                data = os.read(session.master_fd, 1024)
                if data:
                    output = data.decode()
                    session.waiting_for_input = any(pattern in output for pattern in session.input_patterns)
            except OSError:
                pass

        return {
            'success': True,
            'output': output,
            'waiting_for_input': session.waiting_for_input
        }

    except Exception as e:
        logger.error(f"Error getting output: {str(e)}")
        return {'success': False, 'error': str(e)}

def send_input(session_id: str, input_data: str) -> dict:
    """Send input to the session"""
    try:
        with session_lock:
            session = active_sessions.get(session_id)
            if not session:
                return {'success': False, 'error': "Session not found"}

        if not input_data.endswith('\n'):
            input_data += '\n'

        os.write(session.master_fd, input_data.encode())
        return {'success': True}

    except Exception as e:
        logger.error(f"Error sending input: {str(e)}")
        return {'success': False, 'error': str(e)}

def cleanup_session(session_id: str):
    """Clean up a session"""
    try:
        with session_lock:
            session = active_sessions.pop(session_id, None)
            if session:
                session.process.terminate()
                try:
                    os.close(session.master_fd)
                    os.close(session.slave_fd)
                except:
                    pass
    except Exception as e:
        logger.error(f"Error cleaning up session: {str(e)}")


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
            'console.readkey', 'console.write'  # Added console.write
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
        return [{'success': False, 'error': f'Language {language} not supported for parallel compilation'} * len(codes)]

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

        totaltime = time.time() - start_time
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

from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from pathlib import Path
import hashlib
import shutil
from utils.compiler_logger import compiler_logger
import re
import time
import psutil

# Constants section update
MAX_COMPILATION_TIME = 30  # Increased from 20
MAX_EXECUTION_TIME = 10   # Increased from 5
MEMORY_LIMIT = 512
MAX_PARALLEL_COMPILATIONS = min(os.cpu_count() or 4, 8)
CACHE_DIR = "/tmp/compiler_cache"
CACHE_SIZE_LIMIT = 1024 * 1024 * 1024
CONNECTION_TIMEOUT = 45  # New timeout for socket connections
RETRY_ATTEMPTS = 3      # Number of retry attempts

# Initialize cache
os.makedirs(CACHE_DIR, exist_ok=True)
cache_lock = Lock()