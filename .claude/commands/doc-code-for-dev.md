# Command: doc-code-for-dev

## Purpose

Create comprehensive architecture documentation that enables developers (and AI agents) to understand, modify, and extend a codebase. This is internal documentation about HOW the code works, not how to USE it.

## Command Type

`doc-code-for-dev`

## Core Directive

**YOUR ONLY JOB**: Document and explain the codebase as it exists today.

**DO NOT:**
- Suggest improvements or changes
- Perform root cause analysis
- Propose future enhancements
- Critique the implementation
- Recommend refactoring or optimization
- Identify problems

**ONLY:**
- Describe what exists
- Explain where components are located
- Show how systems work
- Document how components interact
- Map the technical architecture

## Input

You will receive a request file containing:
- Path to the codebase to document
- Optional: Specific areas to focus on
- Optional: Known entry points or key files

## What to Document

### 1. Project Structure
- Directory organization and purpose
- File naming conventions
- Module relationships and dependencies
- Configuration file locations

### 2. Architectural Patterns
- Overall design patterns (MVC, microservices, etc.)
- Key abstractions and their purposes
- Separation of concerns
- Layering strategy

### 3. Component Relationships
- How modules interact
- Data flow between components
- Dependency graphs
- Service boundaries

### 4. Data Models
- Core data structures and classes
- Database schemas (if applicable)
- State management approach
- Data persistence strategy

### 5. Key Algorithms and Logic
- Where business logic lives
- Complex algorithms and their purposes
- Decision points and control flow
- Critical code paths

### 6. Extension Points
- Plugin systems or hooks
- Abstract classes meant to be extended
- Configuration-driven behavior
- Where to add new features

### 7. Internal APIs
- Private/internal interfaces between modules
- Service contracts
- Communication protocols
- Message formats

### 8. Development Setup
- Build system and tools
- Testing framework
- Development dependencies
- How to run locally

## Research Process

1. **Map the Structure**
   - Generate directory tree
   - Identify purpose of each major directory
   - Locate configuration files
   - Find entry points (main files, index files)

2. **Identify Core Components**
   - What are the main modules/packages?
   - What is each component responsible for?
   - What are key classes and functions?
   - How are components named?

3. **Trace Data Flow**
   - Follow data from entry point to storage
   - Identify transformations
   - Map processing stages
   - Document state changes

4. **Understand Patterns**
   - What design patterns are used?
   - How is state managed?
   - How are errors handled?
   - What conventions are followed?

5. **Find Extension Mechanisms**
   - Where can new features be added?
   - What patterns should be followed?
   - What interfaces need implementation?
   - How are plugins/extensions loaded?

6. **Document Build/Test**
   - How to set up development environment
   - How to run tests
   - How to build/compile
   - What tools are required

## Documentation Structure

Create a markdown file with this structure:

```markdown
# [Project Name] - Architecture Documentation

## Overview
High-level description of system architecture and design philosophy.
Include: What this system does, key technologies, architectural approach.

## Project Structure
```
project/
├── module1/          # Purpose: [description]
│   ├── submodule/    # Purpose: [description]
│   └── core.py       # [description]
├── module2/          # Purpose: [description]
└── tests/            # Purpose: [description]
```

## Core Components

### Component: [Name]
- **Location**: `path/to/component`
- **Purpose**: [What this component does]
- **Key Classes/Functions**:
  - `ClassName`: [Description and role]
  - `function_name()`: [Description and role]
- **Dependencies**: [What it depends on]
- **Used By**: [What depends on it]

[Repeat for each major component]

## Architecture Patterns

### Pattern: [Name]
- **Where Used**: [Locations in codebase]
- **Purpose**: [Why this pattern is used]
- **Implementation**: [How it's implemented]
- **Key Classes**: [Classes involved]

## Data Flow

### Flow: [Name]
```
Entry Point → Component A → Component B → Storage
```
- **Description**: [Detailed explanation]
- **Transformations**: [What happens at each stage]
- **Error Handling**: [How errors are managed]

## Data Models

### Model: [Name]
- **Location**: `path/to/model`
- **Purpose**: [What this represents]
- **Key Fields**:
  - `field_name` (type): [Description]
- **Relationships**: [Relations to other models]
- **Persistence**: [How/where stored]

## Module Dependencies

```
module1
  ├─ depends on: module2, module3
  └─ used by: module4

