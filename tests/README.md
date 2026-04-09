# Tests

Test suite for CodeReview RL Environment.

## Structure

- `unit/` - Unit tests for individual components
- `integration/` - Integration tests for API endpoints
- `validation/` - OpenEnv validation tests
- `infrastructure/` - Docker and deployment tests

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_env.py

# Run with coverage
pytest --cov=env --cov=tasks --cov=server
```

## Writing Tests

Follow pytest conventions:
- Test files: `test_*.py`
- Test functions: `test_*`
- Use fixtures from `conftest.py`
