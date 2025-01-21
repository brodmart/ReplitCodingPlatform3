import subprocess
import tempfile
import os
import logging
import traceback
import signal
from typing import Dict, Optional, Any, List
from pathlib import Path
import psutil
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import glob
import re
from threading import Lock, Thread, Event
import hashlib
import json
from dataclasses import dataclass, asdict, field
from optimization_analyzer import ResourceMonitor, PerformanceOptimizer

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
MAX_COMPILATION_TIME = 30  # Increased from 10 to 30 seconds
MAX_EXECUTION_TIME = 10    # seconds
MEMORY_LIMIT = 512       # MB
COMPILER_CACHE_DIR = os.path.expanduser("~/.compiler_cache")
MAX_WORKERS = os.cpu_count() or 4
MAX_RETRIES = 2
CACHE_VERSION = "1.0"     # Increment when cache format changes

# Added constants for performance optimizations
COMPILER_WARMUP_ENABLED = True
WARMUP_CACHE_SIZE = 50  # Maximum number of cached compilations
THREAD_POOL_SIZES = {
    'high': lambda cpu_count: max(2, cpu_count // 2),
    'medium': lambda cpu_count: max(2, cpu_count - 1),
    'normal': lambda cpu_count: cpu_count
}

# Create cache directories
os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
NUGET_CACHE = os.path.join(COMPILER_CACHE_DIR, 'nuget')
ASSEMBLY_CACHE = os.path.join(COMPILER_CACHE_DIR, 'assembly')
RESPONSE_FILE_CACHE = os.path.join(COMPILER_CACHE_DIR, 'response')
BUILD_CACHE = os.path.join(COMPILER_CACHE_DIR, 'build')
for cache_dir in [NUGET_CACHE, ASSEMBLY_CACHE, RESPONSE_FILE_CACHE, BUILD_CACHE]:
    os.makedirs(cache_dir, exist_ok=True)

# Cache locks
cache_lock = Lock()
build_lock = Lock()
_compiler_warmed_up = False

def calculate_code_hash(code: str) -> str:
    """Calculate a hash of the code for caching"""
    return hashlib.sha256(code.encode()).hexdigest()

def get_cached_build(code_hash: str) -> Optional[str]:
    """Try to get cached build output"""
    cache_path = os.path.join(BUILD_CACHE, f"{code_hash}.dll")
    config_path = os.path.join(BUILD_CACHE, f"{code_hash}.runtimeconfig.json")

    if os.path.exists(cache_path) and os.path.exists(config_path):
        return cache_path
    return None

def save_to_build_cache(code_hash: str, dll_path: Path) -> None:
    """Save successful build to cache with runtime config"""
    with build_lock:
        cache_path = os.path.join(BUILD_CACHE, f"{code_hash}.dll")
        config_path = os.path.join(BUILD_CACHE, f"{code_hash}.runtimeconfig.json")
        try:
            # Copy the compiled DLL
            shutil.copy2(dll_path, cache_path)

            # Create and save runtime config
            runtime_config = {
                "runtimeOptions": {
                    "tfm": "net7.0",
                    "framework": {
                        "name": "Microsoft.NETCore.App",
                        "version": "7.0.0"
                    }
                }
            }

            with open(config_path, 'w') as f:
                json.dump(runtime_config, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to cache build: {e}")

@dataclass
class CompilationMetrics:
    """Track compilation and execution metrics with dictionary-style access"""
    start_time: float = field(default_factory=time.time)
    compilation_time: float = 0.0
    execution_time: float = 0.0
    peak_memory: float = 0.0
    status_updates: List[tuple] = field(default_factory=list)
    cached: bool = False
    total_time: float = 0.0

    def __getitem__(self, key: str) -> Any:
        """Enable dictionary-style access to metrics"""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Enable dictionary-style setting of metrics"""
        setattr(self, key, value)

    def log_status(self, status: str) -> None:
        """Log a status update with timestamp"""
        current_time = time.time() - self.start_time
        self.status_updates.append((current_time, status))
        logger.debug(f"[{current_time:.2f}s] {status}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format"""
        return asdict(self)

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

class CompilerResourceManager:
    """Manages compiler resources and thread allocation dynamically"""
    def __init__(self):
        self.resource_monitor = ResourceMonitor()
        self.performance_optimizer = PerformanceOptimizer()
        self._thread_pool = None
        self._pool_lock = Lock()

    def get_thread_pool(self) -> ThreadPoolExecutor:
        """Get or create thread pool with optimal size based on current load"""
        with self._pool_lock:
            if not self._thread_pool or self._thread_pool._shutdown:
                cpu_count = os.cpu_count() or 4
                load_level = self.resource_monitor.get_load_level()
                optimal_size = THREAD_POOL_SIZES[load_level](cpu_count)
                self._thread_pool = ThreadPoolExecutor(max_workers=optimal_size)
            return self._thread_pool
    
    def get_recommended_thread_count(self) -> int:
        """Get recommended thread count based on system load"""
        cpu_count = os.cpu_count() or 4
        load_level = self.resource_monitor.get_load_level()
        return THREAD_POOL_SIZES[load_level](cpu_count)

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        return self.resource_monitor.get_current_usage()

    def should_throttle(self) -> bool:
        """Check if compilation requests should be throttled"""
        metrics = self.resource_monitor.get_current_usage()
        return metrics['memory_percent'] > 85 or metrics['cpu_percent'] > 90

# Create global resource manager
compiler_resources = CompilerResourceManager()

def run_parallel_compilation(files_to_compile: List[str], cwd: str, env: dict, timeout: int, retry_count: int = 0) -> List[subprocess.CompletedProcess]:
    """Run compilation in parallel for multiple files using process pool with retry mechanism and resource awareness"""
    def compile_worker(cmd: list) -> subprocess.CompletedProcess:
        try:
            if compiler_resources.should_throttle():
                logger.warning("System under high load, applying throttling")
                time.sleep(1)  # Add delay before processing

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                env=env,
                preexec_fn=os.setsid
            )

            monitor = ProcessMonitor(process, timeout=timeout)
            monitor.start()

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.poll()
                if returncode is None:
                    process.terminate()
                    process.wait(timeout=1)
                    raise subprocess.TimeoutExpired(cmd, timeout)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=1)
                raise
            finally:
                monitor.stop()
                monitor.join(timeout=1)

            return subprocess.CompletedProcess(
                cmd, process.returncode, stdout, stderr
            )
        except Exception as e:
            logger.error(f"Compilation worker error: {e}")
            raise

    try:
        with ThreadPoolExecutor(max_workers=compiler_resources.get_recommended_thread_count()) as executor:
            futures = []
            for file_path in files_to_compile:
                cmd = [
                    'dotnet', 'build',
                    file_path,
                    '--configuration', 'Release',
                    '--runtime', 'linux-x64',
                    '--no-self-contained',
                    '/p:GenerateFullPaths=true',
                    '/p:UseAppHost=false',
                    '/p:EnableDefaultCompileItems=false'
                ]
                futures.append(executor.submit(compile_worker, cmd))

            results = []
            for future in futures:
                try:
                    results.append(future.result(timeout=timeout))
                except TimeoutError:
                    if retry_count < MAX_RETRIES:
                        logger.warning(f"Compilation timeout, retrying ({retry_count + 1}/{MAX_RETRIES})")
                        time.sleep(1)
                        return run_parallel_compilation(files_to_compile, cwd, env, timeout, retry_count + 1)
                    raise subprocess.TimeoutExpired(files_to_compile[0], timeout)
            return results
    except Exception as e:
        logger.error(f"Parallel compilation failed: {e}")
        raise

