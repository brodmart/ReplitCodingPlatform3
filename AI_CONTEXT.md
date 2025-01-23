# AI Session Context Guide
Last Updated: January 23, 2025

## CRITICAL WARNING - CONTENT PRESERVATION
IMPORTANT: No information in this file should be removed or significantly altered WITHOUT EXPLICIT USER CONFIRMATION. This file serves as the primary context for the project and all information is considered critical for maintaining project continuity and understanding.

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
- Comprehensive logging system

## Current Focus
Optimizing C# compilation performance by implementing caching and reducing build overhead
- Issue: Slow compilation time in C# main editor console
- Priority: Improve compiler performance and debugging C# compilation issues
- Target: Faster compilation and execution times

## CRITICAL: Web Console Implementation
As of January 23, 2025, the web console implementation has been identified as the MAKE-OR-BREAK feature for this project:

1. **Core Implementation Requirements**:
   - A fully web-based interactive console that supports all required C# console operations
   - Implementation using CodeMirror editor and Xterm.js terminal for I/O operations
   - Proper Socket.IO integration for real-time I/O handling
   - This is a core feature that cannot be compromised or removed
   - Must handle basic I/O operations flawlessly
   - Real-time interaction between student code and web interface

2. **Technical Integration Requirements**:
   - Proper initialization and error handling
   - Reliable Socket.IO connection management
   - Console initialization issues need immediate resolution
   - Socket.IO connection stability must be improved
   - Element initialization timing needs optimization
   - Real-time I/O handling requires refinement

3. **Success Metrics**:
   - Successful execution of basic I/O operations
   - Reliable console initialization
   - Consistent user interaction experience
   - Zero console element initialization errors

4. **Development Timeline Impact**:
   - Estimated 100+ chat sessions for full implementation
   - 3+ days of dedicated development time
   - Multiple iterations for testing and refinement
   - Critical path for project continuation

5. **Implementation Constraints**:
   - All code compilation and I/O interactions MUST happen within the web interface
   - CodeMirror editor integration is mandatory for code input
   - Console I/O must be handled through the web console implementation
   - No command-line or external IDE compilation is allowed
   - All student interactions must occur through the web interface
   - Compiler service must integrate directly with the web console


## Development Guidelines
1. CRITICAL: Keep all implementations simple and barebones
   - Avoid unnecessary complexity
   - Implement only what's needed
   - Keep code straightforward and easily maintainable
   - Minimize dependencies and external libraries
   - Keep code straightforward and easily maintainable
2. Focus on performance optimization and minimal resource usage
3. Maintain nimbleness and efficiency as top priorities
4. Avoid heavy frameworks unless absolutely necessary
5. Prefer lightweight, modular solutions
6. Regular testing and performance monitoring
7. PROACTIVE ERROR HANDLING: When encountering obvious errors or issues that can be fixed independently, proceed with the fix without waiting for user confirmation
   - This includes syntax errors, basic configuration issues, and standard implementation problems
   - Document the changes made in the response
   - Continue with the implementation flow

## CRITICAL: Essential Logging Guidelines
1. **Immediate Logging Implementation**:
   - Add comprehensive logging AS SOON as any integration work begins
   - Never wait for issues to add logging - implement it proactively
   - Logging is not optional, it's a critical development requirement

2. **Required Logging Points**:
   - All service entry and exit points
   - State changes in critical components
   - All asynchronous operations and their completion
   - All API/Socket events (send and receive)
   - Error conditions with full context
   - Performance-critical operations with timing

3. **Logging Structure**:
   - Use consistent prefixes for different components [AUTH], [SOCKET], [COMPILE]
   - Include session/request IDs in all logs
   - Log both success and failure paths
   - Include relevant data context without sensitive information
   - Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)

4. **Debug-First Architecture**:
   - Implement logging before implementing features
   - Each new feature must include its logging strategy
   - Log state transitions and important variable values
   - Track all async operations and their timing
   - Monitor resource usage in performance-critical sections

5. **Troubleshooting Requirements**:
   - Every error condition must have an associated error log
   - Include stack traces for unexpected errors
   - Log user actions that lead to errors
   - Track system state during failures
   - Log recovery attempts and their outcomes


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

