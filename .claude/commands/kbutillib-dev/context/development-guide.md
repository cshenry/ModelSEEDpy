# KBUtilLib Development Guide

Step-by-step guide for developing and contributing to KBUtilLib.

## Development Setup

### Prerequisites
- Python 3.9+
- `uv` package manager (recommended)
- Git with submodule support

### Initial Setup
```bash
# Clone repository
git clone https://github.com/your-org/KBUtilLib.git
cd KBUtilLib

# Initialize submodules
git submodule update --init --recursive

# Install with development dependencies
uv sync --all-extras

# Verify installation
uv run python -c "import kbutillib; print(kbutillib.__all__)"
```

### Alternative: pip Installation
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e ".[dev,notebooks]"
```

## Adding a New Utility Module

### Step 1: Plan Your Module

Before coding, determine:
1. **Purpose**: What does this module do?
2. **Parent class**: Which utility to inherit from?
3. **Dependencies**: What external libraries needed?
4. **API surface**: What methods will be public?

### Step 2: Create the Module File

```python
# src/kbutillib/my_new_utils.py
"""My New Utilities module.

This module provides utilities for [purpose].

Example:
    >>> from kbutillib import MyNewUtils
    >>> utils = MyNewUtils()
    >>> result = utils.my_method("param")
"""

from typing import Any, Dict, List, Optional
from .shared_env_utils import SharedEnvUtils  # or appropriate parent


