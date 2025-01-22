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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 15  # seconds
MAX_EXECUTION_TIME = 5    # seconds
MEMORY_LIMIT = 512       # MB
MAX_PARALLEL_COMPILATIONS = min(os.cpu_count() or 4, 8)  # Limit max parallel compilations
CACHE_DIR = "/tmp/compiler_cache"
CACHE_SIZE_LIMIT = 1024 * 1024 * 1024  # 1GB cache size limit

# Initialize cache directory and lock
os.makedirs(CACHE_DIR, exist_ok=True)
cache_lock = Lock()

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

def compile_and_run(code: str, language: str = 'csharp', input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compiler with advanced caching and parallel compilation support
    """
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compilation for code length: {len(code)}")

    if not code:
        return {
            'success': False,
            'error': "No code provided",
            'metrics': metrics
        }

    # Check cache first
    cache_key = get_cache_key(code)
    cache_path = Path(CACHE_DIR) / cache_key

    if cache_path.exists():
        logger.debug("Using cached compilation")
        metrics['cached'] = True
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                # Efficiently copy cached files
                shutil.copytree(str(cache_path), str(temp_path), dirs_exist_ok=True)

                # Run the cached program with optimized runtime settings
                env = os.environ.copy()
                env['DOTNET_GCHeapCount'] = str(os.cpu_count())
                env['DOTNET_GCHighMemPercent'] = '90'
                env['DOTNET_GCNoAffinitize'] = '1'
                env['DOTNET_TieredPGO'] = '1'
                env['DOTNET_TC_QuickJitForLoops'] = '1'

                run_process = subprocess.run(
                    ['dotnet', f'{temp_path}/program.dll'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path),
                    env=env
                )

                metrics['compilation_time'] = 0
                metrics['execution_time'] = time.time() - metrics['start_time']
                metrics['total_time'] = metrics['execution_time']

                if run_process.returncode != 0:
                    return {
                        'success': False,
                        'error': format_error(run_process.stderr),
                        'metrics': metrics
                    }

                return {
                    'success': True,
                    'output': run_process.stdout,
                    'metrics': metrics
                }
        except Exception as e:
            logger.warning(f"Cache use failed, falling back to full compilation: {e}")

    # Cleanup old cache entries if needed
    cleanup_old_cache()

    # Create temporary directory for compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_file = temp_path / "Program.cs"

        try:
            # Write source code
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Create optimized project file with enhanced settings
            project_file = temp_path / "program.csproj"
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
    <Configuration>Release</Configuration>
    <ServerGarbageCollection>true</ServerGarbageCollection>
    <ConcurrentGarbageCollection>true</ConcurrentGarbageCollection>
    <RetainVMGarbageCollection>true</RetainVMGarbageCollection>
    <TieredCompilation>true</TieredCompilation>
    <TieredCompilationQuickJit>true</TieredCompilationQuickJit>
    <TieredCompilationQuickJitForLoops>true</TieredCompilationQuickJitForLoops>
  </PropertyGroup>
</Project>"""

            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            # Build with highly optimized settings
            logger.debug("Starting build process")
            env = os.environ.copy()
            env['DOTNET_MULTILEVEL_LOOKUP'] = '0'
            env['DOTNET_SKIP_FIRST_TIME_EXPERIENCE'] = '1'
            env['DOTNET_CLI_TELEMETRY_OPTOUT'] = '1'
            env['DOTNET_ReadyToRun'] = '1'
            env['DOTNET_TC_QuickJitForLoops'] = '1'

            build_process = subprocess.run(
                ['dotnet', 'build', str(project_file),
                 '--configuration', 'Release',
                 '--nologo',
                 '/p:GenerateFullPaths=true',
                 '/consoleloggerparameters:NoSummary',
                 '/p:UseSharedCompilation=true',
                 '/p:DebugType=none',
                 '/p:DebugSymbols=false'],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=str(temp_path),
                env=env
            )

            metrics['compilation_time'] = time.time() - metrics['start_time']

            if build_process.returncode != 0:
                logger.error(f"Build failed: {build_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(build_process.stderr),
                    'metrics': metrics
                }

            # Cache successful compilation
            os.makedirs(cache_path, exist_ok=True)
            shutil.copytree(str(temp_path / "bin" / "Release" / "net7.0"), str(cache_path), dirs_exist_ok=True)

            # Run the program with optimized runtime settings
            logger.debug("Starting program execution")
            env['DOTNET_GCHeapCount'] = str(os.cpu_count())
            env['DOTNET_GCHighMemPercent'] = '90'
            env['DOTNET_GCNoAffinitize'] = '1'

            run_process = subprocess.run(
                ['dotnet', 'run', '--project', str(project_file),
                 '--no-build',
                 '--configuration', 'Release'],
                input=input_data.encode() if input_data else None,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=str(temp_path),
                env=env
            )

            metrics['execution_time'] = time.time() - (metrics['start_time'] + metrics['compilation_time'])
            metrics['total_time'] = time.time() - metrics['start_time']

            if run_process.returncode != 0:
                logger.error(f"Execution failed: {run_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(run_process.stderr),
                    'metrics': metrics
                }

            return {
                'success': True,
                'output': run_process.stdout,
                'metrics': metrics
            }

        except subprocess.TimeoutExpired:
            logger.error("Process timed out")
            return {
                'success': False,
                'error': "Process timed out",
                'metrics': metrics
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'metrics': metrics
            }

def format_error(error_msg: str) -> str:
    """Format error messages to be more user-friendly"""
    if not error_msg:
        return "Unknown error occurred"

    lines = error_msg.splitlines()
    formatted_lines = []

    for line in lines:
        if "error CS" in line:
            parts = line.split(': ', 1)
            if len(parts) > 1:
                formatted_lines.append(f"Compilation Error: {parts[1].strip()}")
        elif "Unhandled exception" in line:
            formatted_lines.append("Runtime Error: Program crashed during execution")

    return "\n".join(formatted_lines) if formatted_lines else error_msg.strip()