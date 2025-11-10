# Command: doc-code-usage

## Purpose

Create comprehensive usage documentation that shows developers how to USE a codebase as a library, tool, or API. This is external-facing documentation for consumers of the code, not for those modifying it.

## Command Type

`doc-code-usage`

## Core Directive

**YOUR ONLY JOB**: Document how to use the code as it exists today.

**DO NOT:**
- Document internal implementation details
- Explain code architecture or design patterns
- Suggest improvements or changes
- Document private methods or internal APIs
- Explain how to modify or extend the codebase

**ONLY:**
- Document public APIs
- Show how to install and import
- Provide usage examples
- Document command-line interfaces
- Explain configuration options
- Document input/output formats

## Input

You will receive a request file containing:
- Path to the codebase to document
- Optional: Type of interface (library, CLI, API)
- Optional: Target audience (beginner, advanced)

## What to Document

### 1. Public APIs
- All public classes, functions, and methods
- Function signatures with parameter types
- Return types and values
- Exceptions that may be raised
- Usage examples for each major API

### 2. Command-Line Interfaces
- All CLI commands and subcommands
- Flags, options, and arguments
- Input/output formats
- Usage examples
- Common workflows

### 3. Configuration
- Configuration files and formats
- Environment variables
- Default values
- Required vs optional settings
- Configuration examples

### 4. Entry Points
- Installation instructions
- Import statements
- Main entry points for different use cases
- Quick start guide
- First-run setup

### 5. Data Formats
- Input data structures and schemas
- Output data structures and schemas
- File formats (if applicable)
- Data validation rules
- Example data

### 6. Error Handling
- Common errors users might encounter
- Error messages and their meanings
- Exception types that may be raised
- How to handle errors
- Troubleshooting guide

## Research Process

1. **Identify Entry Points**
   - Scan for main() functions
   - Look for CLI definitions
   - Find package exports
   - Check setup.py, package.json, etc.

2. **Map Public APIs**
   - Find all public-facing modules
   - Identify public classes and functions
   - Distinguish public from private/internal
   - Check for docstrings and type hints

3. **Extract Signatures**
   - Document all parameters with types
   - Document return values
   - Note any decorators
   - Capture default values

4. **Find Examples**
   - Look in README files
   - Check documentation folders
   - Examine test files for usage patterns
   - Find example directories
   - Check docstrings for examples

5. **Document Configuration**
   - Find config files
   - Identify environment variables
   - Document all options
   - Note defaults and requirements

## Documentation Structure

Create a markdown file with this structure:

```markdown
# [Project Name] - Usage Documentation

## Overview
Brief description of what this code does and who should use it.
Include: Purpose, key features, target users.

## Installation

### Requirements
- [Language/runtime version]
- [Required dependencies]
- [System requirements]

### Install via [Package Manager]
```bash
[installation command]
```

### Install from Source
```bash
[clone and install commands]
```

## Quick Start

[Minimal example to get started - 5-10 lines]

```[language]
# Simple example that demonstrates basic usage
```

## API Reference

### Module: [module_name]

#### Class: [ClassName]

Brief description of what this class does.

**Constructor**
```[language]
ClassName(param1: type, param2: type = default)
```

**Parameters:**
- `param1` (type): Description
- `param2` (type, optional): Description. Defaults to `default`.

**Example:**
```[language]
# Example usage
```

#### Method: [method_name]

Brief description of what this method does.

```[language]
method_name(param1: type, param2: type) -> return_type
```

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Returns:**
- `return_type`: Description of return value

**Raises:**
- `ExceptionType`: When this exception is raised

**Example:**
```[language]
# Example usage
```

### Function: [function_name]

Brief description of what this function does.

```[language]
function_name(param1: type, param2: type = default) -> return_type
```

**Parameters:**
- `param1` (type): Description
- `param2` (type, optional): Description. Defaults to `default`.

**Returns:**
- `return_type`: Description

**Example:**
```[language]
# Example usage
```

## Command-Line Interface

(Include this section if the code has a CLI)

### Command: [command_name]

Brief description of what this command does.

**Usage:**
```bash
command_name [options] <arguments>
```

**Options:**
- `-f, --flag`: Description
- `-o, --option <value>`: Description

**Arguments:**
- `<arg>`: Description (required)
- `[arg]`: Description (optional)

**Examples:**
```bash
# Example 1: Basic usage
command_name file.txt

# Example 2: With options
command_name --flag --option value file.txt
```

## Configuration

### Configuration File

[Project Name] can be configured using `config.[ext]`:

```[format]
# Example configuration
option1: value1
option2: value2
```

**Options:**
- `option1`: Description. Default: `default1`
- `option2`: Description. Default: `default2`

### Environment Variables

- `ENV_VAR_NAME`: Description. Default: `default`
- `ANOTHER_VAR`: Description. Required if [condition]

## Data Formats

### Input Format

Description of expected input format.

**Example:**
```[format]
{
  "field1": "value1",
  "field2": "value2"
}
```

### Output Format

Description of output format.

**Example:**
```[format]
{
  "result": "value",
  "status": "success"
}
```

## Error Reference

### Common Errors

**Error: [Error Message]**
- **Cause**: Why this error occurs
- **Solution**: How to fix it

**Exception: [ExceptionType]**
- **When**: When this exception is raised
- **Handling**: How to catch and handle it
- **Example**:
```[language]
try:
    # code that might raise exception
except ExceptionType as e:
    # handle error
```

## Examples

### Example 1: [Use Case Name]

Description of this use case.

```[language]
# Complete working example
```

### Example 2: [Use Case Name]

Description of this use case.

```[language]
# Complete working example
```

## Advanced Usage

(Optional section for complex features)

### [Advanced Feature Name]

Description and examples of advanced usage.

## Troubleshooting

**Problem**: [Common problem]
**Solution**: [How to solve it]

**Problem**: [Another problem]
**Solution**: [How to solve it]

## API Stability

(If relevant)
- Note which APIs are stable vs experimental
- Deprecation warnings
- Version compatibility

## Further Resources

- Documentation: [link]
- Examples: [link]
- Community: [link]
```

## Output Files

1. **Save Documentation**
   - Filename: `agent-io/docs/[project-name]-usage.md`
   - Create `agent-io/docs/` directory if it doesn't exist
   - Use kebab-case for project name

2. **Reference in JSON**
   - Add to `artifacts.documentation_filename`
   - Add to `files.created` array

## JSON Output Requirements

**Required Fields:**
- `command_type`: "doc-code-usage"
- `status`: "complete", "user_query", or "error"
- `session_summary`: Brief summary of documentation created
- `files.created`: Array with the documentation file
- `artifacts.documentation_filename`: Path to documentation
- `comments`: Important observations and notes

**Optional Fields:**
- `metrics.files_analyzed`: Number of files examined
- Number of public APIs documented

**Example Comments:**
- "Documented 47 public functions across 8 modules"
- "Found comprehensive CLI with 12 commands"
- "Note: Some functions have minimal docstrings - documented based on code analysis"
- "Configuration supports both .yaml and .json formats"
- "Library supports Python 3.8+"

## Quality Checklist

Before marking complete, verify:
- âœ… All public APIs documented with signatures and examples
- âœ… All CLI commands documented with usage examples
- âœ… Configuration options clearly explained
- âœ… Quick start guide enables first use in < 5 minutes
- âœ… Error reference covers common issues
- âœ… Documentation is organized and easy to navigate
- âœ… No internal/private implementation details leaked
- âœ… Examples are practical and copy-pasteable
- âœ… Installation instructions are clear
- âœ… Parameter types and return types documented