def create_response_file(file_path: str, options: list) -> None:
    """Create a compiler response file with cached options"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(options))

def get_cached_response_file(options: list) -> str:
    """Get or create cached response file for compiler options"""
    options_hash = hashlib.sha256(str(sorted(options)).encode()).hexdigest()
    cache_path = os.path.join(RESPONSE_FILE_CACHE, f"response_{options_hash}.rsp")

    with cache_lock:
        if not os.path.exists(cache_path):
            create_response_file(cache_path, options)
    return cache_path

def find_dotnet_path():
    """Find .NET SDK path with optimized search"""
    try:
        # Check Nix store first (most common in Replit)
        possible_paths = glob.glob("/nix/store/*/dotnet-sdk-*/dotnet")
        if possible_paths:
            dotnet_path = possible_paths[0]
            return os.path.dirname(dotnet_path)

        # Check system paths
        system_paths = ["/usr/share/dotnet", "/usr/local/share/dotnet", "/opt/dotnet"]
        for path in system_paths:
            if os.path.exists(os.path.join(path, "dotnet")):
                return path

        # Try PATH as last resort
        process = subprocess.run(['which', 'dotnet'], capture_output=True, text=True)
        if process.returncode == 0:
            return os.path.dirname(process.stdout.strip())

        return None
    except Exception as e:
        logger.error(f"Error finding dotnet path: {e}")
        return None

def preallocate_compilation_buffers():
    """Pre-allocate buffers for compilation to reduce memory fragmentation"""
    try:
        # Pre-allocate common buffer sizes
        buffer_sizes = [4096, 8192, 16384, 32768]
        buffers = []
        for size in buffer_sizes:
            buffers.append(bytearray(size))
        return buffers
    except Exception as e:
        logger.warning(f"Failed to preallocate buffers: {e}")
        return []

def warmup_compiler():
    """Warm up the compiler with common code patterns for better performance"""
    global _compiler_warmed_up
    if not COMPILER_WARMUP_ENABLED or _compiler_warmed_up:
        return

    try:
        logger.debug("Starting compiler warmup sequence...")
        warmup_code = """
