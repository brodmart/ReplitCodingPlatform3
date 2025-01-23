import subprocess
import tempfile
import os
from pathlib import Path
import time

def test_simple_csharp_io():
    """Test basic C# console I/O functionality"""
    print("Testing basic C# I/O...")
    
    # Simple C# program that reads a name and prints it
    code = """
    using System;
    
    class Program {
        static void Main() {
            Console.Write("Enter your name: ");
            string name = Console.ReadLine();
            Console.WriteLine($"Hello, {name}!");
        }
    }
    """
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Create project structure
        project_dir = Path(temp_dir)
        source_file = project_dir / "Program.cs"
        project_file = project_dir / "program.csproj"
        
        # Write project file
        with open(project_file, 'w') as f:
            f.write("""<Project Sdk="Microsoft.NET.Sdk">
                <PropertyGroup>
                    <OutputType>Exe</OutputType>
                    <TargetFramework>net7.0</TargetFramework>
                </PropertyGroup>
            </Project>""")
        
        # Write source file
        with open(source_file, 'w') as f:
            f.write(code)
        
        # Compile
        print("Compiling program...")
        compile_result = subprocess.run(
            ['dotnet', 'build', str(project_file), '--nologo'],
            capture_output=True,
            text=True,
            cwd=temp_dir
        )
        
        if compile_result.returncode != 0:
            print("Compilation failed:")
            print(compile_result.stderr)
            return False
        
        # Run the program
        print("Running program...")
        process = subprocess.Popen(
            ['dotnet', 'run', '--project', str(project_file), '--no-build'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=temp_dir
        )
        
        # Wait for prompt
        time.sleep(0.5)
        output = process.stdout.readline()
        print(f"Initial output: {output}")
        
        # Send input
        test_name = "TestUser\n"
        print(f"Sending input: {test_name.strip()}")
        process.stdin.write(test_name)
        process.stdin.flush()
        
        # Get response
        time.sleep(0.5)
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Verify output
        expected = "Hello, TestUser!"
        if expected in response:
            print("Test passed!")
            return True
        else:
            print(f"Test failed! Expected '{expected}' but got '{response}'")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        return False
    finally:
        # Clean up
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=2)
        
        import shutil
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_simple_csharp_io()
