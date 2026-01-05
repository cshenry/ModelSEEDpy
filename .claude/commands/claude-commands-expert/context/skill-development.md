# Skill/Command Development Guide

## Overview

This repository manages two types of Claude Code extensions:

1. **Commands** - Task-oriented instructions (create-prd, free-agent, etc.)
2. **Expert Skills** - Domain-specific knowledge assistants (msmodelutl-expert, etc.)

## Command vs. Skill

| Aspect | Command | Expert Skill |
|--------|---------|--------------|
| Purpose | Execute a specific task | Answer questions, provide guidance |
| Input | Request JSON file | User question (natural language) |
| Output | JSON + artifacts | Conversational response |
| Invocation | `claude code headless --command` | `/skill-name <question>` |
| Examples | create-prd, generate-tasks | msmodelutl-expert |

## Creating a New Command

### Step 1: Create Command File

Create `commands/<command-name>.md`:

```markdown
# Command: <name>

## Purpose
Brief description of what this command does.

## Command Type
`<command-name>`

## Core Directive
You are a [role]. Your job is to [primary responsibility].

**YOUR JOB:**
- ✅ Task 1
- ✅ Task 2

**DO NOT:**
- ❌ Anti-pattern 1
- ❌ Anti-pattern 2

## Input
You will receive a request file containing:
- `field1`: Description
- `field2`: Description

## Process

### 1. First Step
Description of what to do.

### 2. Second Step
Description of what to do.

## Output Requirements
Describe what goes in the JSON output:
- Required fields
- Artifacts to create
- Files to document

## Quality Checklist
- ✅ Verification 1
- ✅ Verification 2
```

### Step 2: Add to Schema

Update `unified-output-schema.json`:

```json
"command_type": {
  "enum": [..., "your-new-command"]
}
```

### Step 3: Create Example

Add `examples/<command-name>-example.json`:

```json
{
  "request_type": "<command-name>",
  "description": "Example request",
  "context": {
    "relevant_field": "value"
  }
}
```

### Step 4: Deploy

```bash
claude-commands update
```

## Creating an Expert Skill

Expert skills provide domain expertise for answering questions.

### Step 1: Create Main Skill File

Create `commands/<skill-name>.md`:

```markdown
# <Domain> Expert

You are an expert on <domain>. You have deep knowledge of:

1. **Area 1** - Description
2. **Area 2** - Description
3. **Area 3** - Description

## Knowledge Loading

Before answering, read the relevant documentation:

**Always read:**
- `/path/to/main/documentation.md`

**When needed:**
- `/path/to/source/code.py`
- `/path/to/additional/docs.md`

## Quick Reference

### Key Concept 1
```python
# Code example
example_code()
```

### Key Concept 2
Brief explanation with example.

### Common Mistakes
1. **Mistake 1**: How to avoid it
2. **Mistake 2**: How to avoid it

## Guidelines for Responding

When helping users:

1. **Be specific** - Reference exact functions, parameters
2. **Show examples** - Provide working code
3. **Explain why** - Not just what, but why
4. **Warn about pitfalls** - Common mistakes

## Response Formats

### For API questions:
\```
### Method: `method_name(params)`

**Purpose:** Description

**Parameters:**
- `param1` (type): Description

**Returns:** Description

**Example:**
```python
code
```
\```

### For "how do I" questions:
\```
### Approach

Explanation

**Step 1:** Description
```python
code
```
\```

## User Request

$ARGUMENTS
```

### Step 2: Create Context Directory (Optional)

For skills with extensive reference material:

```
commands/
├── <skill-name>.md
└── <skill-name>/
    └── context/
        ├── api-summary.md      # Quick API reference
        ├── patterns.md         # Common usage patterns
        └── integration.md      # Integration with other systems
```

### Step 3: Choose Documentation Strategy

**Static Context (embedded in skill):**
- Faster response time
- Requires manual updates when source changes
- Best for: stable APIs, patterns that rarely change

**Dynamic Loading (read files on invocation):**
- Always current with source
- Slightly slower
- Best for: actively developed code

**Hybrid Approach (recommended):**
- Static: patterns, common mistakes, integration info
- Dynamic: full API reference, source code

Example hybrid:
```markdown
## Knowledge Loading

Before answering, read the current documentation:
- `/path/to/developer-guide.md`  # Dynamic - always current

## Quick Reference
[Embedded patterns and common info]  # Static - fast access
```

### Step 4: Deploy

```bash
claude-commands update
```

## Skill Invocation

After deployment, invoke with:

```
/skill-name How do I do X?
/skill-name What's the difference between A and B?
/skill-name Debug this code that's failing
```

## Best Practices

### For Commands
1. Follow the standard template structure
2. Reference SYSTEM-PROMPT.md for output format (don't duplicate)
3. Include clear quality checklist
4. Document expected request format
5. Provide examples

### For Expert Skills
1. Use dynamic loading for frequently-updated documentation
2. Embed common patterns for fast access
3. Include response format templates
4. Warn about common mistakes
5. Reference exact file paths

### For Both
1. Keep files in `commands/` directory (source)
2. Use `claude-commands update` to deploy
3. Test locally before pushing to all projects
4. Document in comments what each file does

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Command | `<action>-<target>.md` | `create-prd.md`, `doc-code-usage.md` |
| Expert Skill | `<domain>-expert.md` | `msmodelutl-expert.md` |
| Context Dir | `<skill-name>/context/` | `msmodelutl-expert/context/` |
