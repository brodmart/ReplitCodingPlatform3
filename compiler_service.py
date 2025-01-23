import os
import subprocess
import logging
import pty
import select
import uuid
from threading import Lock
from pathlib import Path

# Basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class InteractiveSession:
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id = session_id
        self.temp_dir = temp_dir
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.output_buffer = []
        self.waiting_for_input = False

        # Initialize PTY
        try:
            self.master_fd, self.slave_fd = pty.openpty()
        except Exception as e:
            logger.error(f"Failed to initialize PTY: {e}")

def get_or_create_session(session_id=None):
    """Get existing session or create new one"""
    session_id = session_id or str(uuid.uuid4())
    temp_dir = f'/tmp/compiler_{session_id}'
    os.makedirs(temp_dir, exist_ok=True)
    return InteractiveSession(session_id, temp_dir)

def start_interactive_session(session, code: str, language: str):
    """Start an interactive C# session"""
    try:
        # Write source code
        source_file = Path(session.temp_dir) / "Program.cs"
        with open(source_file, 'w') as f:
            f.write(code)

        # Create project file
        project_file = Path(session.temp_dir) / "program.csproj"
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <OutputType>Exe</OutputType>
            <TargetFramework>net7.0</TargetFramework>
          </PropertyGroup>
        </Project>"""

        with open(project_file, 'w') as f:
            f.write(project_content)

        # Compile
        compile_result = subprocess.run(
            ['dotnet', 'build', str(project_file), '--nologo'],
            capture_output=True,
            text=True,
            cwd=session.temp_dir
        )

        if compile_result.returncode != 0:
            logger.error(f"Build failed: {compile_result.stderr}")
            return {'success': False, 'error': compile_result.stderr}

        # Run the compiled program
        exe_path = Path(session.temp_dir) / "bin" / "Debug" / "net7.0" / "program"
        session.process = subprocess.Popen(
            [str(exe_path)],
            stdin=session.slave_fd,
            stdout=session.slave_fd,
            stderr=session.slave_fd,
            close_fds=True
        )

        return {
            'success': True,
            'session_id': session.session_id
        }

    except Exception as e:
        logger.error(f"Error in start_interactive_session: {e}")
        return {'success': False, 'error': str(e)}

def get_output(session_id: str):
    """Get output from the session"""
    try:
        session = get_or_create_session(session_id)
        if not session.master_fd:
            return {'success': False, 'error': 'Invalid session'}

        ready, _, _ = select.select([session.master_fd], [], [], 0.1)
        if ready:
            output = os.read(session.master_fd, 1024).decode()
            session.waiting_for_input = 'input' in output.lower() or '?' in output
            return {
                'success': True,
                'output': output,
                'waiting_for_input': session.waiting_for_input
            }
        return {
            'success': True,
            'output': '',
            'waiting_for_input': session.waiting_for_input
        }
    except Exception as e:
        logger.error(f"Error getting output: {e}")
        return {'success': False, 'error': str(e)}

def send_input(session_id: str, input_text: str):
    """Send input to the session"""
    try:
        session = get_or_create_session(session_id)
        if not session.master_fd:
            return {'success': False, 'error': 'Invalid session'}

        if not input_text.endswith('\n'):
            input_text += '\n'
        os.write(session.master_fd, input_text.encode())
        return {'success': True}
    except Exception as e:
        logger.error(f"Error sending input: {e}")
        return {'success': False, 'error': str(e)}

def cleanup_session(session_id: str):
    """Clean up session resources"""
    try:
        session = get_or_create_session(session_id)
        if session.process:
            session.process.terminate()
        if session.master_fd:
            os.close(session.master_fd)
        if session.slave_fd:
            os.close(session.slave_fd)
        if os.path.exists(session.temp_dir):
            os.rmdir(session.temp_dir)
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")