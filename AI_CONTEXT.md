# AI Session Context Guide
Last Updated: January 21, 2025

## Project Philosophy:
- The project must maintain nimbleness and efficiency as a top priority
- Avoid heavy frameworks or complex dependencies unless absolutely necessary
- Prefer lightweight, modular solutions that can be easily maintained
- Focus on performance and minimal resource usage

### Priority Files for Context (Read First):
1. project_memory.md - Overall project status and architecture
2. architectural_decisions.md - Key technical decisions
3. development_patterns.md - Common patterns and practices
4. integration_notes.md - System integration details

### Database Information:
The project uses a PostgreSQL database for curriculum storage:
- Database Name: ICS3U Curriculum Database
- Connection: Managed through DATABASE_URL environment variable
- Access: Via SQLAlchemy ORM with Flask-SQLAlchemy integration
- Main Tables:
  * courses: Stores course information (e.g., ICS3U)
    - Bilingual fields: title_en/fr, description_en/fr, prerequisite_en/fr
  * strands: Stores curriculum strands (A, B, C, D)
    - Bilingual fields: title_en/fr
    - Current Strands:
      A: Computing Environment and Tools / Environnement informatique de travail
      B: Programming Concepts / Concepts de programmation
      C: Software Development / Développement de logiciels
      D: Computing and Society / Enjeux sociétaux et perspectives professionnelles
  * overall_expectations: Stores overall expectations for each strand
    - Bilingual fields: description_en/fr
  * specific_expectations: Stores specific expectations linked to overall expectations
    - Bilingual fields: description_en/fr
- Current Status (as of Jan 20, 2025):
  * 1 course (ICS3U)
  * 4 strands
  * 11 overall expectations
  * 55 specific expectations
  * Complete bilingual content (French and English)
  * Verified data integrity and alignment

### How to Use These Files:

1. **Initial Context Loading**:
   - Review project_memory.md first for current project status
   - Check architectural_decisions.md for key technical choices
   - Reference development_patterns.md for coding standards
   - Consult integration_notes.md for system connections

2. **During Development**:
   - Update relevant memory files when making significant changes
   - Add timestamps to updates
   - Cross-reference between files when needed
   - Document new patterns or decisions

3. **Version Control Integration**:
   - All memory files are version controlled
   - Changes are tracked with timestamps
   - Historical context is preserved

### File Update Guidelines:

1. project_memory.md:
   - Update when adding new features
   - Modify when changing core functionality
   - Add new integrations or dependencies

2. architectural_decisions.md:
   - Document new architectural choices
   - Record reasons for technical decisions
   - Track changes in system design
   Latest Decision (January 20, 2025):
   Database-Driven Development Approach
   - Decision: Adapt models to match existing database schema
   - Rationale:
     * Database contains existing production data and activities
     * Current schema is well-designed and consistent
     * Lower risk than database migrations
     * Changes primarily involve nullable constraints
   - Impact:
     * Models will be updated to match database constraints
     * Affects Student, Progress tracking, and Achievement models
     * Maintains data integrity while reducing migration risks

3. development_patterns.md:
   - Add new coding patterns
   - Update best practices
   - Document common solutions

4. integration_notes.md:
   - Update when modifying integrations
   - Document new connection parameters
   - Track integration status

### Core Educational Requirements:

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

2. **Lexicon System Requirements**:
   - Unified bilingual support (French/English) across all levels
   - Context-aware syntax highlighting for all supported languages
   - Support for multiple programming paradigms
   - Advanced curriculum-specific content organization
   - Database-driven architecture for scalability
   - JSON-based content storage with curriculum mapping
   - Advanced code editor integration
   - Comprehensive search with curriculum tags
   - Student-specific curriculum alignment verification

3. **Language Support Requirements**:
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

4. **Assessment and Learning Analytics**:
   - Course-specific difficulty scaling
   - Adaptive problem complexity per curriculum level
   - Metacognitive assessment strategies
   - Performance analytics tailored to course requirements
   - Individual learning paths based on course curriculum
   - Cross-course progression tracking
   - Interactive Console Implementation:
     * CodeMirror-based interactive console similar to CodePen/W3Schools
     * Real-time code execution and output display
     * Support for multiple programming languages
     * Integrated error handling and output formatting

5. **Curriculum Verification System**:
   - Student-specific curriculum checking
   - Individual progress tracking per course
   - Automatic difficulty adjustment
   - Course-appropriate content delivery
   - Achievement tracking against course expectations
   - Cross-reference with Ontario curriculum documents

### Timestamps and Versioning:
- All updates include timestamps
- Format: "Last Updated: YYYY-MM-DD"
- Keep previous significant entries

### Cross-Referencing:
- Use relative links between files
- Maintain consistency in terminology
- Reference specific sections when needed

### Recent Layout Changes (January 17, 2025)
A critical layout fix was implemented to address container width inconsistencies across different page types:

1. **Container Width Inheritance**
   - Base template (base.html) controls initial container width settings
   - Full-width layout is applied conditionally based on page type
   - Main editor and activity pages were correctly using full width
   - Enhanced learning and grade list pages were incorrectly receiving padding

2. **Layout Fix Implementation**
   - Location: templates/base.html
   - Issue: Conditional statement for full-width layout was too restrictive
   - Fix: Extended the condition to include:
     * Enhanced learning pages
     * Activity list pages (Grade 10/11)
   - Previous working pages remain unaffected

3. **Affected Pages**
   - Working correctly (before fix):
     * Main editor page
     * Individual activity templates
   - Fixed pages (after update):
     * Enhanced learning view
     * Grade 10 activities list
     * Grade 11 activities list

This guide helps maintain consistent project understanding across AI sessions. Always read these files at the start of each session and update them when making significant changes.