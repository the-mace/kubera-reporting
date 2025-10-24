# Contributing to Kubera Reporting

Thank you for your interest in contributing to Kubera Reporting! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and constructive in all interactions
- Welcome newcomers and help them get started
- Focus on what's best for the community and the project

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/the-mace/kubera-reporting.git
cd kubera-reporting
```

### 2. Set Up Development Environment

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 3. Set Up Credentials for Testing

Create `~/.env` with your credentials:

```bash
KUBERA_API_KEY=your_api_key_here
KUBERA_SECRET=your_secret_here
KUBERA_REPORT_EMAIL=your-email@example.com
GROK_API_KEY=your_grok_key_here
```

## Development Workflow

### Creating a Branch

Use descriptive branch names:

```bash
# For new features
git checkout -b feature/add-weekly-reports

# For bug fixes
git checkout -b fix/email-formatting

# For documentation
git checkout -b docs/improve-readme
```

### Making Changes

1. **Write clear, focused commits**
   - One logical change per commit
   - Write descriptive commit messages

2. **Follow code style**
   - We use Ruff for formatting and linting
   - Type hints are required for all functions
   - Line length: 100 characters

3. **Add tests for new functionality**
   - Unit tests in `tests/`
   - Aim for >80% code coverage
   - Use pytest

4. **Update documentation**
   - Update README.md if adding new features
   - Add docstrings to new functions
   - Update examples/ if applicable

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_storage.py

# Run with coverage report
pytest --cov=kubera_reporting --cov-report=term-missing

# Run only specific test
pytest tests/test_storage.py::test_save_and_load_snapshot
```

### Code Quality Checks

Run these before submitting a PR:

```bash
# Format code
ruff format .

# Check for linting issues
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Type checking
mypy kubera_reporting

# All checks together
ruff check . && ruff format . && mypy kubera_reporting && pytest
```

## Pull Request Process

### Before Submitting

- [ ] All tests pass (`pytest`)
- [ ] Code is formatted (`ruff format .`)
- [ ] No linting errors (`ruff check .`)
- [ ] Type checking passes (`mypy kubera_reporting`)
- [ ] Coverage hasn't decreased
- [ ] Documentation is updated
- [ ] Commit messages are clear

### Submitting the PR

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request** on GitHub with:
   - Clear title describing the change
   - Description explaining what and why
   - Reference any related issues (`Fixes #123`)
   - Screenshots/examples if applicable

3. **Respond to feedback**
   - Address review comments promptly
   - Push additional commits to your branch
   - Ask questions if anything is unclear

### PR Review Criteria

Your PR will be reviewed for:

- **Functionality**: Does it work as intended?
- **Tests**: Are there adequate tests?
- **Code Quality**: Is it well-structured and readable?
- **Documentation**: Are changes documented?
- **Backwards Compatibility**: Does it break existing code?

## Types of Contributions

### Bug Reports

**Include:**
- Python version
- Package version
- Error messages and stack traces
- Minimal code to reproduce
- Expected vs actual behavior

### Feature Requests

**Include:**
- Use case description
- Proposed API/interface
- Example usage code
- Why existing functionality doesn't work

### Code Contributions

**Good First Issues:**
- Look for issues labeled `good first issue`
- These are beginner-friendly tasks
- Ask questions if anything is unclear

**Common Areas:**
- Adding new report types (weekly, monthly, annual)
- Improving email templates
- Adding new AI analysis features
- Writing tests
- Improving documentation

### Documentation Improvements

Documentation PRs are highly valued!

- Fix typos or unclear explanations
- Add examples or use cases
- Improve API documentation
- Update outdated information

## Project Structure

```
kubera-reporting/
├── kubera_reporting/      # Main package
│   ├── __init__.py       # Package exports
│   ├── cli.py            # Command-line interface
│   ├── fetcher.py        # Kubera API data fetching
│   ├── storage.py        # JSON snapshot storage
│   ├── reporter.py       # Report generation
│   ├── emailer.py        # Email sending
│   ├── llm_client.py     # AI/LLM interface
│   ├── types.py          # Type definitions
│   └── exceptions.py     # Custom exceptions
├── tests/                # Test suite
│   ├── test_storage.py   # Storage tests
│   ├── test_reporter.py  # Reporter tests
│   └── ...
├── examples/             # Usage examples
├── .github/              # GitHub configuration
├── pyproject.toml        # Project metadata
└── README.md             # User documentation
```

## Coding Standards

### Python Style

- Follow PEP 8 (enforced by Ruff)
- Use type hints for all function parameters and returns
- Write docstrings for public functions
- Keep functions focused and small

### Type Hints

```python
# Good
def fetch_snapshot(portfolio_id: str | None = None) -> PortfolioSnapshot:
    """Fetch current portfolio snapshot."""
    ...

# Bad - no types
def fetch_snapshot(portfolio_id=None):
    ...
```

### Error Handling

- Use custom exceptions from `exceptions.py`
- Provide helpful error messages
- Include context in exception messages

```python
# Good
raise DataFetchError(
    f"Failed to fetch portfolio {portfolio_id}: {error_details}"
)

# Bad
raise Exception("Fetch failed")
```

### Testing

- Test both success and error cases
- Use descriptive test names
- Use pytest fixtures for common setup

```python
def test_save_and_load_snapshot(temp_dir, sample_snapshot):
    """Test saving and loading a snapshot."""
    storage = SnapshotStorage(temp_dir)
    storage.save_snapshot(sample_snapshot)
    loaded = storage.load_snapshot(datetime.now())
    assert loaded is not None
```

### Commit Messages

Follow conventional commit format:

```
type(scope): brief description

Detailed explanation of the change.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions or changes
- `refactor`: Code refactoring
- `style`: Code style changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(reporter): add weekly summary reports

Add new weekly report generation that summarizes changes over the
past 7 days with percentage calculations.

Fixes #45
```

```
fix(emailer): handle mail command timeout gracefully

Previously crashed when mail command timed out. Now properly catches
TimeoutExpired and raises EmailError.

Fixes #67
```

## Questions?

- **General questions**: Use GitHub Discussions
- **Bug reports**: GitHub Issues
- **Security issues**: Email maintainers directly (don't open public issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions make this project better for everyone. Thank you for taking the time to contribute!
