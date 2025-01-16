# Architectural Decision Records (ADR)
Last Updated: January 16, 2025

## ADR 1: Custom Authentication System
### Context
The project requires specific integration with educational institutions and domain restrictions.

### Decision
Implemented a custom authentication system instead of using third-party solutions.

### Consequences
- Pros:
  * Full control over user management
  * Domain-specific email restrictions
  * Custom security logging
- Cons:
  * More maintenance responsibility
  * Need to implement security best practices

## ADR 2: SQLAlchemy ORM
### Context
Need for type-safe database operations and migration support.

### Decision
Chose SQLAlchemy ORM over raw SQL or other ORMs.

### Consequences
- Pros:
  * Type safety
  * Migration support
  * Query optimization
  * Better maintainability
- Cons:
  * Learning curve
  * Performance overhead for simple queries

## ADR 3: Bilingual Support Implementation
### Context
Need to support both English and French content delivery.

### Decision
Implemented dynamic templates with JSON-based activity files for multilingual content.

### Consequences
- Pros:
  * Easy content management
  * Flexible language switching
  * Maintainable content structure
- Cons:
  * Additional complexity in content management
  * Need for careful synchronization of translations

## ADR 4: Security Implementation
### Context
Need for robust security in an educational environment.

### Decision
Implemented multiple security layers:
- Failed login tracking
- Account locking
- Session management
- CSRF protection
- Rate limiting

### Consequences
- Pros:
  * Enhanced security
  * Better audit capabilities
  * Protection against common attacks
- Cons:
  * Additional system complexity
  * Need for careful security testing

## ADR 5: Database Backup Strategy
### Context
Need for reliable data preservation and disaster recovery.

### Decision
Implemented automated backups using APScheduler with:
- Daily backup schedule
- 7-day retention
- SSL-enabled transfers
- Version control for backups

### Consequences
- Pros:
  * Reliable data preservation
  * Automated recovery options
  * Secure backup transfers
- Cons:
  * Storage overhead
  * Need for backup monitoring
