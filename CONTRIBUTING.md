# Contributing to DB Facade

## Core Principles

### 1. FAIL-STOP is the Primary Design Principle
- NEVER implement fallbacks or paper over errors
- ALWAYS fail immediately and visibly when issues occur
- NEVER substitute mock/fake data when real data is unavailable
- ALWAYS exit with a clear error message rather than continuing with degraded functionality

### 2. Database Integrity
- NEVER mock database connections or data
- Database connections are REQUIRED for functionality
- If a database connection fails, the application should fail clearly
- All database operations must use the obfuscation layer

### 3. Exception Handling
- DO NOT use blanket try/except Exception handlers
- Only catch specific exceptions you can meaningfully handle
- Document the recovery strategy for each caught exception
- Let unhandled exceptions propagate for clearer debugging
- Example of INCORRECT pattern to avoid:
  ```python
  # BAD: This hides errors and continues with potentially corrupt state
  try:
      result = critical_operation()
  except Exception as e:
      logger.error(f"Something went wrong: {e}")
      result = None  # Continuing with None is dangerous
  ```
- Example of CORRECT pattern:
  ```python
  # GOOD: Specific exception with clear handling strategy
  try:
      result = critical_operation()
  except ConnectionError as e:
      logger.error(f"Database connection failed: {e}")
      sys.exit(1)  # Fail-stop instead of continuing
  ```

### 4. Privacy and Security
- NEVER leak semantic field names in production
- ALWAYS use the registry service for mapping
- DO NOT create shortcuts or bypasses around the obfuscation layer
- Ensure all logs are sanitized of semantic information
- Treat UUIDs as the only valid field identifiers in database operations

## Python Standards

### Python Version
- Code must be compatible with Python 3.13+
- Use modern Python features including:
  - Pattern matching (match/case)
  - Type annotations with latest typing features
  - Dataclasses and Pydantic models
  - Asynchronous programming where appropriate

### Type Annotations
- ALL functions must have complete type annotations
- Use the latest typing features (Python 3.13+)
- Example:
  ```python
  def process_record(record: ObfuscatedModel) -> dict[UUID, Any]:
      """Process a record and return UUID-mapped data."""
      # implementation
  ```

### Imports
- Organize imports in this order:
  1. Standard library imports
  2. Related third-party imports
  3. Local application imports
- Use explicit imports (avoid wildcard imports)

### Code Formatting
- Use 4 spaces for indentation
- Maximum line length of 100 characters
- Follow PEP 8 for naming conventions
- Use Black for automatic formatting

## Testing Requirements

### Test Coverage
- All code must have corresponding unit tests
- Minimum 90% test coverage required
- Include specific tests for privacy/security requirements
- Test both development and production modes

### Verification Tests
- Include tests that verify no semantic data is leaked
- Test error conditions and ensure proper fail-stop behavior
- Validate that exceptions propagate correctly
- Verify database interactions maintain obfuscation

## Development Workflow

### Pre-commit Hooks
- All commits must pass pre-commit hooks checking:
  - Code formatting (Black)
  - Import sorting
  - Type checking (mypy)
  - Security patterns
  - Exception handling patterns
  - Privacy leakage detection

### Pull Request Process
- PRs require passing CI checks
- Include test coverage for all new code
- Update documentation for new features
- Add relevant information to CHANGELOG.md

## Documentation

### Code Documentation
- All public functions must have docstrings
- Include parameter and return type descriptions
- Document exceptions that may be raised
- Explain security implications where relevant

### Project Documentation
- Keep README.md up to date with installation and usage
- Document security model and privacy guarantees
- Include examples for common use cases
- Maintain architecture documentation