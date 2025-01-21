import subprocess
import tempfile
import os
import logging
import traceback
import signal
from typing import Dict, Optional, Any
from pathlib import Path
import psutil
import time
import re
import glob
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 10  # Further reduced from 15 to 10 seconds
MAX_EXECUTION_TIME = 5    # Reduced from 10 to 5 seconds
MEMORY_LIMIT = 512        # MB
COMPILER_CACHE_DIR = os.path.expanduser("~/.compiler_cache")  # Persistent cache location
MAX_WORKERS = 4           # Maximum number of parallel compilation workers

def find_dotnet_path():
    """Find .NET SDK path with enhanced path detection"""
    try:
        # Check Nix store with more specific patterns
        possible_paths = []

        # Check for dotnet-sdk
        sdk_paths = glob.glob("/nix/store/*/dotnet-sdk-*/dotnet")
        if sdk_paths:
            possible_paths.extend(sdk_paths)

        # Check for dotnet runtime
        runtime_paths = glob.glob("/nix/store/*/dotnet-runtime-*/dotnet")
        if runtime_paths:
            possible_paths.extend(runtime_paths)

        # Check aspnet paths
        aspnet_paths = glob.glob("/nix/store/*/aspnetcore-runtime-*/dotnet")
        if aspnet_paths:
            possible_paths.extend(aspnet_paths)

        if possible_paths:
            # Sort by version number (assuming newer versions have higher numbers)
            possible_paths.sort(reverse=True)
            dotnet_path = possible_paths[0]
            logger.debug(f"Found dotnet in Nix store: {dotnet_path}")
            return os.path.dirname(dotnet_path)

        # Try common system locations
        system_locations = [
            "/usr/share/dotnet",
            "/usr/local/share/dotnet",
            "/opt/dotnet",
            os.path.expanduser("~/.dotnet")
        ]

        for location in system_locations:
            dotnet_exe = os.path.join(location, "dotnet")
            if os.path.exists(dotnet_exe) and os.access(dotnet_exe, os.X_OK):
                logger.debug(f"Found dotnet in system location: {dotnet_exe}")
                return location

        # Try PATH as last resort
        process = subprocess.run(['which', 'dotnet'], capture_output=True, text=True)
        if process.returncode == 0:
            dotnet_path = process.stdout.strip()
            logger.debug(f"Found dotnet in PATH: {dotnet_path}")
            return os.path.dirname(dotnet_path)

        logger.error("Could not find dotnet installation")
        return None
    except Exception as e:
        logger.error(f"Error finding dotnet path: {e}\n{traceback.format_exc()}")
        return None

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compile and run with enhanced performance and better path handling
    """
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'error': "Code and language are required",
            'metrics': metrics
        }

    try:
        # Set up cache directories
        os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
        os.chmod(COMPILER_CACHE_DIR, 0o755)

        nuget_cache = os.path.join(COMPILER_CACHE_DIR, 'nuget')
        os.makedirs(nuget_cache, exist_ok=True)

        assembly_cache = os.path.join(COMPILER_CACHE_DIR, 'assembly')
        os.makedirs(assembly_cache, exist_ok=True)

        # Find dotnet installation
        dotnet_root = find_dotnet_path()
        if not dotnet_root:
            error_msg = "Could not find .NET SDK installation"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'metrics': metrics
            }

        # Enhanced environment setup
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
            'NUGET_PACKAGES': nuget_cache,
            'DOTNET_ASSEMBLY_CACHE': assembly_cache,
            'DOTNET_USE_POLLING_FILE_WATCHER': '1',
            'DOTNET_ROLL_FORWARD': 'Major',
            'COMPlus_gcServer': '1',
            'COMPlus_GCRetainVM': '1',
            'LC_ALL': 'C',
            'LANG': 'C'
        })

        with tempfile.TemporaryDirectory(prefix='compile_', dir=COMPILER_CACHE_DIR) as temp_dir:
            if language == 'csharp':
                # Set up minimal project structure
                project_dir = Path(temp_dir)
                source_file = project_dir / "Program.cs"
                project_file = project_dir / "program.csproj"
                bin_dir = project_dir / "bin" / "Release" / "net7.0" / "linux-x64"

                # Write source code
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Create optimized project file
                project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
    <PublishSingleFile>false</PublishSingleFile>
    <SelfContained>false</SelfContained>
    <InvariantGlobalization>true</InvariantGlobalization>
    <DebugType>none</DebugType>
    <Optimize>true</Optimize>
    <TieredCompilation>true</TieredCompilation>
    <UseSystemConsole>true</UseSystemConsole>
    <UseAppHost>false</UseAppHost>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <EnableDefaultItems>false</EnableDefaultItems>
    <ServerGarbageCollection>true</ServerGarbageCollection>
    <RetainVMGarbageCollection>true</RetainVMGarbageCollection>
    <ConcurrentGarbageCollection>true</ConcurrentGarbageCollection>
    <WarningLevel>0</WarningLevel>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Program.cs" />
  </ItemGroup>
</Project>"""

                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                # Create bin directory
                os.makedirs(bin_dir, exist_ok=True)

                try:
                    compile_start = time.time()
                    dotnet_cmd = os.path.join(dotnet_root, 'dotnet')

                    # Fast compilation with minimal restore
                    build_cmd = [
                        dotnet_cmd, 'publish',
                        str(project_file),
                        '--configuration', 'Release',
                        '--runtime', 'linux-x64',
                        '--no-self-contained',
                        '--output', str(bin_dir),
                        '-nologo',
                        '-maxcpucount:4',
                        '/p:GenerateFullPaths=true',
                        '/p:UseAppHost=false',
                        '/p:EnableDefaultCompileItems=false',
                        '/p:SkipCompilerExecution=false',
                        '/p:ContinuousIntegrationBuild=true',
                        '/p:GenerateAssemblyInfo=false',
                        '/p:WarningLevel=0',
                        '/p:RestoreDisableParallel=false',
                        '/p:RestoreUseSkipNonexistentTargets=true'
                    ]

                    logger.debug(f"Starting compilation with command: {' '.join(build_cmd)}")

                    compile_process = subprocess.run(
                        build_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_COMPILATION_TIME,
                        cwd=str(project_dir),
                        env=env
                    )

                    metrics['compilation_time'] = time.time() - compile_start

                    if compile_process.returncode != 0:
                        error_msg = format_csharp_error(compile_process.stderr)
                        logger.error(f"Compilation failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': metrics
                        }

                    # Verify output and run
                    dll_path = bin_dir / "program.dll"
                    if not dll_path.exists():
                        error_msg = f"Compilation succeeded but no output found in {bin_dir}"
                        logger.error(error_msg)
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': metrics
                        }

                    # Run with optimized settings
                    run_cmd = [
                        dotnet_cmd,
                        str(dll_path),
                        '--gc-server',
                        '--tiered-compilation'
                    ]

                    logger.debug(f"Running program with command: {' '.join(run_cmd)}")
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        input=input_data.encode() if input_data else None,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        cwd=str(project_dir),
                        env=env
                    )

                    metrics['execution_time'] = time.time() - run_start
                    metrics['total_time'] = time.time() - metrics['start_time']

                    if run_process.returncode != 0:
                        error_msg = format_runtime_error(run_process.stderr)
                        logger.error(f"Execution failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': metrics
                        }

                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'metrics': metrics
                    }

                except subprocess.TimeoutExpired as e:
                    phase = "compilation" if time.time() - compile_start < MAX_COMPILATION_TIME else "execution"
                    error_msg = f"{phase.capitalize()} timed out after {e.timeout} seconds"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'metrics': metrics
                    }

            else:
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}",
                    'metrics': metrics
                }

    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'metrics': metrics
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