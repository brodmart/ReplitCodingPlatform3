# Project Memory System
Last Updated: January 16, 2025

## Project Overview
A bilingual educational coding platform for high school computer science students featuring:
- Interactive learning environment
- Administrative tools
- Progress tracking
- Bilingual support (English/French)
- Enhanced memory management system
- Version-controlled project memory

## Technical Stack
- Backend: Flask with APScheduler
- Database: PostgreSQL with SQLAlchemy ORM
- Frontend: CodeMirror, Flexbox
- Authentication: Custom secure login system

## Core Components

### 1. Database Models
- Student: User management with enhanced security features
- Achievement: Gamification system
- CodeSubmission: Student code handling
- CodingActivity: Exercise management
- SharedCode: Code sharing functionality
- AuditLog: System-wide change tracking

### 2. Security Features
- Password hashing with Werkzeug
- Failed login attempt tracking
- Account locking mechanism
- Session management
- CSRF protection
- Rate limiting

### 3. Core Functionalities
- Bilingual content delivery
- Student progress tracking
- Code compilation and execution
- Achievement system
- Administrative dashboard
- Automated backups

## Integration Points
1. Mail System
   - SMTP integration for notifications
   - Currently configured for Gmail
   - Requires valid SMTP credentials

2. Database Connections
   - PostgreSQL with connection pooling
   - Automatic ping and reconnection
   - Transaction management

## Known Issues
1. Email Configuration
   - SMTP authentication currently failing
   - Needs valid Gmail credentials

## Future Enhancements
1. Security Improvements (Based on security_recommendations.md)
   - Multi-factor authentication
   - Enhanced password policies
   - API key validation
   - OAuth 2.0 integration

2. Performance Optimizations
   - Database query optimization
   - Caching implementation
   - Asset compression

## Architecture Decisions
1. SQLAlchemy ORM
   - Chosen for: Type safety, migration support, and query optimization
   - Benefits: Reduces SQL injection risks, better maintainability

2. Custom Authentication
   - Reason: Specific requirements for educational institution integration
   - Features: Domain restriction, enhanced security logging

3. Bilingual Support
   - Implementation: Dynamic templates
   - Storage: JSON activity files with multilingual content

## Development Guidelines
1. Code Organization
   - Routes in separate blueprints
   - Model-specific business logic in models
   - Utility functions in utils/

2. Security Practices
   - All database queries using ORM
   - Input validation on both client and server
   - Proper error handling and logging

3. Testing Strategy
   - Unit tests for models
   - Integration tests for routes
   - Security vulnerability testing

## Maintenance Notes
1. Database Backups
   - Automated backups via APScheduler
   - Retention policy: 7 days
   - SSL-enabled secure transfers

2. Error Monitoring
   - Structured logging implemented
   - Different log levels for development/production
   - Audit logging for critical operations

This document should be updated with significant changes to maintain its value as a project memory system.