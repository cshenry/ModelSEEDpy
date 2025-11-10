# Command: create-prd

## Purpose

Generate a comprehensive Product Requirements Document (PRD) from a user's feature request. The PRD should be clear, actionable, and suitable for a junior developer to understand and implement.

## Command Type

`create-prd`

## Input

You will receive a request file containing:
- Initial feature description or request
- Any existing context about the product/system
- Target users or stakeholders

## Process

### Phase 1: Clarification

1. **Analyze the Request**
   - Read the feature request carefully
   - Identify what information is provided
   - Identify what critical information is missing

2. **Ask Clarifying Questions** (if needed)
   - Ask about problem/goal: "What problem does this feature solve?"
   - Ask about target users: "Who is the primary user?"
   - Ask about core functionality: "What are the key actions users should perform?"
   - Ask for user stories: "As a [user], I want to [action] so that [benefit]"
   - Ask about acceptance criteria: "How will we know this is successfully implemented?"
   - Ask about scope: "What should this feature NOT do?"
   - Ask about data requirements: "What data needs to be displayed or manipulated?"
   - Ask about design/UI: "Are there mockups or UI guidelines?"
   - Ask about edge cases: "What potential error conditions should we consider?"
   
   **Important**: Only ask questions where the answer is not already clear from the request. Make reasonable assumptions and document them in comments.

### Phase 2: PRD Generation

3. **Generate PRD Markdown**
   - Create a comprehensive PRD following the structure below
   - Write for a junior developer audience
   - Be explicit and unambiguous
   - Avoid jargon where possible

4. **Determine PRD Directory Name**
   - Convert feature name to kebab-case
   - Example: "User Profile Editing" → "user-profile-editing"

5. **Save PRD Files**
   - Create directory: `agent-io/prds/<prd-name>/`
   - Save user's original request to: `agent-io/prds/<prd-name>/humanprompt.md`
   - Save AI-enhanced description to: `agent-io/prds/<prd-name>/aiprompt.md` (if applicable)
   - Save complete PRD to: `agent-io/prds/<prd-name>/fullprompt.md`
   - Create JSON tracking file: `agent-io/prds/<prd-name>/<prd-name>.json`
   - Document the filename in JSON output's `artifacts.prd_filename`

## PRD Structure

Your PRD markdown file must include these sections:

```markdown
# PRD: [Feature Name]

## Introduction/Overview
Brief description of the feature and the problem it solves. State the primary goal.

## Goals
List specific, measurable objectives for this feature:
1. [Goal 1]
2. [Goal 2]
3. [Goal 3]

## User Stories
Detail user narratives describing feature usage and benefits:

**As a** [type of user]
**I want to** [perform some action]
**So that** [I can achieve some benefit]

(Include 3-5 user stories)

## Functional Requirements

List specific functionalities the feature must have. Use clear, concise language. Number each requirement.

1. The system must [specific requirement]
2. The system must [specific requirement]
3. Users must be able to [specific action]
4. The feature must [specific behavior]

## Non-Goals (Out of Scope)

Clearly state what this feature will NOT include:
- [Non-goal 1]
- [Non-goal 2]
- [Non-goal 3]

## Design Considerations

(Optional - include if relevant)
- Link to mockups or design files
- Describe UI/UX requirements
- Mention relevant components or design system elements
- Note accessibility requirements

## Technical Considerations

(Optional - include if relevant)
- Known technical constraints
- Dependencies on other systems or modules
- Performance requirements
- Security considerations
- Scalability concerns

## Success Metrics

How will the success of this feature be measured?
- [Metric 1: e.g., "Increase user engagement by 10%"]
- [Metric 2: e.g., "Reduce support tickets related to X by 25%"]
- [Metric 3: e.g., "90% of users complete the flow without errors"]

## Open Questions

List any remaining questions or areas needing further clarification:
1. [Question 1]
2. [Question 2]
```

## Tasks to Track

Create tasks in the JSON output:

```
1.0 Clarify requirements (if questions needed)
2.0 Generate PRD content
3.0 Save PRD file
```

Mark tasks as completed as you progress.

## JSON Output Requirements

Your JSON output must include:

**Required Fields:**
- `command_type`: "create-prd"
- `status`: "complete", "user_query", or "error"
- `session_summary`: Brief summary of PRD creation
- `files.created`: Array with the PRD file entry
- `artifacts.prd_filename`: Path to the PRD file
- `comments`: Array of notes (e.g., assumptions made, important decisions)

**For user_query status:**
- `queries_for_user`: Your clarifying questions
- `context`: Save the initial request and any partial work

**Example Comments:**
- "Assumed feature is for logged-in users only"
- "PRD written for web interface; mobile considerations noted as future enhancement"
- "No existing user authentication system mentioned; included as technical dependency"

## Quality Checklist

Before marking complete, verify:
- âœ… PRD includes all required sections
- âœ… Requirements are specific and measurable
- âœ… User stories follow the standard format
- âœ… Non-goals are clearly stated
- âœ… PRD is understandable by a junior developer
- âœ… File saved to correct location with correct naming
- âœ… JSON output includes all required fields
- âœ… All assumptions documented in comments
