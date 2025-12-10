# Claude Code Universal Behavior Guidelines

## Overview

This document defines universal behavior guidelines for Claude Code across all commands and workflows. These principles apply regardless of the specific command being executed.

## Core Principles

### 1. Complete Documentation
- Document every action you take in the appropriate JSON file
- Track all files created, modified, or deleted
- Capture task progress and status changes
- Include all relevant context, decisions, and assumptions
- Never assume information is obvious - document everything explicitly

### 2. Consistent Output Format
- Always use the unified JSON schema (see below)
- Include all required fields for the relevant status
- Use optional fields as needed to provide additional context
- Validate JSON structure before completing work
- Ensure JSON is properly formatted and parseable

### 3. Session Management & Stateful Resumption
- Claude Code provides a session ID that maintains conversation context automatically
- Always include `session_id` in your output to enable seamless continuation
- When resuming work from a previous session, include `parent_session_id` to link sessions
- The session ID allows Claude Code to preserve full conversation history
- If you need user input, the context is preserved via session ID
- Include enough detail in `session_summary` to understand what was accomplished
- Don't make the user repeat information - session maintains context

### 4. Task Management
- Track all tasks in JSON output files (NOT in separate markdown files)
- Use hierarchical task IDs: "1.0" for parent, "1.1", "1.2" for children
- Track task status: pending, in_progress, completed, skipped, blocked
- Include task descriptions and any relevant notes
- Update task status as you work
- Document which tasks were completed in each session
- Note any tasks that were skipped and explain why
- When blocked, document the blocker clearly

### 5. Query Management
- Save all queries to users in the session JSON file
- When querying users, include:
  - Clear, specific questions
  - Query type (text, multiple_choice, boolean)
  - Any relevant context needed to answer
  - Query number for reference
- Save user responses in the same JSON file
- Link queries and responses with query numbers

## File Organization Structure

All agent-related documents and files must be organized under the `agent-io` directory:

```
agent-io/
├── prds/
│   └── <prd-name>/
│       ├── humanprompt.md      # Original user description of PRD
│       ├── fullprompt.md       # Fully fleshed PRD after completion
│       └── data.json           # JSON file documenting queries, responses, tasks, etc.
└── docs/
    └── <document-name>.md      # Architecture docs, usage docs, etc.
```

### File Organization Guidelines:
- **PRD Files**: Save to `agent-io/prds/<prd-name>/` directory
  - Each PRD gets its own directory named after the PRD
  - Use kebab-case for PRD names (e.g., "user-profile-editing", "payment-integration")
  - Directory contains: humanprompt.md, fullprompt.md, and data.json
  - The data.json file tracks all queries, responses, tasks, errors, and progress

- **PRD Storage and Reference**:
  - **When user provides a prompt without a PRD name**:
    - Analyze the prompt to create a descriptive PRD name (use kebab-case)
    - Create directory: `agent-io/prds/<prd-name>/`
    - Save the original user prompt to `agent-io/prds/<prd-name>/humanprompt.md`
    - Document the PRD name in your output for future reference
    - This allows users to reference this PRD by name in future sessions

  - **When user references an existing PRD by name**:
    - Look for the PRD directory: `agent-io/prds/<prd-name>/`
    - Read available PRD files in order of preference:
      1. `fullprompt.md` - the complete, finalized PRD (if available)
      2. `humanprompt.md` - the original user description
    - Use these files as context for the requested work
    - Update or create additional files as needed

  - **PRD Naming Best Practices**:
    - Use descriptive, feature-focused names
    - Keep names concise (2-4 words typically)
    - Use kebab-case consistently
    - Examples: "user-authentication", "payment-processing", "real-time-notifications"

- **Documentation Files**: Save to `agent-io/docs/`
  - Architecture documentation: `agent-io/docs/<project-name>-architecture.md`
  - Usage documentation: `agent-io/docs/<project-name>-usage.md`
  - Other documentation as appropriate

- **Code Files**: Save to appropriate project locations
  - Follow existing project structure
  - Document each file in the JSON tracking file
  - Include purpose and type for each file

### JSON Documentation Files:
- Every PRD must have an associated `data.json` file in its directory
- The data.json file documents:
  - Tasks and their status
  - Queries to users and their responses
  - Errors and problems encountered
  - Files created, modified, deleted
  - Session information and summaries
  - Comments and context

## Unified JSON Output Schema

Use this schema for all JSON output files:

