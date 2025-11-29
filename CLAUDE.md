# CLAUDE.md - Project Guidelines

Instructions for Claude
For all work in this repository, you must use the beads issue tracker.
Use the bd command-line tool to create, manage, and close issues.
Do not use markdown files for creating to-do lists or for tracking your work. All issues and bugs are to be tracked via bd.

bd - Dependency-Aware Issue Tracker

Issues chained together like beads.

GETTING STARTED
  bd init   Initialize bd in your project
            Creates .beads/ directory with project-specific database        
            Auto-detects prefix from directory name (e.g., myapp-1, myapp-2)

  bd init --prefix api   Initialize with custom prefix
            Issues will be named: api-1, api-2, ...

CREATING ISSUES
  bd create "Fix login bug"
  bd create "Add auth" -p 0 -t feature
  bd create "Write tests" -d "Unit tests for auth" --assignee alice

VIEWING ISSUES
  bd list       List all issues
  bd list --status open  List by status
  bd list --priority 0  List by priority (0-4, 0=highest)
  bd show bd-1       Show issue details

MANAGING DEPENDENCIES
  bd dep add bd-1 bd-2     Add dependency (bd-2 blocks bd-1)
  bd dep tree bd-1  Visualize dependency tree
  bd dep cycles      Detect circular dependencies

DEPENDENCY TYPES
  blocks  Task B must complete before task A
  related  Soft connection, doesn't block progress
  parent-child  Epic/subtask hierarchical relationship
  discovered-from  Auto-created when AI discovers related work

READY WORK
  bd ready       Show issues ready to work on
            Ready = status is 'open' AND no blocking dependencies
            Perfect for agents to claim next work!

UPDATING ISSUES
  bd update bd-1 --status in_progress
  bd update bd-1 --priority 0
  bd update bd-1 --assignee bob

CLOSING ISSUES
  bd close bd-1
  bd close bd-2 bd-3 --reason "Fixed in PR #42"

DATABASE LOCATION
  bd automatically discovers your database:
    1. --db /path/to/db.db flag
    2. $BEADS_DB environment variable
    3. .beads/*.db in current directory or ancestors
    4. ~/.beads/default.db as fallback

AGENT INTEGRATION
  bd is designed for AI-supervised workflows:
    • Agents create issues when discovering new work
    • bd ready shows unblocked work ready to claim
    • Use --json flags for programmatic parsing
    • Dependencies prevent agents from duplicating effort
	
GIT WORKFLOW (AUTO-SYNC)
  bd automatically keeps git in sync:
    • ✓ Export to JSONL after CRUD operations (5s debounce)
    • ✓ Import from JSONL when newer than DB (after git pull)
    • ✓ Works seamlessly across machines and team members
    • No manual export/import needed!
  Disable with: --no-auto-flush or --no-auto-import

### 1. No Stubs, No Shortcuts
- **NEVER** use `unimplemented!()`, `todo!()`, or stub implementations
- **NEVER** leave placeholder code or incomplete implementations
- **NEVER** skip functionality because it seems complex
- Every function must be fully implemented and working
- Every feature must be complete before moving on

### 2. Break Down Complex Tasks
- Large files or complex features should be broken into manageable chunks
- If a file is too large, discuss breaking it into smaller modules
- If a task seems overwhelming, ask the user how to break it down
- Work incrementally, but each increment must be complete and functional

## Python Best Practices

### Code Style
- Follow PEP 8 style guidelines
- Use 4 spaces for indentation (no tabs)
- Maximum line length of 88 characters (Black formatter default)
- Use meaningful, descriptive variable and function names
- Prefer snake_case for functions and variables, PascalCase for classes

### Type Hints
- Use type hints for all function parameters and return values
- Import types from `typing` module when needed (List, Dict, Optional, Union, etc.)
- Use `| None` syntax for optional types in Python 3.10+

### Imports
- Group imports in order: standard library, third-party, local
- Use absolute imports over relative imports
- Avoid wildcard imports (`from module import *`)

### Functions and Classes
- Keep functions small and focused on a single responsibility
- Use docstrings for public functions and classes (Google or NumPy style)
- Prefer composition over inheritance
- Use `@staticmethod` and `@classmethod` decorators appropriately

### Error Handling
- Use specific exception types, not bare `except:`
- Handle exceptions at the appropriate level
- Use context managers (`with` statements) for resource management
- Raise exceptions with meaningful error messages

### Testing
- Write tests for new functionality
- Use pytest as the testing framework
- Aim for descriptive test names that explain the expected behavior
- Use fixtures for common test setup

### Project Structure
- Keep related code in modules
- Use `__init__.py` to define public APIs
- Separate concerns: business logic, I/O, configuration

### Security
- Never commit secrets or API keys
- Use environment variables for sensitive configuration
- Validate and sanitize user input
- Be cautious with string formatting in SQL/shell commands

### Git Workflow
- Write clear, descriptive commit messages
- Keep commits focused and atomic
- Do not commit, leave that to the user.
