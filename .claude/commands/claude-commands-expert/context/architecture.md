# ClaudeCommands Architecture

## System Overview

ClaudeCommands is a framework for running Claude Code in headless mode with structured input/output and comprehensive documentation.

```
┌─────────────────────────────────────────────────────────────┐
│                   ClaudeCommands Repository                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ SYSTEM-      │  │  commands/   │  │  data/       │       │
│  │ PROMPT.md    │  │  *.md        │  │ projects.json│       │
│  │              │  │  */context/  │  │              │       │
│  │ (Universal   │  │ (Command &   │  │ (Tracked     │       │
│  │  instructions)│ │  Skill defs) │  │  projects)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                                  │
│         └────────┬────────┘                                  │
│                  │                                           │
│                  ▼                                           │
│         ┌──────────────┐                                     │
│         │claude_       │                                     │
│         │commands.py   │ ◄───── CLI Tool                     │
│         │              │                                     │
│         └──────────────┘                                     │
│                  │                                           │
│         ┌───────┴───────┐                                    │
│         │               │                                    │
│         ▼               ▼                                    │
│  ┌────────────┐  ┌────────────────┐                         │
│  │ ~/.claude/ │  │ project/.claude│                         │
│  │ (Global)   │  │ (Per-project)  │                         │
│  └────────────┘  └────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. SYSTEM-PROMPT.md

Universal instructions that apply to ALL command executions.

**Purpose:** Define the "rules of the game" - output format, documentation requirements, session management.

**Key sections:**
- Core Principles (documentation, output format, session management)
- Unified JSON Output Schema
- File Organization Structure
- Error Handling
- Best Practices

**Deployed as:** `CLAUDE.md` in target directories

### 2. Command Files (commands/*.md)

Define WHAT to do for specific command types.

**Categories:**
- **Task Commands:** create-prd, generate-tasks, free-agent
- **Documentation Commands:** doc-code-for-dev, doc-code-usage
- **Expert Skills:** msmodelutl-expert, claude-commands-expert

**Structure:**
```markdown
# Command/Skill Name
## Purpose
## Command Type (for commands) or Knowledge Loading (for skills)
## Process/Guidelines
## Output Requirements/Response Format
## Quality Checklist
```

### 3. CLI Tool (claude_commands.py)

Manages deployment of commands to projects.

**Key methods:**
```python
class ClaudeCommandsCLI:
    def install(self)           # → ~/.claude/
    def addproject(self, dir)   # → project/.claude/
    def update(self)            # → All tracked projects
    def list(self)              # → Show tracked projects
    def removeproject(self, name)
```

**Deployment logic:**
```python
def _copy_files_to_project(self, project_path):
    # 1. Copy SYSTEM-PROMPT.md → .claude/CLAUDE.md
    shutil.copy2(self.system_prompt, target_prompt)

    # 2. Copy entire commands/ → .claude/commands/
    shutil.copytree(self.commands_dir, target_commands)
    # (Preserves subdirectories for skills with context)
```

### 4. Project Tracking (data/projects.json)

Tracks which projects have commands installed.

```json
{
  "project-name": "/absolute/path/to/project",
  "another-project": "/path/to/another"
}
```

## Information Flow

### Headless Execution

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code CLI                           │
│                                                              │
│  Inputs:                                                     │
│  ├─ --system-prompt .claude/CLAUDE.md                       │
│  ├─ --command .claude/commands/<command>.md                 │
│  └─ --request request.json                                  │
│                                                              │
│  Execution:                                                  │
│  ├─ Reads and follows system prompt                         │
│  ├─ Follows command-specific instructions                   │
│  ├─ Creates artifacts (PRDs, docs, code)                    │
│  └─ Documents everything                                    │
│                                                              │
│  Outputs:                                                    │
│  ├─ claude-output.json (complete execution record)          │
│  └─ [artifacts] (files created by command)                  │
└─────────────────────────────────────────────────────────────┘
```

### Skill Invocation

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code IDE/CLI                       │
│                                                              │
│  User types: /skill-name How do I do X?                     │
│                                                              │
│  Claude:                                                     │
│  ├─ Loads .claude/commands/skill-name.md                    │
│  ├─ Follows Knowledge Loading instructions                  │
│  ├─ Reads referenced documentation (dynamic)                │
│  ├─ Uses Quick Reference (static)                           │
│  └─ Responds following Guidelines                           │
│                                                              │
│  Output: Conversational response with examples              │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Global Installation (~/.claude/)

Available in all projects (fallback when project-level not present).

```
~/.claude/
├── CLAUDE.md              # System prompt
└── commands/
    ├── command1.md
    ├── skill1.md
    └── skill1/
        └── context/
            └── *.md
```

### Project Installation (project/.claude/)

Project-specific, takes precedence over global.

```
my-project/
├── .claude/
│   ├── CLAUDE.md          # System prompt
│   └── commands/
│       └── ...
└── (project files)
```

### Precedence

1. Project-level (.claude/) - checked first
2. User-level (~/.claude/) - fallback

## Unified JSON Output Schema

All commands produce structured output:

```json
{
  "command_type": "string",
  "status": "complete|incomplete|user_query|error",
  "session_id": "string",
  "parent_session_id": "string|null",
  "session_summary": "string",

  "tasks": [
    {
      "task_id": "1.0",
      "description": "string",
      "status": "pending|in_progress|completed|skipped|blocked",
      "parent_task_id": "string|null",
      "notes": "string"
    }
  ],

  "files": {
    "created": [{"path": "", "purpose": "", "type": ""}],
    "modified": [{"path": "", "changes": ""}],
    "deleted": [{"path": "", "reason": ""}]
  },

  "artifacts": {
    "prd_filename": "string",
    "documentation_filename": "string"
  },

  "queries_for_user": [
    {
      "query_number": 1,
      "query": "string",
      "type": "text|multiple_choice|boolean",
      "choices": [{"id": "", "value": ""}],
      "response": "string|null"
    }
  ],

  "comments": ["string"],
  "context": "string",

  "errors": [
    {
      "message": "string",
      "type": "string",
      "fatal": true
    }
  ]
}
```

## Extension Points

### Adding New Commands

1. Create `commands/<name>.md` following template
2. Deploy with `claude-commands update`

### Adding Expert Skills

1. Create `commands/<name>.md` with Knowledge Loading
2. Optionally add `commands/<name>/context/` for reference docs
3. Deploy with `claude-commands update`

### Modifying System Behavior

1. Edit `SYSTEM-PROMPT.md`
2. Deploy with `claude-commands update`

## Design Principles

1. **Separation of Concerns**
   - Universal rules → SYSTEM-PROMPT.md
   - Command logic → commands/*.md
   - User requests → request.json

2. **Single Source of Truth**
   - One system prompt for all commands
   - One output schema for all outputs

3. **Complete Documentation**
   - Everything in JSON (user can't see terminal)
   - All file operations tracked
   - Session management for resumption

4. **Centralized Management**
   - Commands developed in one repo
   - Deployed to many projects
   - Single update pushes everywhere
