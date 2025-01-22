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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 20  # reduced from 30 to 20 seconds
MAX_EXECUTION_TIME = 5    # reduced from 10 to 5 seconds for simple programs
MEMORY_LIMIT = 512       # MB
MAX_PARALLEL_COMPILATIONS = min(os.cpu_count() or 4, 8)
CACHE_DIR = "/tmp/compiler_cache"
CACHE_SIZE_LIMIT = 1024 * 1024 * 1024  # 1GB cache size limit

# Initialize cache directory and lock
os.makedirs(CACHE_DIR, exist_ok=True)
cache_lock = Lock()

# Language templates
CPP_TEMPLATE = """#include <iostream>
#include <string>
using namespace std;

int main() {
    cout << "Hello World!" << endl;
    return 0;
}"""

CSHARP_TEMPLATE = """using System;

class Program {
    static void Main() {
        Console.WriteLine("Hello World!");
    }
}"""

def get_template(language: str) -> str:
    """Get the template code for a given language"""
    templates = {
        'cpp': CPP_TEMPLATE,
        'csharp': CSHARP_TEMPLATE
    }
    return templates.get(language, '')

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

def compile_and_run(code: str, language: str = 'csharp', input_data: Optional[str] = None) -> Dict[str, Any]:
    """Compile and run code with enhanced error handling"""
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compilation for {language}")

    if not code:
        return {
            'success': False,
            'error': "No code provided",
            'metrics': metrics
        }

    # Generate cache key for the code
    cache_key = get_cache_key(code)
    cache_dir = Path(CACHE_DIR) / cache_key

    try:
        # Check cache first
        if cache_dir.exists():
            logger.debug("Using cached compilation")
            if language == 'cpp':
                executable = cache_dir / "program"
            else:
                executable = cache_dir / "bin" / "Release" / "net7.0" / "program.dll"

            if executable.exists():
                # Run the cached executable
                run_process = subprocess.run(
                    [str(executable)] if language == 'cpp' else ['dotnet', 'run', '--no-build'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(cache_dir)
                )

                if run_process.returncode == 0:
                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'metrics': metrics
                    }

        # If not in cache or cache execution failed, compile normally
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if language == 'cpp':
                source_file = temp_path / "program.cpp"
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Compile C++ code with aggressive optimization
                executable = temp_path / "program"
                compile_process = subprocess.run(
                    ['g++', '-std=c++17', '-Wall', '-O3', '-march=native', 
                     str(source_file), '-o', str(executable)],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME
                )

                if compile_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_cpp_error(compile_process.stderr),
                        'metrics': metrics
                    }

                # Cache the successful compilation
                os.makedirs(cache_dir, exist_ok=True)
                shutil.copy2(executable, cache_dir / "program")

                # Run with resource limits
                run_process = subprocess.run(
                    [str(executable)],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME
                )

            elif language == 'csharp':
                source_file = temp_path / "Program.cs"
                project_file = temp_path / "program.csproj"

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
                    <TieredCompilation>true</TieredCompilation>
                    <Optimize>true</Optimize>
                  </PropertyGroup>
                </Project>"""
                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                # Build with optimized settings
                build_process = subprocess.run(
                    ['dotnet', 'build', str(project_file),
                     '--configuration', 'Release',
                     '--nologo',
                     '/p:GenerateFullPaths=true',
                     '/consoleloggerparameters:NoSummary'],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(temp_path),
                    env={
                        **os.environ,
                        'DOTNET_MULTILEVEL_LOOKUP': '0',
                        'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1',
                        'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
                        'DOTNET_ReadyToRun': '1',
                        'DOTNET_TC_QuickJitForLoops': '1'
                    }
                )

                if build_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_csharp_error(build_process.stderr),
                        'metrics': metrics
                    }

                # Cache the successful compilation
                os.makedirs(cache_dir, exist_ok=True)
                shutil.copytree(temp_path / "bin", cache_dir / "bin", dirs_exist_ok=True)

                # Run the program
                run_process = subprocess.run(
                    ['dotnet', 'run', '--project', str(project_file),
                     '--no-build',
                     '--configuration', 'Release'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path)
                )

            if run_process.returncode != 0:
                error_formatter = format_cpp_error if language == 'cpp' else format_csharp_error
                return {
                    'success': False,
                    'error': error_formatter(run_process.stderr),
                    'metrics': metrics
                }

            metrics['total_time'] = time.time() - metrics['start_time']
            return {
                'success': True,
                'output': run_process.stdout,
                'metrics': metrics
            }

    except subprocess.TimeoutExpired:
        phase = "compilation" if time.time() - metrics['start_time'] < MAX_COMPILATION_TIME else "execution"
        return {
            'success': False,
            'error': f"{phase.capitalize()} timed out",
            'metrics': metrics
        }
    except Exception as e:
        logger.error(f"Unexpected error: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'metrics': metrics
        }

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