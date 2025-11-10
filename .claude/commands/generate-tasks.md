# Command: generate-tasks

## Purpose

Generate a detailed, hierarchical task list from an existing PRD. Tasks should guide a developer through implementation with clear, actionable steps.

## Command Type

`generate-tasks`

## Input

You will receive a request file containing:
- Reference to a specific PRD file (path or ID)
- Any additional context or constraints

## Process

### Phase 1: Analysis

1. **Read the PRD**
   - Locate and read the specified PRD file
   - Understand functional requirements
   - Identify user stories and acceptance criteria
   - Note technical considerations

2. **Assess Current Codebase**
   - Review existing code structure
   - Identify relevant existing components
   - Understand architectural patterns
   - Note relevant files that may need modification
   - Identify utilities and libraries already in use

3. **Identify Relevant Files**
   - List files that will need to be created
   - List files that will need to be modified
   - Include corresponding test files
   - Note the purpose of each file

### Phase 2: Generate Parent Tasks

4. **Create High-Level Tasks**
   - Break the PRD into 4-7 major work streams
   - Each parent task should be a significant milestone
   - Examples:
     - "Set up data models and database schema"
     - "Implement backend API endpoints"
     - "Create frontend components"
     - "Add form validation and error handling"
     - "Implement tests"
     - "Add documentation"

5. **Present to User**
   - Generate the high-level tasks in the JSON output
   - Set status to "user_query"
   - Ask: "I have generated the high-level tasks. Ready to generate sub-tasks? Respond with 'Go' to proceed."
   - Save context with the parent tasks

### Phase 3: Generate Sub-Tasks

6. **Wait for User Confirmation**
   - Only proceed after user responds with "Go" or equivalent

7. **Break Down Each Parent Task**
   - Create 2-8 sub-tasks for each parent task
   - Sub-tasks should be:
     - Specific and actionable
     - Able to be completed in 15-60 minutes
     - Ordered logically (dependencies first)
     - Clear enough for a junior developer
   
   **Sub-task Quality Guidelines:**
   - Start with action verbs: "Create", "Implement", "Add", "Update", "Test"
   - Include what and where: "Create UserProfile component in components/profile/"
   - Reference existing patterns: "Following the pattern used in AuthForm component"
   - Note dependencies: "After completing 1.2, update..."

8. **Update Task List**
   - Add all sub-tasks to the JSON output
   - Link sub-tasks to parent tasks using parent_task_id
   - All tasks should have status "pending"

## Task ID Format

- **Parent tasks**: X.0 (1.0, 2.0, 3.0, etc.)
- **Sub-tasks**: X.Y (1.1, 1.2, 1.3, etc.)
- Maximum depth: 2 levels (no sub-sub-tasks)

## Task Structure in JSON

```json
{
  "task_id": "1.0",
  "description": "Set up data models and database schema",
  "status": "pending",
  "parent_task_id": null,
  "notes": ""
},
{
  "task_id": "1.1",
  "description": "Create User model with fields: name, email, avatar_url, bio",
  "status": "pending",
  "parent_task_id": "1.0",
  "notes": "Reference existing models in models/ directory"
}
```

## Relevant Files Documentation

In your `comments` array, include a section listing relevant files:

```
"RELEVANT FILES:",
"- src/models/User.ts - Create new User model",
"- src/models/User.test.ts - Unit tests for User model",
"- src/api/users.ts - API endpoints for user operations",
"- src/api/users.test.ts - API endpoint tests",
"- src/components/UserProfile.tsx - New profile display component",
"- src/components/UserProfile.test.tsx - Component tests"
```

## JSON Output Requirements

**Required Fields:**
- `command_type`: "generate-tasks"
- `status`: "complete" (after sub-tasks) or "user_query" (after parent tasks)
- `session_summary`: Brief summary of task generation
- `tasks`: Array of all tasks (parent and sub-tasks after completion)
- `comments`: Include relevant files list and important notes

**For user_query status (after Phase 2):**
- `tasks`: Array with only parent tasks
- `queries_for_user`: Ask user to confirm before generating sub-tasks
- `context`: Save PRD analysis and parent tasks

**Example Comments:**
- "Generated 5 parent tasks and 27 sub-tasks total"
- "Identified 12 files that need creation or modification"
- "Tasks assume use of existing authentication middleware"
- "Test tasks follow Jest/React Testing Library patterns used in codebase"

## Quality Checklist

Before marking complete, verify:
- âœ… All functional requirements from PRD are covered by tasks
- âœ… Tasks are ordered logically with dependencies first
- âœ… Each task is specific and actionable
- âœ… Parent tasks represent major milestones
- âœ… Sub-tasks can each be completed in reasonable time
- âœ… Testing tasks are included
- âœ… Task descriptions reference existing patterns where relevant
- âœ… All tasks use proper ID format
- âœ… Relevant files are identified with purposes
- âœ… JSON output includes all required fields

## Example Task Breakdown

**Parent Task:**
```json
{
  "task_id": "2.0",
  "description": "Implement backend API endpoints",
  "status": "pending",
  "parent_task_id": null
}
```

**Sub-tasks:**
```json
{
  "task_id": "2.1",
  "description": "Create GET /api/users/:id endpoint to retrieve user profile",
  "status": "pending",
  "parent_task_id": "2.0",
  "notes": "Return user object with all fields from User model"
},
{
  "task_id": "2.2",
  "description": "Create PUT /api/users/:id endpoint to update user profile",
  "status": "pending",
  "parent_task_id": "2.0",
  "notes": "Validate input, check authorization, update only allowed fields"
},
{
  "task_id": "2.3",
  "description": "Add authentication middleware to protect user endpoints",
  "status": "pending",
  "parent_task_id": "2.0",
  "notes": "Use existing auth middleware pattern from api/auth.ts"
}
```
