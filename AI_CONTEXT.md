# AI Session Context Guide
Last Updated: January 23, 2025

## CRITICAL WARNING - CONTENT PRESERVATION
IMPORTANT: No information in this file should be removed or significantly altered WITHOUT EXPLICIT USER CONFIRMATION. This file serves as the primary context for the project and all information is considered critical for maintaining project continuity and understanding.

## Project Overview
Ontario Secondary Computer Science Curriculum Educational Platform
- Multi-language interactive web-based programming learning environment
- Curriculum-aligned coding exercises with intelligent compiler services
- Advanced debugging and process management capabilities

## Tech Stack
- Python/Flask backend with PostgreSQL database
- Flask-Login authentication and comprehensive logging
- Mono and .NET SDK integration
- CodeMirror editor and Xterm.js terminal
- Multi-language compiler service

## Critical Components

### Web Console Implementation
Core Requirements:
- Web-based interactive console supporting all C# console operations
- CodeMirror editor and Xterm.js terminal integration
- Socket.IO for real-time I/O handling
- Code compilation and I/O must occur within web interface
- No command-line or external IDE compilation allowed


### Console Application Compatibility
1. Code Preservation:
   - Student code must run unmodified
   - Environment must adapt to support all valid submissions
   - No modifications to working code that runs in standard IDEs

2. Required Console Features:
   - Full support for C# console operations (Write, Read, Clear, etc.)
   - Console color and formatting options
   - Interactive input handling matching IDE behavior
   - Support for complex console-based interfaces

3. Application Support:
   - Handle large applications (up to 10MB source code)
   - Support multiple source files and projects
   - Match standard IDE behavior (Visual Studio, VS Code)


## Development Guidelines
1. Keep implementations simple and barebones
2. Focus on performance optimization
3. Implement proactive error handling
4. Regular testing and monitoring
5. Minimize dependencies

## Essential Logging Requirements
1. Immediate Implementation Points:
   - Service entry/exit points
   - State changes in critical components
   - API/Socket events (send/receive)
   - Error conditions with context
   - Performance-critical operations

2. Structure:
   - Use consistent prefixes: [AUTH], [SOCKET], [COMPILE]
   - Include session/request IDs
   - Log both success and failure paths
   - Track system state during failures

## .NET Runtime Configuration
1. Project Requirements:
   - UseAppHost: false (prevent self-contained deployment)
   - Runtime identifier (RID): match deployment environment
   - DOTNET_ROOT: '/nix/store/4k08ckhym1bcwnsk52j201a80l2xrkhp-dotnet-sdk-7.0.410'
   - DOTNET_CLI_HOME: temporary directory

2. Build and Execution:
   - Build using Release configuration
   - Execute using 'dotnet [dll_path]'
   - Proper PTY setup for interactive console

## Performance Optimizations
Latest Improvements (January 22, 2025):
- Reduced compilation time: 7.21s to 0.12s
- Implemented smart caching with invalidation
- Enhanced memory management
- Optimized build process
- Added comprehensive metrics tracking

## Architecture
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

## Replit Interactive Web Console Policies

### WebSocket Security
- Always verify WebSocket connections aren't HMR (Hot Module Reload) connections
- Use dedicated WebSocket paths (e.g., '/ws') to avoid conflicts
- Handle connection errors gracefully

### Process Execution
- Never run infinite loops or resource-intensive processes
- Set timeouts for long-running operations
- Clean up temporary files and processes

### Memory Management
- Keep memory usage within Replit's limits
- Clear buffers and cache regularly
- Monitor output size to prevent overflow

### Best Practices
- Use streaming for large outputs instead of buffering
- Implement rate limiting for user inputs
- Handle disconnections gracefully with reconnection logic
- Keep security in mind - validate and sanitize all inputs

This guide maintains critical project information for AI sessions. Update when making significant changes.