6. **Process Spawn and Event Handling Monitoring**:
   Critical Points to Monitor:
   - Pre-process spawn environment state
   - Process creation attempt timing
   - Post-spawn process state
   - Parent-child process communication
   - Resource allocation and cleanup
   - Event queue state and processing
   - Thread synchronization points
   - System resource utilization
   - Inter-process message passing
   - Deadlock detection points

   Logging Requirements:
   - Timestamp all process lifecycle events
   - Track process hierarchy relationships
   - Monitor system resource thresholds
   - Log all inter-process communications
   - Record event handler entry/exit
   - Track thread pool utilization
   - Monitor file descriptor usage
   - Log memory allocation patterns

   Early Warning Signs:
   - Missing process spawn logs
   - Delayed event processing
   - Resource exhaustion patterns
   - Communication timeouts
   - Thread pool saturation
   - File descriptor leaks
   - Memory growth patterns
   - Event queue backlog

## Database Information
- Database Name: ICS3U Curriculum Database
- Connection: Managed through DATABASE_URL environment variable
- Access: Via SQLAlchemy ORM with Flask-SQLAlchemy integration
- Main Tables:
  * courses: Stores course information
  * strands: Stores curriculum strands
  * overall_expectations: Stores overall expectations
  * specific_expectations: Stores specific expectations

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

## Session Learnings History
Last Updated: January 23, 2025

### Web Console Architecture
1. Components Overview:
   ```
   Browser                     Flask Server                  Backend
   +-----------+              +------------+                +-----------+
   | Xterm.js  | WebSocket/   | Socket.IO  |    Internal   | Code      |
   | Terminal  |<------------>| Server     |<------------->| Execution |
   +-----------+ Socket.IO    +------------+    Pipeline   +-----------+
        |                           |                           |
   +-----------+              +------------+                +-----------+
   | CodeMirror |  HTTP/      | Flask HTTP |    File        | Compiler  |
   | Editor    |<------------>| Server     |<------------->| Service   |
   +-----------+   AJAX      +------------+    System      +-----------+
   ```

2. Communication Flow:
   - Browser initiates WebSocket connection via Socket.IO
   - Flask server handles connection and maintains session
   - Code compilation requests flow through Socket.IO events
   - I/O operations are streamed in real-time via WebSocket
   - Error handling and state management at each layer

3. Key Implementation Findings:
   - Direct Socket.IO event handling is preferable to complex state management
   - Terminal initialization timing is critical for proper console display
   - Multiple console instances can cause resource conflicts
   - Keep Socket.IO event structure simple for reliability
   - Proper cleanup of terminal instances is essential

4. Current Recommendations:
   - Use simplified Socket.IO event structure:
     * 'connect/disconnect' for session management
     * 'compile_and_run' for code execution
     * 'input/output' for I/O operations
   - Ensure single console instance per session
   - Add explicit error handling for socket connection issues
   - Implement proper cleanup for terminal instances

5. Next Steps:
   - Reduce Socket.IO event complexity
   - Improve console initialization reliability
   - Enhance error handling and user feedback
   - Implement proper cleanup for terminal instances

### Flask Server Role (January 23, 2025)
1. **Core Responsibilities**:
   - Acts as WebSocket endpoint for real-time communication
   - Manages Socket.IO events and connections
   - Coordinates between web terminal and backend services
   - Handles session management and state persistence

2. **Critical Implementation Requirements**:
   - Proper eventlet initialization and monkey patching
   - Simplified Socket.IO configuration
   - Minimal middleware and event handlers
   - Clear separation of concerns between components

3. **Key Learnings**:
   - Eventlet monkey patching must occur before other imports
   - Socket.IO configuration should be minimal for reliability
   - Proper error handling is crucial for debugging
   - Detailed logging helps track connection issues
   - Single instance management prevents resource conflicts

4. **Performance Considerations**:
   - Minimize event handler complexity
   - Use efficient WebSocket communication
   - Implement proper cleanup routines
   - Monitor connection and resource usage
   - Handle disconnections gracefully

## Critical .NET Runtime Configuration (January 23, 2025)
1. **Project Configuration Requirements**:
   - UseAppHost must be set to false to prevent self-contained deployment
   - Runtime identifier (RID) must match the deployment environment
   - Project must use non-self-contained deployment model
   - DOTNET_ROOT environment variable must be properly set
   - DOTNET_CLI_HOME must be set to the temporary directory

2. **Runtime Path Configuration**:
   - DOTNET_ROOT must point to SDK location: '/nix/store/4k08ckhym1bcwnsk52j201a80l2xrkhp-dotnet-sdk-7.0.410'
   - Use dotnet command to execute DLLs instead of direct executable execution
   - Ensure proper environment variable inheritance in subprocess calls

3. **Build and Execution Flow**:
   - Build using optimized Release configuration
   - Execute using 'dotnet [dll_path]' instead of direct executable
   - Handle process spawning with proper environment setup
   - Ensure PTY setup for interactive console support

This guide helps maintain consistent project understanding across AI sessions. Always read these files at the start of each session and update them when making significant changes.