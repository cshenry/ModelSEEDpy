# ClaudeCommands CLI Reference

## Installation

```bash
cd /path/to/ClaudeCommands
pip install -e .
```

This installs the `claude-commands` command globally.

## Commands

### install

Install commands to user's home directory (~/.claude).

```bash
claude-commands install
```

**What it does:**
1. Creates `~/.claude/` directory if missing
2. Copies `SYSTEM-PROMPT.md` to `~/.claude/CLAUDE.md`
3. Copies all commands (including subdirectories) to `~/.claude/commands/`

**Prompts:**
- Asks before overwriting existing files

### addproject

Add a project to tracking and install commands.

```bash
claude-commands addproject ~/my-project
```

**What it does:**
1. Validates the directory exists
2. Adds to tracking list (`data/projects.json`)
3. Creates `.claude/` directory in project
4. Copies `SYSTEM-PROMPT.md` to `.claude/CLAUDE.md`
5. Copies all commands to `.claude/commands/`

**Name collision:**
- Projects are tracked by directory name
- Two projects with same directory name → error

### update

Update all tracked projects with latest commands.

```bash
claude-commands update
```

**What it does:**
1. Reads `data/projects.json`
2. For each project:
   - Verifies directory exists
   - Re-copies SYSTEM-PROMPT.md and commands
3. Reports success/warnings

### list

List all tracked projects.

```bash
claude-commands list
```

**Output:**
```
Tracked projects (3):

  ✓ my-project
      /Users/me/code/my-project

  ✓ another-app
      /Users/me/work/another-app

  ✗ deleted-project
      /Users/me/old/deleted-project
```

- ✓ = directory exists
- ✗ = directory missing

### removeproject

Remove a project from tracking.

```bash
claude-commands removeproject my-project
```

**What it does:**
1. Removes from `data/projects.json`
2. Does NOT delete `.claude/` directory

## Project Tracking

Projects tracked in `data/projects.json`:

```json
{
  "my-project": "/Users/me/code/my-project",
  "another-app": "/Users/me/work/another-app"
}
```

**Key points:**
- Project name = directory name (not path)
- Paths are absolute
- File is gitignored (local to machine)
- Don't edit manually - use CLI

## File Structure After Installation

### User-level (~/.claude/)
```
~/.claude/
├── CLAUDE.md                  # Universal system prompt
└── commands/
    ├── create-prd.md
    ├── free-agent.md
    ├── msmodelutl-expert.md
    └── msmodelutl-expert/
        └── context/
            ├── api-summary.md
            ├── patterns.md
            └── integration.md
```

### Project-level (project/.claude/)
```
my-project/
├── .claude/
│   ├── CLAUDE.md              # Universal system prompt
│   └── commands/
│       ├── create-prd.md
│       └── ...
└── (project files)
```

## Workflow Examples

### Initial Setup
```bash
# Clone repo
git clone <url> ClaudeCommands
cd ClaudeCommands

# Install CLI
pip install -e .

# Install to home directory
claude-commands install

# Add your projects
claude-commands addproject ~/project1
claude-commands addproject ~/project2
```

### After Modifying Commands
```bash
# Edit a command
vim commands/my-command.md

# Push to all projects
claude-commands update
```

### Adding New Project
```bash
claude-commands addproject ~/new-project
# Commands automatically installed
```

### Cleaning Up
```bash
# Remove project from tracking
claude-commands removeproject old-project

# Manually delete .claude if desired
rm -rf ~/old-project/.claude
```
