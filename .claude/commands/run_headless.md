# Command: run_headless

## Purpose

Execute Claude Code commands in autonomous headless mode with comprehensive JSON output. This command enables Claude to run structured tasks without interactive terminal access, producing complete documentation of all actions taken.

## Overview

You are running in headless mode to execute structured commands. You will receive input that may include:
1. **Claude Commands**: One or more commands to be executed (e.g., create-prd, generate-tasks, doc-code-for-dev)
2. **User Prompt**: Description of the work to be done, which may:
   - Reference an existing PRD by name (e.g., "user-profile-editing")
   - Contain a complete new feature description that should be saved as a PRD
3. **PRD Reference Handling**: When a PRD name is referenced:
   - Look for `agent-io/prds/<prd-name>/humanprompt.md`
   - Look for `agent-io/prds/<prd-name>/aiprompt.md`
   - Look for `agent-io/prds/<prd-name>/fullprompt.md` if present
   - These files provide the detailed context for the work
4. **PRD Storage**: When a user prompt is provided without a PRD name:
   - Analyze the prompt to create a descriptive PRD name (use kebab-case)
   - Save the user prompt to `agent-io/prds/<prd-name>/humanprompt.md`
   - Document the PRD name in your output for future reference

Your job is to execute the command according to the instructions and produce a comprehensive JSON output file.

## Critical Principles for Headless Operation

### User Cannot See Terminal
- The user has NO access to your terminal output
- ALL relevant information MUST go in the JSON output file
- Do not assume the user saw anything you did
- Every action, decision, and result must be documented in `claude-output.json`

### Autonomous Execution
- Execute tasks independently without asking for permission
- Only ask questions when genuinely ambiguous or missing critical information
- Make reasonable assumptions and document them in comments
- Complete as much work as possible before requesting user input
- Work proactively to accomplish the full scope of the command

## Command Execution Flow

Follow this process for all headless executions:

### 1. Parse Input and Handle PRDs
- Parse the input to identify:
  - Which Claude commands to execute
  - The user prompt describing the work
  - Whether a PRD name is referenced
- **If a PRD name is referenced**:
  - Read the PRD files from `agent-io/prds/<prd-name>/`
  - Use humanprompt.md, aiprompt.md, and fullprompt.md (if available) as context
- **If user prompt provided without PRD name**:
  - Create a descriptive PRD name based on the prompt content (use kebab-case)
  - Create directory `agent-io/prds/<prd-name>/`
  - Save the user prompt to `agent-io/prds/<prd-name>/humanprompt.md`
  - Document the PRD name in your output
- If resuming from a previous session, review the parent session context

### 2. Execute Command
- Follow the instructions in the command file
- Apply the principles from the system prompt
- Work autonomously as much as possible
- Track all actions as you work

### 3. Track Everything
- Track all actions in memory as you work
- Build up the JSON output structure continuously
- Document files created, modified, or deleted
- Record task progress and status changes
- Capture all decisions and assumptions

### 4. Handle User Queries (if needed)
- If you need user input, prepare clear questions
- Format questions according to the JSON schema
- Save complete context for resumption
- Set status to "user_query"
- Ensure session_id is included for continuity

### 5. Write JSON Output
- Write the complete JSON to `claude-output.json`
- Ensure all required fields are present
- Validate JSON structure before writing
- Include comprehensive session_summary

## Example Headless Session

### Example 1: New PRD Creation

**Input:**
- Commands: `["create-prd"]`
- User prompt: "Add user profile editing feature with avatar upload and bio section"
- PRD name: Not provided

**Execution Process:**
1. Parse input - no PRD name provided, so create one
2. Generate PRD name: "user-profile-editing"
3. Create directory: `agent-io/prds/user-profile-editing/`
4. Save user prompt to `agent-io/prds/user-profile-editing/humanprompt.md`
5. Ask clarifying questions (if needed) by setting status to "user_query"
6. Generate enhanced PRD content
7. Save to `agent-io/prds/user-profile-editing/fullprompt.md`
8. Create comprehensive JSON output with:
   - Status: "complete"
   - Session ID: (provided by Claude Code automatically)
   - Parent session ID: null (this is a new session)
   - Session summary explaining what was accomplished
   - Files created: humanprompt.md, fullprompt.md, data.json
   - PRD name documented in artifacts
   - Any relevant comments, assumptions, or observations

### Example 2: Using Existing PRD

**Input:**
- Commands: `["generate-tasks"]`
- User prompt: "Generate implementation tasks for user-profile-editing"
- PRD name: "user-profile-editing" (referenced in prompt)

**Execution Process:**
1. Parse input - PRD name "user-profile-editing" identified
2. Read `agent-io/prds/user-profile-editing/humanprompt.md`
3. Read `agent-io/prds/user-profile-editing/aiprompt.md` (if exists)
4. Read `agent-io/prds/user-profile-editing/fullprompt.md` (if exists)
5. Use PRD context to generate detailed task list
6. Save tasks to `agent-io/prds/user-profile-editing/data.json`
7. Create comprehensive JSON output with task list and references

### The user workflow:
- User reads `claude-output.json` to understand everything you did
- User can review created files based on paths in JSON
- User can resume work by creating new session with parent_session_id

### If clarification is needed:
- Set status to "user_query"
- Include session_id in output
- Add queries_for_user array with clear, specific questions
- When user provides answers in a new session, that session will have parent_session_id pointing to this session
- Claude Code uses the session chain to maintain full context

## Output Requirements

Always output to: `claude-output.json` in the working directory

The JSON must include:
- All required fields for the command type and status
- Complete file tracking (created, modified, deleted)
- Task progress if applicable
- Session information for continuity
- Comments explaining decisions and assumptions
- Any errors or warnings encountered

## Best Practices for Headless Execution

- **Be Specific**: Include file paths, line numbers, function names
- **Be Complete**: Don't leave out details assuming the user knows them
- **Be Clear**: Write for someone who wasn't watching you work
- **Be Actionable**: Comments should help the user understand next steps
- **Be Honest**: If something is incomplete or uncertain, say so
- **Be Thorough**: Document every action taken, no matter how small
- **Be Proactive**: Complete as much work as possible before asking questions