class MyNewUtils(SharedEnvUtils):
    """Utility class for [purpose].

    This class provides methods for [description].

    Attributes:
        some_attribute: Description of attribute.

    Example:
        >>> utils = MyNewUtils(config_file="my_config.yaml")
        >>> utils.my_method("test")
    """

    def __init__(
        self,
        config_file: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize MyNewUtils.

        Args:
            config_file: Optional path to configuration file.
            **kwargs: Additional arguments passed to parent class.
        """
        super().__init__(config_file=config_file, **kwargs)
        self.log_info("MyNewUtils initialized")

        # Module-specific initialization
        self._cache: Dict[str, Any] = {}

    def my_method(
        self,
        required_param: str,
        optional_param: Optional[int] = None
    ) -> Dict[str, Any]:
        """Brief description of method.

        Longer description explaining what the method does,
        any important behaviors, and edge cases.

        Args:
            required_param: Description of this parameter.
            optional_param: Description of optional parameter.
                Defaults to None.

        Returns:
            Dictionary containing:
                - key1: Description
                - key2: Description

        Raises:
            ValueError: When required_param is empty.
            ConnectionError: When external service unavailable.

        Example:
            >>> utils = MyNewUtils()
            >>> result = utils.my_method("test", optional_param=5)
            >>> print(result["key1"])
        """
        # Track method call for provenance
        self.initialize_call("my_method", {
            "required_param": required_param,
            "optional_param": optional_param
        })

        # Validate arguments
        if not required_param:
            raise ValueError("required_param cannot be empty")

        # Check cache
        cache_key = f"my_method:{required_param}"
        if cache_key in self._cache:
            self.log_debug(f"Cache hit: {cache_key}")
            return self._cache[cache_key]

        # Main implementation
        self.log_info(f"Processing: {required_param}")
        result = self._do_actual_work(required_param, optional_param)

        # Cache result
        self._cache[cache_key] = result

        return result

    def _do_actual_work(
        self,
        param1: str,
        param2: Optional[int]
    ) -> Dict[str, Any]:
        """Internal method for actual processing.

        Private methods start with underscore and don't need
        full docstrings unless complex.
        """
        # Implementation here
        return {"key1": param1, "key2": param2 or 0}
```

### Step 3: Add to Package Exports

```python
# src/kbutillib/__init__.py

# Add import with try/except for optional dependencies
try:
    from .my_new_utils import MyNewUtils
except ImportError as e:
    import logging
    logging.getLogger(__name__).debug(f"MyNewUtils not available: {e}")
    MyNewUtils = None

# Add to __all__
__all__ = [
    # ... existing exports ...
    "MyNewUtils",
]
```

### Step 4: Write Tests

```python
# tests/test_my_new_utils.py
"""Tests for MyNewUtils."""

import pytest
from kbutillib import MyNewUtils


class TestMyNewUtils:
    """Test suite for MyNewUtils class."""

    @pytest.fixture
    def utils(self):
        """Create MyNewUtils instance for testing."""
        return MyNewUtils()

    def test_initialization(self, utils):
        """Test that utils initializes correctly."""
        assert utils is not None
        assert hasattr(utils, 'logger')

    def test_initialization_with_config(self, tmp_path):
        """Test initialization with config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n")
        utils = MyNewUtils(config_file=str(config_file))
        assert utils is not None

    def test_my_method_basic(self, utils):
        """Test my_method with valid input."""
        result = utils.my_method("test_param")
        assert result is not None
        assert "key1" in result
        assert result["key1"] == "test_param"

    def test_my_method_with_optional(self, utils):
        """Test my_method with optional parameter."""
        result = utils.my_method("test", optional_param=42)
        assert result["key2"] == 42

    def test_my_method_empty_param_raises(self, utils):
        """Test that empty required_param raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            utils.my_method("")

    def test_my_method_caching(self, utils):
        """Test that results are cached."""
        result1 = utils.my_method("cached_param")
        result2 = utils.my_method("cached_param")
        assert result1 is result2  # Same object from cache

    @pytest.mark.parametrize("param,expected", [
        ("a", "a"),
        ("test", "test"),
        ("longer_param", "longer_param"),
    ])
    def test_my_method_various_inputs(self, utils, param, expected):
        """Test my_method with various inputs."""
        result = utils.my_method(param)
        assert result["key1"] == expected


class TestMyNewUtilsIntegration:
    """Integration tests for MyNewUtils."""

    @pytest.mark.integration
    def test_with_real_service(self):
        """Test integration with external service."""
        pytest.skip("Requires external service")
```

### Step 5: Add Documentation

```markdown
# docs/modules/my_new_utils.md

# MyNewUtils

Utility class for [purpose].

## Overview

MyNewUtils provides functionality for [description]. It inherits from
SharedEnvUtils, giving access to configuration and token management.

## Installation

MyNewUtils is included in the base kbutillib package:

```python
from kbutillib import MyNewUtils
```

## Quick Start

```python
from kbutillib import MyNewUtils

# Initialize
utils = MyNewUtils()

# Basic usage
result = utils.my_method("parameter")
print(result)
```

## Configuration

MyNewUtils uses the standard configuration system:

```yaml
# ~/kbutillib_config.yaml
my_new_utils:
  setting1: value1
  setting2: value2
```

## API Reference

### my_method(required_param, optional_param=None)

Brief description.

**Parameters:**
- `required_param` (str): Description
- `optional_param` (int, optional): Description

**Returns:**
- dict: Result dictionary with keys...

**Example:**
```python
result = utils.my_method("test", optional_param=5)
```

## Composition Examples

MyNewUtils can be combined with other utilities:

```python
from kbutillib import MyNewUtils, KBGenomeUtils

class CustomTools(MyNewUtils, KBGenomeUtils):
    pass

tools = CustomTools()
```

## See Also

- [SharedEnvUtils](shared_env_utils.md) - Parent class
- [Related utility](related.md)
```

### Step 6: Update README

Add a brief mention to the main README.md if the module is significant.

## Running Tests

### Full Test Suite
```bash
# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=kbutillib --cov-report=html

# Verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

### Specific Tests
```bash
# Single file
uv run pytest tests/test_my_new_utils.py

# Single test class
uv run pytest tests/test_my_new_utils.py::TestMyNewUtils

# Single test
uv run pytest tests/test_my_new_utils.py::TestMyNewUtils::test_my_method_basic

# Pattern matching
uv run pytest -k "my_method"
```

### Test Markers
```bash
# Skip slow tests
uv run pytest -m "not slow"

# Only integration tests
uv run pytest -m integration
```

## Code Quality

### Linting with Ruff
```bash
# Check for issues
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/
```

### Type Checking with MyPy
```bash
# Check types
uv run mypy src/kbutillib/

# Specific file
uv run mypy src/kbutillib/my_new_utils.py
```

### Pre-commit Hooks
```bash
# Install hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

## Working with Dependencies

### Adding Runtime Dependencies
```bash
# Add to project
uv add requests

# With version constraint
uv add "requests>=2.28"
```

### Adding Development Dependencies
```bash
uv add --dev pytest-cov
```

### Adding Optional Dependencies
Edit pyproject.toml:
```toml
[project.optional-dependencies]
ml = ["torch>=2.0", "transformers>=4.0"]
```

### Managing Git Submodules
```bash
# Initialize
git submodule update --init --recursive

# Update to latest
git submodule update --remote

# Check status
git submodule status
```

## Common Development Patterns

### Inheriting from BaseUtils
```python
from .base_utils import BaseUtils

class MyUtils(BaseUtils):
    def my_method(self):
        self.initialize_call("my_method", {})
        self.log_info("Starting...")
        # work
        self.log_debug("Details...")
        return result
```

### Inheriting from SharedEnvUtils
```python
from .shared_env_utils import SharedEnvUtils

class MyUtils(SharedEnvUtils):
    def my_method(self):
        # Access config
        setting = self.get_config_value("my.setting")

        # Access token
        token = self.get_token("kbase")

        return result
```

### HTTP Client Pattern
```python
import requests
from .shared_env_utils import SharedEnvUtils

class MyAPIUtils(SharedEnvUtils):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session = requests.Session()
        self._base_url = self.get_config_value("my_api.endpoint")

    def _request(self, method, endpoint, **kwargs):
        """Make authenticated request."""
        url = f"{self._base_url}/{endpoint}"
        headers = kwargs.pop("headers", {})

        token = self.get_token("my_api")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = self._session.request(
            method, url, headers=headers, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def get_resource(self, resource_id):
        return self._request("GET", f"resources/{resource_id}")
```

### Caching Pattern
```python
from functools import lru_cache
from .base_utils import BaseUtils

class CachedUtils(BaseUtils):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cache = {}

    def get_with_cache(self, key):
        if key not in self._cache:
            self._cache[key] = self._fetch(key)
        return self._cache[key]

    def clear_cache(self):
        self._cache.clear()

    @lru_cache(maxsize=100)
    def get_with_lru(self, key):
        """Uses built-in LRU cache."""
        return self._fetch(key)
```

## Debugging Tips

### Enable Debug Logging
```python
import logging
logging.getLogger("kbutillib").setLevel(logging.DEBUG)

utils = MyUtils()
utils.my_method("test")  # Will show debug output
```

### Interactive Debugging
```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use pytest debugging
# pytest --pdb  # Drop into debugger on failure
# pytest --pdb-first  # Drop on first failure
```

### Inspect Provenance
```python
utils = MyUtils()
utils.my_method("test")
utils.another_method("param")

# See all tracked calls
for call in utils.provenance:
    print(f"{call['method']}: {call['params']}")
```

## Pull Request Checklist

Before submitting a PR:

- [ ] All tests pass: `uv run pytest`
- [ ] Linting passes: `uv run ruff check src/`
- [ ] Types check: `uv run mypy src/kbutillib/`
- [ ] New code has tests
- [ ] Docstrings follow Google style
- [ ] Module added to `__init__.py`
- [ ] README updated if adding major feature
- [ ] No secrets in code

## Troubleshooting

### Import Errors
```python
# Check if module is available
from kbutillib import MyUtils
if MyUtils is None:
    print("Module not available - check dependencies")
```

### Submodule Issues
```bash
# Reset submodules
git submodule deinit -f --all
git submodule update --init --recursive
```

### Test Discovery Issues
```bash
# Check pytest can find tests
uv run pytest --collect-only

# Verbose collection
uv run pytest --collect-only -v
```