using System;
class Program {
    static void Main() {
        Console.WriteLine("Hello World");
    }
}"""

        # Create a temporary file for warmup
        with tempfile.NamedTemporaryFile(suffix='.cs', mode='w', delete=False) as f:
            f.write(warmup_code)
            warmup_file = f.name

        try:
            # Simple compilation without recursion
            dotnet_cmd = 'dotnet'
            if dotnet_path := find_dotnet_path():
                dotnet_cmd = os.path.join(dotnet_path, 'dotnet')

            process = subprocess.run(
                [dotnet_cmd, 'build', warmup_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )

            if process.returncode == 0:
                logger.debug("Compiler warmup successful")
            else:
                logger.warning(f"Compiler warmup completed with warnings: {process.stderr}")
        finally:
            try:
                os.unlink(warmup_file)
            except Exception as e:
                logger.warning(f"Failed to cleanup warmup file: {e}")

        _compiler_warmed_up = True
        logger.debug("Compiler warmup complete")
    except Exception as e:
        logger.warning(f"Compiler warmup failed: {e}")
        _compiler_warmed_up = True  # Prevent retries even on failure

def get_optimized_environment() -> Dict[str, str]:
    """Get optimized environment variables for the compiler"""
    dotnet_root = find_dotnet_path()
    if not dotnet_root:
        return os.environ.copy()

    env = os.environ.copy()
    env.update({
        'DOTNET_ROOT': dotnet_root,
        'PATH': f"{dotnet_root}:{env.get('PATH', '')}",
        'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
        'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1',
        'DOTNET_NOLOGO': '1',
        'DOTNET_MULTILEVEL_LOOKUP': '0',
        'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT': '1',
        'DOTNET_CLI_HOME': COMPILER_CACHE_DIR,
        'NUGET_PACKAGES': NUGET_CACHE,
        'DOTNET_ASSEMBLY_CACHE': ASSEMBLY_CACHE,
        'DOTNET_USE_POLLING_FILE_WATCHER': '1',
        'DOTNET_ROLL_FORWARD': 'Major',
        'COMPlus_gcServer': '1',
        'COMPlus_GCRetainVM': '1',
        'COMPlus_Thread_UseAllCpuGroups': '1',
        'COMPlus_gcConcurrent': '1',
        'COMPlus_GCLatencyLevel': '1',
        'COMPlus_GCCpuGroup': '1',
        'COMPlus_ThreadPool_ForceMinWorkerThreads': str(MAX_WORKERS),
        'COMPlus_JitMinOpts': '1',
        'COMPlus_TieredCompilation': '1',
        'COMPlus_TC_QuickJit': '1',
        'DOTNET_SYSTEM_GLOBALIZATION_PREDEFINED_CULTURES_ONLY': 'true'
    })
    return env

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compile and run with caching and proper process management
    """
    metrics = CompilationMetrics()
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        return {
            'success': False,
            'error': "Code and language are required",
            'metrics': metrics.to_dict()
        }

    # Calculate code hash for caching
    code_hash = calculate_code_hash(code)

    # Check cache first
    if cached_dll := get_cached_build(code_hash):
        metrics.cached = True
        return run_cached_build(cached_dll, input_data, metrics)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            source_file = project_dir / "Program.cs"
            project_file = project_dir / "program.csproj"

            # Write source code
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Create optimized project file
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>false</SelfContained>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Program.cs" />
  </ItemGroup>
