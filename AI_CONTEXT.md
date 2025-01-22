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

## CRITICAL WARNING - Console Implementation
PERSISTENT ISSUE DOCUMENTED: There has been a recurring tendency to implement and test console functionality through command-line interfaces instead of the required web console interface. This is STRICTLY PROHIBITED.

Key Points:
1. ALL console interactions MUST be implemented through the web interface using:
   - CodeMirror for code editing
   - Xterm.js for console output
   - WebSocket/HTTP for real-time I/O
2. Command-line testing (e.g., using unittest) for console functionality is NOT ACCEPTABLE
3. Console implementation must focus on web-based integration
4. Any command-line console testing should be immediately redirected to web console implementation
5. Test cases should be written for web console interaction, not command-line programs

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


## Development Guidelines
1. Focus on performance optimization and minimal resource usage
2. Maintain nimbleness and efficiency as top priorities
3. Avoid heavy frameworks unless absolutely necessary
4. Prefer lightweight, modular solutions
5. Regular testing and performance monitoring

## Systematic Debugging Approach
1. **Frontend-Backend Analysis Pattern**:
   - Always analyze both frontend and backend components
   - Identify where the communication chain breaks
   - Verify each step of the data flow

2. **Structured Bottleneck Analysis**:
   Frontend Verification:
   - Socket.IO connection status
   - Event emission confirmation
   - Event listener setup
   - Console log monitoring
   - UI state updates

   Backend Verification:
   - Socket.IO event reception
   - Handler execution flow
   - Service integration points
   - Data processing steps
   - Response emission

3. **Progressive Debug Logging**:
   - Add detailed logging at each critical point
   - Track data transformation between layers
   - Monitor timing and performance metrics
   - Log both success and failure paths

4. **Common Bottleneck Patterns**:
   - Socket.IO event mismatches
   - Data serialization issues
   - Async/await flow breaks
   - Memory/resource constraints
   - Service integration gaps

5. **Resolution Strategy**:
   - Identify the exact break point
   - Add comprehensive logging
   - Make atomic, focused fixes
   - Verify the entire chain
   - Document the solution pattern


## Database Information
- Database Name: ICS3U Curriculum Database
- Connection: Managed through DATABASE_URL environment variable
- Access: Via SQLAlchemy ORM with Flask-SQLAlchemy integration
- Main Tables:
  * courses: Stores course information
  * strands: Stores curriculum strands
  * overall_expectations: Stores overall expectations
  * specific_expectations: Stores specific expectations

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