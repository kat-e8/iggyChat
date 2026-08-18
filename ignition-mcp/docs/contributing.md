# Contributing Guide

Thank you for your interest in contributing to the Ignition MCP Server! This guide will help you get started with development and contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Development Workflow](#development-workflow)
- [Release Process](#release-process)

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.10+** installed
- **Git** for version control
- **uv** or **pip** for package management
- Access to an **Ignition Gateway 8.3+** for testing
- Familiarity with **asyncio** and **MCP protocol**

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

```bash
git clone https://github.com/yourusername/ignition-mcp.git
cd ignition-mcp
```

3. **Add upstream remote**:

```bash
git remote add upstream https://github.com/originalowner/ignition-mcp.git
```

## Development Setup

### 1. Create Development Environment

```bash
# Using uv (recommended)
uv sync --group dev

# Using pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Install Pre-commit Hooks

```bash
pre-commit install
```

This ensures code formatting and linting on every commit.

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your test gateway details
```

### 4. Verify Setup

```bash
# Run tests
uv run pytest

# Lint and format check (ruff also handles import sorting)
uv run ruff check .
uv run ruff format --check .

# Type check
uv run mypy src/

# Smoke-test the server starts
uv run python mcp_server.py --transport stdio &
```

## Code Style Guidelines

We follow Python best practices and use automated tooling to maintain consistent code style.

### Formatting Tools

- **Ruff**: Formatting, import sorting, and linting (100 character line length, rules `E`, `F`, `W`, `I` — see `pyproject.toml`)
- **mypy**: Static type checking (`disallow_untyped_defs = true`)

### Style Rules

#### 1. Code Formatting

```python
# Good: Black-formatted code
async def get_gateway_status(self) -> Dict[str, Any]:
    """Get gateway status information."""
    return await self._request("GET", "/system/gateway-network/remote-servers/status")


# Bad: Inconsistent formatting
async def get_gateway_status(self)->Dict[str,Any]:
    return await self._request( "GET","/system/gateway-network/remote-servers/status" )
```

#### 2. Type Hints

Always use type hints for function signatures:

```python
# Good: Complete type hints
async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Execute an Ignition Gateway API call."""
    ...

# Bad: Missing type hints
async def call_tool(self, name, arguments):
    """Execute an Ignition Gateway API call."""
    ...
```

#### 3. Docstrings

Use Google-style docstrings:

```python
async def execute_api_call(
    self, 
    client: IgnitionClient, 
    tool_def: Dict[str, Any], 
    arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the actual API call.
    
    Args:
        client: Ignition client instance
        tool_def: Tool definition dictionary
        arguments: Call arguments
        
    Returns:
        API response data
        
    Raises:
        httpx.HTTPStatusError: On API errors
    """
```

#### 4. Import Organization

Ruff's `I` rule set enforces import order — standard library, then third-party, then local:

```python
# Standard library imports
import asyncio
import json
from typing import Any, Dict, List

# Third-party imports
import httpx
from fastmcp import FastMCP

# Local imports
from .config import settings
from .ignition_client import IgnitionClient
```

#### 5. Error Handling

Use specific exceptions and proper error messages:

```python
# Good: Specific error handling
try:
    result = await client._request(method, final_path, **kwargs)
except httpx.HTTPStatusError as e:
    return CallToolResult(
        content=[TextContent(type="text", text=f"HTTP {e.response.status_code}: {e.response.text}")],
        isError=True
    )
except httpx.ConnectError:
    return CallToolResult(
        content=[TextContent(type="text", text="Failed to connect to gateway")],
        isError=True
    )

# Bad: Generic error handling
try:
    result = await client._request(method, final_path, **kwargs)
except Exception as e:
    return CallToolResult(
        content=[TextContent(type="text", text=str(e))],
        isError=True
    )
```

### Running Style Checks

```bash
# Format code
uv run ruff format .

# Check style and types
uv run ruff check .
uv run mypy src/

# Run all checks
pre-commit run --all-files
```

## Testing

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_client.py        # IgnitionClient unit tests (mocked httpx)
├── test_tools.py         # Tool logic unit tests (mocked client)
└── test_integration.py   # Live gateway tests (skipped unless RUN_LIVE_GATEWAY_TESTS=1)
```

### Writing Tests

#### Unit Tests (mocked, no live gateway)

```python
# tests/test_client.py style — mock httpx, assert on the request/response contract
import pytest
from unittest.mock import AsyncMock, patch
from ignition_mcp.ignition_client import IgnitionClient


@pytest.mark.asyncio
async def test_get_gateway_info():
    client = IgnitionClient(gateway_url="http://test-gateway:8088", api_key="test-key")
    with patch.object(client, "_request", new=AsyncMock(return_value={"edition": "standard"})):
        result = await client.get_gateway_info()
        assert result["edition"] == "standard"
    await client.close()
```

#### Integration Tests (live gateway, opt-in)

```python
# tests/test_integration.py — guarded by RUN_LIVE_GATEWAY_TESTS
import os
import pytest
from ignition_mcp.ignition_client import IgnitionClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_GATEWAY_TESTS"),
    reason="Set RUN_LIVE_GATEWAY_TESTS=1 to run against a real gateway",
)


@pytest.mark.asyncio
async def test_gateway_info():
    async with IgnitionClient() as client:
        info = await client.get_gateway_info()
        assert "ignitionVersion" in info
```

### Running Tests

```bash
# Unit tests only (default — no live gateway needed)
uv run pytest tests/ -v

# Include live-gateway integration tests
RUN_LIVE_GATEWAY_TESTS=1 uv run pytest tests/test_integration.py -v

# With coverage
uv run pytest --cov=src/ignition_mcp --cov-report=html

# Single file / pattern
uv run pytest tests/test_client.py
uv run pytest -k "gateway_info"
```

Test configuration (`asyncio_mode`, `testpaths`) lives in `[tool.pytest.ini_options]`
in `pyproject.toml` — no separate `pytest.ini`.

## Pull Request Process

### 1. Create Feature Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Changes

- Write code following the style guidelines
- Add tests for new functionality
- Update documentation if needed
- Ensure all tests pass

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add support for custom timeout configuration

- Add timeout parameter to IgnitionClient
- Update configuration with timeout setting
- Add tests for timeout functionality
- Update documentation"
```

#### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(tools): add project import validation
fix(client): handle connection timeout errors
docs: update installation guide for Windows
test: add integration tests for backup tools
```

### 4. Push and Create PR

```bash
# Push feature branch
git push origin feature/your-feature-name

# Create pull request on GitHub
```

### 5. PR Requirements

Your pull request must:

- [ ] Include clear description of changes
- [ ] Have passing tests (`pytest`)
- [ ] Pass code quality checks (`ruff check`, `ruff format --check`, `mypy`)
- [ ] Include documentation updates if needed
- [ ] Follow semantic versioning for breaking changes
- [ ] Have appropriate commit messages

### 6. Review Process

- Maintainers will review your PR
- Address any feedback or requested changes
- Once approved, your PR will be merged

## Issue Guidelines

### Reporting Bugs

Use the bug report template:

```markdown
**Bug Description**
A clear description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. macOS 14.0]
- Python: [e.g. 3.11.0]
- Ignition Version: [e.g. 8.1.25]
- MCP Server Version: [e.g. 0.1.0]