```json
{
  "command_type": "string (create-prd | doc-code-for-dev | doc-code-usage | free-agent | generate-tasks)",
  "status": "string (complete | incomplete | user_query | error)",
  "session_id": "string - Claude Code session ID for this execution",
  "parent_session_id": "string | null - Session ID of previous session when resuming work",
  "session_summary": "string - Brief summary of what was accomplished",

  "tasks": [
    {
      "task_id": "string (e.g., '1.0', '1.1', '2.0')",
      "description": "string",
      "status": "string (pending | in_progress | completed | skipped | blocked)",
      "parent_task_id": "string | null",
      "notes": "string (optional details about completion/issues)"
    }
  ],

  "files": {
    "created": [
      {
        "path": "string (relative to working directory)",
        "purpose": "string (why this file was created)",
        "type": "string (markdown | code | config | documentation)"
      }
    ],
    "modified": [
      {
        "path": "string",
        "changes": "string (description of modifications)"
      }
    ],
    "deleted": [
      {
        "path": "string",
        "reason": "string"
      }
    ]
  },

  "artifacts": {
    "prd_filename": "string (for create-prd command)",
    "documentation_filename": "string (for doc-code commands)"
  },

  "queries_for_user": [
    {
      "query_number": "integer",
      "query": "string",
      "type": "string (text | multiple_choice | boolean)",
      "choices": [
        {
          "id": "string",
          "value": "string"
        }
      ],
      "response": "string | null - User's response (populated after query is answered)"
    }
  ],

  "comments": [
    "string - important notes, warnings, observations"
  ],

  "context": "string - optional supplementary state details. Session ID preserves full context automatically, so this field is only needed for additional implementation-specific state not captured in the conversation.",

  "metrics": {
    "duration_seconds": "number (optional)",
    "files_analyzed": "number (optional)",
    "lines_of_code": "number (optional)"
  },

  "errors": [
    {
      "message": "string",
      "type": "string",
      "fatal": "boolean"
    }
  ]
}
```

## Required Fields by Status

### Status: "complete"
- `command_type`, `status`, `session_id`, `session_summary`, `files`, `comments`
- `parent_session_id` (if this session continues work from a previous session)
- Plus any command-specific artifacts (prd_filename, documentation_filename, etc.)
- `tasks` array if the command involves tasks

### Status: "user_query"
- `command_type`, `status`, `session_id`, `session_summary`, `queries_for_user`
- `files` (for work done so far)
- `comments` (explaining why input is needed)
- `context` (optional - session_id maintains context automatically)
- Note: When user provides answers, they'll create a new session with `parent_session_id` linking back to this one

### Status: "incomplete"
- `command_type`, `status`, `session_id`, `session_summary`, `files`, `comments`
- Explanation in `comments` of what's incomplete and why
- `errors` array if errors caused incompleteness
- `context` (optional - session_id maintains context automatically)

### Status: "error"
- `command_type`, `status`, `session_id`, `session_summary`, `errors`, `comments`
- `files` (if any work was done before error)
- `context` (optional - for additional recovery details beyond what session maintains)

## Error Handling

When errors occur:
1. Set status to "error" (or "incomplete" if partial work succeeded)
2. Document the error in the `errors` array
3. Include what failed, why it failed, and potential fixes
4. Document any work that was completed before the error
5. Provide context for potential recovery
6. Save error details to the JSON file

## Code Development Guidelines

### Keep Code Simple
- Prefer simple, straightforward implementations over clever or complex solutions
- Write code that is easy to read and understand
- Avoid unnecessary abstractions or over-engineering
- Use clear, descriptive variable and function names
- Comment complex logic, but prefer self-documenting code

### Limit Complexity
- Minimize the number of classes and Python files
- Consolidate related functionality into fewer, well-organized modules
- Only create new files when there's a clear separation of concerns
- Avoid deep inheritance hierarchies
- Prefer composition over inheritance when appropriate

### Use JSON Schema Validation
- All JSON files must have corresponding JSON schemas
- Validate JSON files against their schemas
- Document the schema in comments or separate schema files
- Use schema validation to catch errors early
- Keep schemas simple and focused

### Keep Code Management Simple
- Don't use excessive linting rules
- Avoid complex documentation frameworks (like Sphinx) unless truly needed
- Use simple, standard tools (pytest for testing, basic linting)
- Focus on clear code over extensive tooling
- Documentation should be clear markdown files, not generated sites

## Best Practices

- **Be Specific**: Include file paths, line numbers, function names
- **Be Complete**: Don't leave out details assuming the user knows them
- **Be Clear**: Write for someone who wasn't watching you work
- **Be Actionable**: Comments should help the user understand next steps
- **Be Honest**: If something is incomplete or uncertain, say so
- **Be Consistent**: Follow the same patterns and conventions throughout
- **Be Thorough**: Test your work and verify it functions correctly
- **Be Organized**: Maintain clean directory structure and file organization

## Workflow Principles

### PRD Workflow
1. User provides initial feature description → saved as `humanprompt.md`
2. Complete PRD after workflow → saved as `fullprompt.md`
3. All progress tracked in `<prd-name>.json`

### Task Workflow
1. Break work into clear, manageable tasks
2. Use hierarchical task IDs (1.0, 1.1, 1.2, 2.0, etc.)
3. Update task status as work progresses
4. Document completed work and any blockers
5. Track everything in JSON file

### Documentation Workflow
1. Understand the codebase or feature thoroughly
2. Create clear, well-organized documentation
3. Save to appropriate location in `agent-io/docs/`
4. Track file creation and content in JSON output
5. Include examples and practical guidance

### Query Workflow
1. Only query when genuinely needed
2. Ask clear, specific questions
3. Save query to JSON file with query_number
4. Wait for user response
5. Save response to same JSON file
6. Continue work with provided information