</Project>"""

            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            try:
                # Build with optimized settings
                logger.debug("Starting compilation")
                env = get_optimized_environment()
                build_process = subprocess.run(
                    [
                        'dotnet', 'build',
                        str(project_file),
                        '--configuration', 'Release',
                        '--nologo',
                        '/p:GenerateFullPaths=true',
                        '/consoleloggerparameters:NoSummary'
                    ],
                    capture_output=True,
                    text=True,
                    timeout=MAX_COMPILATION_TIME,
                    cwd=str(project_dir),
                    env=env
                )

                if build_process.returncode != 0:
                    logger.error(f"Build failed: {build_process.stderr}")
                    return {
                        'success': False,
                        'error': format_csharp_error(build_process.stderr),
                        'metrics': metrics.to_dict()
                    }

                # Save successful build to cache
                dll_path = project_dir / "bin" / "Release" / "net7.0" / "program.dll"
                save_to_build_cache(code_hash, dll_path)

                # Run the compiled program
                logger.debug("Starting program execution")
                run_process = subprocess.Popen(
                    ['dotnet', str(dll_path)],
                    stdin=subprocess.PIPE if input_data else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(project_dir),
                    env=env
                )

                try:
                    stdout, stderr = run_process.communicate(
                        input=input_data,
                        timeout=MAX_EXECUTION_TIME
                    )

                    if run_process.returncode != 0:
                        logger.error(f"Execution failed: {stderr}")
                        return {
                            'success': False,
                            'error': format_runtime_error(stderr),
                            'metrics': metrics.to_dict()
                        }

                    return {
                        'success': True,
                        'output': stdout,
                        'metrics': metrics.to_dict()
                    }

                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(run_process.pid), signal.SIGTERM)
                    run_process.wait(timeout=1)
                    logger.error("Execution timed out")
                    return {
                        'success': False,
                        'error': "Execution timed out",
                        'metrics': metrics.to_dict()
                    }

            except subprocess.TimeoutExpired:
                logger.error("Compilation timed out")
                return {
                    'success': False,
                    'error': "Compilation timed out",
                    'metrics': metrics.to_dict()
                }

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'metrics': metrics.to_dict()
        }

def run_cached_build(dll_path: str, input_data: Optional[str], metrics: CompilationMetrics) -> Dict[str, Any]:
    """Run a cached build output"""
    try:
        dotnet_root = find_dotnet_path()
        if not dotnet_root:
            return {
                'success': False,
                'error': "Could not find .NET SDK installation",
                'metrics': metrics.to_dict()
            }

        # Ensure runtime config exists
        runtime_config = dll_path.replace('.dll', '.runtimeconfig.json')
        if not os.path.exists(runtime_config):
            return {
                'success': False,
                'error': "Missing runtime configuration",
                'metrics': metrics.to_dict()
            }

        run_cmd = [
            os.path.join(dotnet_root, 'dotnet'),
            '--roll-forward', 'Major',
            dll_path,
            '--gc-server',
            '--tiered-compilation'
        ]

        env = get_optimized_environment()
        run_start = time.time()
        metrics.log_status("Execution started (cached)")

        run_process = subprocess.run(
            run_cmd,
            input=input_data.encode() if input_data else None,
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            env=env
        )

        metrics.execution_time = time.time() - run_start
        metrics.log_status("Execution finished (cached)")
        metrics['total_time'] = time.time() - metrics.start_time

        if run_process.returncode != 0:
            return {
                'success': False,
                'error': format_runtime_error(run_process.stderr),
                'metrics': metrics.to_dict()
            }

        return {
            'success': True,
            'output': run_process.stdout,
            'metrics': metrics.to_dict()
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f"Execution timed out after {MAX_EXECUTION_TIME} seconds",
            'metrics': metrics.to_dict()
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Error running cached build: {str(e)}",
            'metrics': metrics.to_dict()
        }

def format_csharp_error(error_msg: str) -> str:
    """Format C# compilation errors to be more user-friendly"""
    try:
        if not error_msg:
            return "Compilation Error: No error message provided"

        if "error CS" in error_msg:
            match = re.search(r'error CS\d+:(.+?)(?:\r|\n|$)', error_msg)
            if match:
                return f"Compilation Error: {match.group(1).strip()}"
        return f"Compilation Error: {error_msg.strip()}"
    except Exception as e:
        logger.error(f"Error formatting C# error message: {str(e)}")
        return f"Compilation Error: {error_msg}"

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors to be more user-friendly"""
    try:
        if not error_msg:
            return "Runtime Error: No error message provided"

        common_errors = {
            "System.NullReferenceException": "Attempted to use a null object",
            "System.IndexOutOfRangeException": "Array index out of bounds",
            "System.DivideByZeroException": "Division by zero detected",
            "System.InvalidOperationException": "Invalid operation",
            "System.ArgumentException": "Invalid argument provided",
            "System.FormatException": "Invalid format",
            "System.StackOverflowException": "Stack overflow - check for infinite recursion",
            "System.OutOfMemoryException": "Out of memory - program is using too much memory",
            "System.IO.IOException": "Input/Output operation failed",
            "System.Security.SecurityException": "Security violation"
        }

        for error_type, message in common_errors.items():
            if error_type in error_msg:
                return f"Runtime Error: {message}"
        return f"Runtime Error: {error_msg.strip()}"
    except Exception:
        return f"Runtime Error: {error_msg}"

import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

def compile_and_run_parallel(files: List[str], language: str) -> List[Dict[str, Any]]:
    """
    Compile and run multiple files in parallel
    """
    logger.info(f"Starting parallel compilation for {len(files)} {language} files")
    start_time = time.time()

    if language != 'csharp':
        return [{'success': False, 'error': f'Language {language} not supported for parallel compilation'}]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Read file contents
        file_contents = {}
        for file_path in files:
            logger.debug(f"Reading file: {file_path}")
            with open(file_path, 'r') as f:
                file_contents[file_path] = f.read()
        # Submit compilation tasks
        futures = []
        for file_path in files:
            logger.debug(f"Submitting compilation task for: {file_path}")
            futures.append(
                executor.submit(
                    compile_and_run,
                    code=file_contents[file_path],
                    language=language,
                    
                )
            )

        # Collect results
        results = []
        for i, future in enumerate(futures):
            try:
                logger.debug(f"Waiting for result of file {i+1}/{len(futures)}")
                result = future.result(timeout=MAX_COMPILATION_TIME * 2)  # Double timeout for safety
                results.append(result)
                if result['success']:
                    logger.info(f"File {i+1} compiled successfully in {result['metrics']['compilation_time']:.2f}s")
                else:
                    logger.error(f"File {i+1} failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                error_msg = f'Parallel compilation failed: {str(e)}'
                logger.error(error_msg)
                results.append({
                    'success': False,
                    'error': error_msg,
                    'metrics': {'compilation_time': 0, 'execution_time': 0}
                })

        total_time = time.time() - start_time
        logger.info(f"Parallel compilation completed in {total_time:.2f}s")
        return results