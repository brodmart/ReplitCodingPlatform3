# AI Session Context Guide
Last Updated: January 22, 2025

## Project Overview
Ontario Secondary Computer Science Curriculum Educational Platform
- Curriculum-aligned coding exercises with intelligent compiler services
- Multi-language support focusing on curriculum requirements
- Advanced interactive learning environment for programming education

## Tech Stack
- Python/Flask backend
- PostgreSQL database 
- Flask-Login authentication
- Pytest for testing
- Mono and .NET SDK integration
- CodeMirror for code editing
- Multi-language compiler service
- Xterm.js for interactive console

## Current Focus
Optimizing C# compilation performance by implementing caching and reducing build overhead
- Issue: Slow compilation time in C# main editor console
- Priority: Improve compiler performance and debugging C# compilation issues
- Target: Faster compilation and execution times

Critical: All code compilation and I/O interactions MUST happen within the web interface:
- CodeMirror editor integration is mandatory for code input
- Console I/O must be handled through the web console implementation
- No command-line or external IDE compilation is allowed
- All student interactions must occur through the web interface
- Compiler service must integrate directly with the web console

## Core Educational Requirements:
1. **Multi-Level Curriculum Support**:
   - Support for multiple Ontario curriculum levels:
     * ICS4U (Grade 12 University)
     * ICS3U (Grade 11 University)
     * ICS2O (Grade 10 Open)
     * TEJ2O (Grade 10 Computer Technology)
   - Adaptive difficulty scaling per student's course level
   - Individual student progress tracking
   - Course-specific assessment criteria
   - Dynamic content presentation based on course level

2. **Language Support Requirements**:
   - Primary Languages:
     * C++: Scalable from TEJ2O basics to ICS4U advanced features
     * C#: Progressive from ICS2O fundamentals to ICS4U advanced concepts
   - Secondary Languages:
     * Python: Adaptable complexity based on course level
   - Future Consideration:
     * JavaScript: Progressive complexity support
   - Language features adapt to course level:
     * Basic concepts for ICS2O/TEJ2O
     * Intermediate structures for ICS3U
     * Advanced implementations for ICS4U

3. **Assessment and Learning Analytics**:
   - Course-specific difficulty scaling
   - Adaptive problem complexity per curriculum level
   - Performance analytics tailored to course requirements
   - Individual learning paths based on course curriculum
   - Cross-course progression tracking

## Console Application Compatibility Requirements
1. **Code Preservation Policy**:
   - Student code must NEVER be modified to fit the environment
   - Console applications must run as-is, exactly as they would in standard IDEs
   - Environment must adapt to support all valid code submissions
   - No suggestions to modify working code that runs in standard IDEs

2. **Console I/O Support**:
   - Full support for all C# console operations:
     * Console.Write and Console.WriteLine
     * Console.Read and Console.ReadLine
     * Console.Clear
     * Console.SetCursorPosition
     * Console.ForegroundColor and Console.BackgroundColor
     * All standard console color and formatting options
   - Interactive input handling must match standard IDE behavior
   - Support for complex console-based user interfaces
   - Proper handling of special characters and encoding

3. **Large Application Support**:
   - Support for reasonable-sized console applications (up to 10MB source code)
   - Support for extensive console-based applications within standard IDE limits
   - Full support for class hierarchies and complex data structures
   - Environment must scale to handle most student applications efficiently
   - Optimized performance for typical code bases
   - Support for multiple source files and projects

4. **IDE Compatibility**:
   - Behavior must match standard C# IDEs (Visual Studio, VS Code)
   - Consistent console behavior across all supported operations
   - Proper handling of threading and synchronization
   - Support for standard debugging output
   - Identical runtime behavior to desktop IDEs
   - Support for all valid C# console features


## Database Information
- Database Name: ICS3U Curriculum Database
- Connection: Managed through DATABASE_URL environment variable
- Access: Via SQLAlchemy ORM with Flask-SQLAlchemy integration
- Main Tables:
  * courses: Stores course information
  * strands: Stores curriculum strands
  * overall_expectations: Stores overall expectations
  * specific_expectations: Stores specific expectations

## Development Guidelines
1. Focus on performance optimization and minimal resource usage
2. Maintain nimbleness and efficiency as top priorities
3. Avoid heavy frameworks unless absolutely necessary
4. Prefer lightweight, modular solutions
5. Regular testing and performance monitoring

## Current Objective
Optimize C# compiler service for faster compilation and execution:
1. Implement caching to reduce redundant compilations
2. Optimize project file generation and build process
3. Implement incremental compilation
4. Optimize memory usage during compilation

## Key Performance Optimizations
### Compiler Service Improvements (January 22, 2025)
1. **Compilation Performance**
   - Reduced compilation time from 7.21s to 0.12s (60x improvement)
   - Implemented smart caching with proper cache invalidation
   - Added parallel compilation support for large projects
   - Enhanced memory management and resource utilization

2. **Resource Management**
   - Optimized build process for minimal memory impact
   - Implemented efficient cleanup of temporary files
   - Added comprehensive performance metrics tracking
   - Enhanced error handling and logging

3. **Caching Strategy**
   - Implemented hash-based cache invalidation
   - Added warm-up phase for frequently used code patterns
   - Optimized cache storage and retrieval
   - Reduced redundant compilations through smart dependency tracking

4. **Future Improvements**
   - Further memory usage optimization
   - Implementation of smarter caching strategies
   - Enhanced parallel processing capabilities
   - Additional performance monitoring metrics

This guide helps maintain consistent project understanding across AI sessions. Always read these files at the start of each session and update them when making significant changes.