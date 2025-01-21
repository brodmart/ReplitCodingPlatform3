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
MAX_COMPILATION_TIME = 15  # Reduced from 30 to 15 seconds
MAX_EXECUTION_TIME = 10    # Reduced from 15 to 10 seconds
MEMORY_LIMIT = 512        # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"
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

        # If nothing found, log detailed debug information
        logger.error("Could not find dotnet installation. Debug info:")
        logger.error(f"PATH: {os.environ.get('PATH', 'Not set')}")
        logger.error(f"Searched Nix paths: {len(possible_paths)} found")
        logger.error("Searched system locations: " + ", ".join(system_locations))
        return None
    except Exception as e:
        logger.error(f"Error finding dotnet path: {e}\n{traceback.format_exc()}")
        return None

class CompilationTimeout(Exception):
    """Raised when compilation exceeds time limit"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compile and run with enhanced performance and better path handling
    """
    start_time = time.time()
    metrics = {'start_time': start_time}
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'error': "Code and language are required",
            'metrics': metrics
        }

    try:
        # Ensure cache directory exists with proper permissions
        os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)
        os.chmod(COMPILER_CACHE_DIR, 0o755)

        # Find dotnet installation with enhanced path detection
        dotnet_root = find_dotnet_path()
        if not dotnet_root:
            error_msg = "Could not find .NET SDK installation. Please ensure .NET SDK is properly installed."
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'metrics': metrics
            }

        # Set up enhanced environment variables
        enhanced_env = os.environ.copy()  # Start with current environment
        enhanced_env.update({
            'DOTNET_ROOT': dotnet_root,
            'PATH': f"{dotnet_root}:{enhanced_env.get('PATH', '')}",
            'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
            'DOTNET_SKIP_FIRST_TIME_EXPERIENCE': '1',
            'DOTNET_NOLOGO': '1',
            'DOTNET_MULTILEVEL_LOOKUP': '0',
            'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT': '1',
            'LC_ALL': 'C',
            'LANG': 'C',
        })

        # Log environment setup for debugging
        logger.debug(f"Using DOTNET_ROOT: {dotnet_root}")
        logger.debug(f"Updated PATH: {enhanced_env['PATH']}")

        with tempfile.TemporaryDirectory(prefix="compile_", dir=COMPILER_CACHE_DIR) as temp_dir:
            if language == 'csharp':
                # Set up project structure
                project_dir = Path(temp_dir)
                source_file = project_dir / "Program.cs"
                project_file = project_dir / "program.csproj"
                bin_dir = project_dir / "bin" / "Release" / "net7.0" / "linux-x64"

                # Write source code
                logger.debug(f"Writing source code to {source_file}")
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
  </PropertyGroup>
</Project>"""

                logger.debug(f"Writing project file to {project_file}")
                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                # Create bin directory
                os.makedirs(bin_dir, exist_ok=True)

                try:
                    # Fast restore with minimal dependencies
                    logger.debug("Restoring NuGet packages...")
                    dotnet_cmd = os.path.join(dotnet_root, 'dotnet')
                    restore_cmd = [dotnet_cmd, 'restore', str(project_file), '--runtime', 'linux-x64']
                    restore_process = subprocess.run(
                        restore_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=str(project_dir),
                        env=enhanced_env
                    )

                    if restore_process.returncode != 0:
                        error_msg = restore_process.stderr or "Package restore failed with no error message"
                        logger.error(f"Package restore failed: {error_msg}")
                        return {
                            'success': False,
                            'error': f"Package restore failed: {error_msg}",
                            'metrics': metrics
                        }

                    # Optimized build command
                    compile_cmd = [
                        dotnet_cmd, 'publish',
                        str(project_file),
                        '--configuration', 'Release',
                        '--runtime', 'linux-x64',
                        '--no-self-contained',
                        '--output', str(bin_dir),
                        '-nologo',
                        '-maxcpucount:4',
                        '/p:GenerateFullPaths=true',
                        '/p:UseAppHost=false'
                    ]

                    logger.debug(f"Starting compilation with command: {' '.join(compile_cmd)}")
                    compile_start = time.time()

                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_COMPILATION_TIME,
                        cwd=str(project_dir),
                        env=enhanced_env
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

                    # Run the compiled program
                    run_cmd = [dotnet_cmd, str(dll_path)]
                    logger.debug(f"Running program with command: {' '.join(run_cmd)}")
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        input=input_data.encode() if input_data else None,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        cwd=str(project_dir),
                        env=enhanced_env
                    )

                    metrics['execution_time'] = time.time() - run_start
                    metrics['total_time'] = time.time() - start_time

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
                    error_msg = f"{phase.capitalize()} timed out after {e.timeout:.2f} seconds"
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
            return "Compilation Error: No error message provided by the compiler"

        if "error CS" in error_msg:
            # Extract the error code and message
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
            return "Runtime Error: No error message provided by the runtime"

        common_errors = {
            "System.NullReferenceException": "Attempted to use a null object",
            "System.IndexOutOfRangeException": "Array index out of bounds",
            "System.DivideByZeroException": "Division by zero detected",
            "System.InvalidOperationException": "Invalid operation",
            "System.ArgumentException": "Invalid argument provided",
            "System.FormatException": "Invalid format"
        }

        for error_type, message in common_errors.items():
            if error_type in error_msg:
                return f"Runtime Error: {message}"
        return f"Runtime Error: {error_msg}"
    except Exception:
        return f"Runtime Error: {error_msg}"

def find_icu_path():
    """Find ICU library path in Nix store"""
    try:
        # Look for ICU library directory in Nix store
        possible_paths = glob.glob("/nix/store/*/lib/icu*")
        if possible_paths:
            icu_dir = os.path.dirname(possible_paths[0])
            logger.debug(f"Found ICU library path: {icu_dir}")
            return icu_dir
        logger.info("No ICU path found, using invariant globalization")
        return None
    except Exception as e:
        logger.error(f"Error finding ICU path: {e}")
        return None