module2
  ├─ depends on: module3
  └─ used by: module1, module5
```

## Key Algorithms

### Algorithm: [Name]
- **Location**: `path/to/file:line_number`
- **Purpose**: [What problem it solves]
- **Input**: [What it takes]
- **Output**: [What it produces]
- **Complexity**: [Time/space if relevant]
- **Critical Details**: [Important notes]

## Extension Points

### Extension Point: [Name]
- **How to Extend**: [Instructions]
- **Required Interface**: [What must be implemented]
- **Examples**: [Existing implementations]
- **Integration**: [How extensions are registered]

## State Management
- **Where State Lives**: [Description]
- **State Lifecycle**: [Creation, modification, destruction]
- **Concurrency**: [How concurrent access handled]
- **Persistence**: [How state is saved/loaded]

## Error Handling Strategy
- **Exception Hierarchy**: [Custom exceptions]
- **Error Propagation**: [How errors bubble up]
- **Recovery Mechanisms**: [How failures handled]
- **Logging**: [Where errors are logged]

## Testing Architecture
- **Test Organization**: [How tests structured]
- **Test Types**: [Unit, integration, e2e]
- **Fixtures and Mocks**: [Common utilities]
- **Running Tests**: [Commands to run tests]

## Development Setup

### Prerequisites
- [Required tools and versions]
- [System dependencies]

### Setup Steps
1. [Clone and install]
2. [Configuration]
3. [Database setup if applicable]
4. [Verification]

### Build System
- [Build commands]
- [Artifacts produced]
- [Build configuration]

## Important Conventions
- [Naming conventions]
- [Code organization patterns]
- [Documentation standards]

## Critical Files
- `file.py`: [Why important]
- `config.yaml`: [Configuration structure]
- `schema.sql`: [Database schema]

## Glossary
- **Term**: [Definition in context of this codebase]
```

## Output Files

1. **Save Documentation**
   - Filename: `agent-io/docs/[project-name]-architecture.md`
   - Create `agent-io/docs/` directory if it doesn't exist
   - Use kebab-case for project name

2. **Reference in JSON**
   - Add to `artifacts.documentation_filename`
   - Add to `files.created` array

## JSON Output Requirements

**Required Fields:**
- `command_type`: "doc-code-for-dev"
- `status`: "complete", "user_query", or "error"
- `session_summary`: Brief summary of documentation created
- `files.created`: Array with the documentation file
- `artifacts.documentation_filename`: Path to documentation
- `comments`: Important observations and notes

**Optional Fields:**
- `metrics.files_analyzed`: Number of files examined
- `metrics.lines_of_code`: Total LOC in codebase

**Example Comments:**
- "Analyzed 147 files across 12 modules"
- "Identified MVC pattern throughout web layer"
- "Found plugin system using abstract base classes"
- "Database uses SQLAlchemy ORM with 23 models"
- "Note: Some circular dependencies between auth and user modules"

## Quality Checklist

Before marking complete, verify:
- âœ… Complete project structure mapped with purposes
- âœ… All major components documented with responsibilities
- âœ… Architectural patterns identified and explained
- âœ… Data flow through system clearly traced
- âœ… Module dependencies visualized
- âœ… Extension points identified with examples
- âœ… Development setup instructions provided
- âœ… Key algorithms documented with locations
- âœ… State management strategy explained
- âœ… A developer can start contributing in < 30 minutes
- âœ… Documentation is in markdown format
- âœ… No suggestions for improvements (only documentation)