**Additional Context**
Any other context about the problem.
```

### Feature Requests

Use the feature request template:

```markdown
**Feature Description**
A clear description of what you want to happen.

**Use Case**
Describe the use case that would benefit from this feature.

**Proposed Solution**
If you have ideas on how to implement this, describe them here.

**Alternatives Considered**
Describe any alternative solutions you've considered.

**Additional Context**
Any other context or screenshots about the feature request.
```

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `priority:high`: High priority issue
- `priority:low`: Low priority issue

## Development Workflow

### 1. Daily Development

```bash
# Start development session
git checkout main
git pull upstream main
git checkout -b feature/new-feature

# Make changes, test frequently
uv run pytest tests/
uv run python mcp_server.py --transport stdio

# Commit often with good messages
git add .
git commit -m "feat: implement basic functionality"

# Continue development...
```

### 2. Before Submitting

```bash
# Run full test suite
pytest

# Check code quality
pre-commit run --all-files

# Update documentation if needed
# Update CHANGELOG.md if significant changes

# Rebase on latest main
git fetch upstream
git rebase upstream/main

# Push and create PR
git push origin feature/new-feature
```

### 3. Keeping Fork Updated

```bash
# Regularly sync with upstream
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH` (e.g., 1.2.3)
- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes (backward compatible)

### Release Steps

1. **Update Version**:
   - Update `pyproject.toml`
   - Update `CHANGELOG.md`

2. **Create Release PR**:
   ```bash
   git checkout -b release/v1.2.3
   # Make version updates
   git commit -m "chore: bump version to 1.2.3"
   ```

3. **Tag Release**:
   ```bash
   git tag v1.2.3
   git push upstream v1.2.3
   ```

4. **GitHub Release**:
   - Create release on GitHub
   - Include changelog
   - Attach built packages

## Getting Help

### Development Questions

- **GitHub Discussions**: For general questions
- **Discord/Slack**: Real-time chat (if available)
- **Issues**: For specific bugs or features

### Resources

- [MCP Protocol Documentation](https://github.com/modelcontextprotocol)
- [Ignition API Documentation](https://docs.inductiveautomation.com/)
- [Python AsyncIO Guide](https://docs.python.org/3/library/asyncio.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to the Ignition MCP Server! Your contributions help make this project better for everyone.