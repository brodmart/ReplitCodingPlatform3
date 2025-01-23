import os
import subprocess
import logging
import pty
import select
import uuid
import psutil
import shutil
import time
from threading import Lock
from pathlib import Path
from typing import Dict, Optional, Any

# Enhanced logging setup with formatting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s - %(filename)s:%(lineno)d'
)
logger = logging.getLogger(__name__)

# Constants for resource management
MAX_MEMORY_MB = 512
MAX_COMPILATION_TIME = 30
MAX_EXECUTION_TIME = 10
CLEANUP_INTERVAL = 300  # 5 minutes

# Use project directory with size limit
COMPILER_DIR = os.path.join(os.getcwd(), 'compiler_workspace')
MAX_WORKSPACE_SIZE_MB = 100
os.makedirs(COMPILER_DIR, exist_ok=True)

class ResourceMonitor:
    """Monitor and manage system resources"""
    def __init__(self):
        self.process = psutil.Process()
        self._lock = Lock()
        self._last_cleanup = time.time()

    def check_memory_usage(self) -> bool:
        """Check if memory usage is within limits"""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            logger.debug(f"Current memory usage: {memory_mb:.2f} MB")
            return memory_mb <= MAX_MEMORY_MB
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return False

    def cleanup_if_needed(self):
        """Perform cleanup if interval exceeded or memory high"""
        with self._lock:
            current_time = time.time()
            if (current_time - self._last_cleanup >= CLEANUP_INTERVAL or 
                not self.check_memory_usage()):
                self._perform_cleanup()
                self._last_cleanup = current_time

    def _perform_cleanup(self):
        """Clean up old compilation directories"""
        try:
            total_size = 0
            for item in os.listdir(COMPILER_DIR):
                item_path = os.path.join(COMPILER_DIR, item)
                try:
                    if os.path.isdir(item_path):
                        size = sum(f.stat().st_size for f in Path(item_path).rglob('*'))
                        total_size += size
                        if time.time() - os.path.getmtime(item_path) > CLEANUP_INTERVAL:
                            shutil.rmtree(item_path)
                            logger.info(f"Cleaned up old session directory: {item_path}")
                except Exception as e:
                    logger.error(f"Error processing {item_path}: {e}")

            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)
            logger.info(f"Total workspace size: {total_size_mb:.2f} MB")

            if total_size_mb > MAX_WORKSPACE_SIZE_MB:
                logger.warning("Workspace size exceeded limit, triggering cleanup")
                self._force_cleanup()
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

    def _force_cleanup(self):
        """Force cleanup of old sessions when space limit exceeded"""
        try:
            directories = []
            for item in os.listdir(COMPILER_DIR):
                item_path = os.path.join(COMPILER_DIR, item)
                if os.path.isdir(item_path):
                    directories.append((item_path, os.path.getmtime(item_path)))

            # Sort by modification time (oldest first)
            directories.sort(key=lambda x: x[1])

            # Remove oldest directories until under limit
            for dir_path, _ in directories[:-5]:  # Keep 5 most recent
                try:
                    shutil.rmtree(dir_path)
                    logger.info(f"Force cleaned directory: {dir_path}")
                except Exception as e:
                    logger.error(f"Error removing directory {dir_path}: {e}")
        except Exception as e:
            logger.error(f"Error in force cleanup: {e}")

# Initialize resource monitor
resource_monitor = ResourceMonitor()

class InteractiveSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.temp_dir = os.path.join(COMPILER_DIR, session_id)
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.start_time = time.time()
        self.last_activity = time.time()
        self.waiting_for_input = False

        # Initialize PTY with error handling
        try:
            self.master_fd, self.slave_fd = pty.openpty()
            logger.info(f"[Session {session_id}] PTY initialized successfully")
        except Exception as e:
            logger.error(f"[Session {session_id}] Failed to initialize PTY: {e}")
            raise

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()

    def is_expired(self) -> bool:
        """Check if session has expired"""
        return (time.time() - self.last_activity) > MAX_EXECUTION_TIME

    def cleanup(self):
        """Clean up session resources"""
        try:
            logger.info(f"[Session {self.session_id}] Cleaning up resources")
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception as e:
                    logger.error(f"[Session {self.session_id}] Error terminating process: {e}")
                    try:
                        self.process.kill()
                    except:
                        pass

            for fd in (self.master_fd, self.slave_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception as e:
                        logger.error(f"[Session {self.session_id}] Error closing fd {fd}: {e}")

            if os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"[Session {self.session_id}] Removed temp directory")
                except Exception as e:
                    logger.error(f"[Session {self.session_id}] Error removing temp directory: {e}")
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error in cleanup: {e}")

def start_interactive_session(session: InteractiveSession, code: str, language: str = 'csharp') -> Dict[str, Any]:
    """Start an interactive session with resource monitoring"""
    try:
        logger.info(f"[Session {session.session_id}] Starting interactive session")

        # Check resources before proceeding
        if not resource_monitor.check_memory_usage():
            logger.error(f"[Session {session.session_id}] Memory limit exceeded")
            return {'success': False, 'error': 'System resources unavailable'}

        # Periodic cleanup check
        resource_monitor.cleanup_if_needed()

        # Create and verify temp directory
        os.makedirs(session.temp_dir, exist_ok=True)

        # Write source code with error handling
        source_file = Path(session.temp_dir) / "Program.cs"
        try:
            with open(source_file, 'w') as f:
                f.write(code)
        except Exception as e:
            logger.error(f"[Session {session.session_id}] Failed to write source file: {e}")
            return {'success': False, 'error': 'Failed to prepare code for compilation'}

        # Create optimized project file
        project_file = Path(session.temp_dir) / "program.csproj"
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <OutputType>Exe</OutputType>
            <TargetFramework>net7.0</TargetFramework>
            <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
            <PublishSingleFile>true</PublishSingleFile>
            <SelfContained>false</SelfContained>
            <EnableDefaultItems>false</EnableDefaultItems>
            <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
          </PropertyGroup>
          <ItemGroup>
            <Compile Include="Program.cs" />
          </ItemGroup>
        </Project>"""

        try:
            with open(project_file, 'w') as f:
                f.write(project_content)
        except Exception as e:
            logger.error(f"[Session {session.session_id}] Failed to write project file: {e}")
            return {'success': False, 'error': 'Failed to create project configuration'}

        # Compile with optimized settings and timeout
        logger.info(f"[Session {session.session_id}] Starting compilation")
        try:
            compile_result = subprocess.run(
                ['dotnet', 'build', str(project_file), '--nologo', '-c', 'Release',
                 '/p:GenerateFullPaths=true',
                 '/consoleloggerparameters:NoSummary'],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=session.temp_dir
            )
        except subprocess.TimeoutExpired:
            logger.error(f"[Session {session.session_id}] Compilation timed out")
            return {'success': False, 'error': 'Compilation timed out'}
        except Exception as e:
            logger.error(f"[Session {session.session_id}] Compilation failed: {e}")
            return {'success': False, 'error': str(e)}

        if compile_result.returncode != 0:
            logger.error(f"[Session {session.session_id}] Build failed: {compile_result.stderr}")
            return {'success': False, 'error': compile_result.stderr}

        # Run the compiled program
        exe_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / "linux-x64" / "program"
        if not os.path.exists(exe_path):
            logger.error(f"[Session {session.session_id}] Executable not found at {exe_path}")
            return {'success': False, 'error': 'Compiled executable not found'}

        try:
            session.process = subprocess.Popen(
                [str(exe_path)],
                stdin=session.slave_fd,
                stdout=session.slave_fd,
                stderr=session.slave_fd,
                close_fds=True
            )
            logger.info(f"[Session {session.session_id}] Process started with PID: {session.process.pid}")
            return {'success': True, 'session_id': session.session_id}
        except Exception as e:
            logger.error(f"[Session {session.session_id}] Failed to start process: {e}")
            return {'success': False, 'error': f'Failed to start program: {str(e)}'}

    except Exception as e:
        logger.error(f"[Session {session.session_id}] Unexpected error: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def get_output(session_id: str) -> Dict[str, Any]:
    """Get output from the session with timeout handling"""
    session = InteractiveSession(session_id)
    try:
        if not session.master_fd:
            logger.error(f"[Session {session_id}] Invalid session - no master_fd")
            return {'success': False, 'error': 'Invalid session'}

        if session.is_expired():
            logger.warning(f"[Session {session_id}] Session expired")
            return {'success': False, 'error': 'Session expired'}

        ready, _, _ = select.select([session.master_fd], [], [], 0.1)
        if ready:
            try:
                output = os.read(session.master_fd, 1024).decode()
                session.update_activity()
                session.waiting_for_input = 'input' in output.lower() or '?' in output
                logger.debug(f"[Session {session_id}] Output received: {len(output)} bytes")
                return {
                    'success': True,
                    'output': output,
                    'waiting_for_input': session.waiting_for_input
                }
            except OSError as e:
                logger.error(f"[Session {session_id}] Error reading from PTY: {e}")
                return {'success': False, 'error': f'Error reading output: {e}'}

        return {
            'success': True,
            'output': '',
            'waiting_for_input': session.waiting_for_input
        }

    except Exception as e:
        logger.error(f"[Session {session_id}] Error in get_output: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def send_input(session_id: str, input_text: str) -> Dict[str, Any]:
    """Send input to the session with validation"""
    session = InteractiveSession(session_id)
    try:
        logger.info(f"[Session {session_id}] Sending input: {len(input_text)} bytes")

        if not session.master_fd:
            logger.error(f"[Session {session_id}] Invalid session - no master_fd")
            return {'success': False, 'error': 'Invalid session'}

        if session.is_expired():
            logger.warning(f"[Session {session_id}] Session expired")
            return {'success': False, 'error': 'Session expired'}

        # Validate input
        if len(input_text) > 1024:  # Limit input size
            logger.warning(f"[Session {session_id}] Input too large: {len(input_text)} bytes")
            return {'success': False, 'error': 'Input too large'}

        if not input_text.endswith('\n'):
            input_text += '\n'

        try:
            bytes_written = os.write(session.master_fd, input_text.encode())
            session.update_activity()
            logger.info(f"[Session {session_id}] Successfully wrote {bytes_written} bytes")
            return {'success': True}
        except OSError as e:
            logger.error(f"[Session {session_id}] Error writing to PTY: {e}")
            return {'success': False, 'error': f'Error sending input: {e}'}

    except Exception as e:
        logger.error(f"[Session {session_id}] Error in send_input: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def cleanup_session(session_id: str):
    """Clean up session resources"""
    try:
        logger.info(f"[Session {session_id}] Starting cleanup")
        session = InteractiveSession(session_id)
        session.cleanup()
        logger.info(f"[Session {session_id}] Cleanup completed")
    except Exception as e:
        logger.error(f"[Session {session_id}] Error in cleanup: {e}")

def cleanup_old_sessions():
    """Clean up old compilation directories using ResourceMonitor"""
    resource_monitor.cleanup_if_needed()

def get_or_create_session(session_id=None):
    """Get existing session or create new one, with cleanup"""
    cleanup_old_sessions()

    session_id = session_id or str(uuid.uuid4())
    session_dir = os.path.join(COMPILER_DIR, session_id)

    # Remove existing session directory if it exists
    if os.path.exists(session_dir):
        try:
            shutil.rmtree(session_dir)
        except Exception as e:
            logger.error(f"Error cleaning up existing session directory: {e}")

    os.makedirs(session_dir, exist_ok=True)
    logger.info(f"[Session {session_id}] Created/retrieved session in {session_dir}")
    return InteractiveSession(session_id)