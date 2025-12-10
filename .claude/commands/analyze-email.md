# Command: analyze-email

## Purpose

Analyze an email document to extract key information, classify its importance, assign it to relevant projects, identify action items, and prepare a draft response. All analysis results are saved to a structured JSON file for downstream processing.

## Command Type

`analyze-email`

## Input

You will receive a request file containing:
- Email content (body, subject, sender, recipients)
- Email metadata (date, time, headers)
- User preferences (optional)

## Process

### Phase 1: Email Content Analysis

1. **Read Email Document**
   - Parse email subject, body, sender, recipients
   - Extract metadata (date, time, CC, BCC if available)
   - Identify attachments mentioned or referenced
   - Note email thread context if provided

2. **Extract Key Information**
   - Identify main topics and themes
   - Extract specific requests or questions
   - Note mentioned dates, deadlines, or time-sensitive information
   - Identify key stakeholders mentioned
   - Extract any reference numbers, project codes, or identifiers

### Phase 2: Classification

3. **Classify Email Importance**
   - Analyze content and metadata to classify as one of:
     - **unimportant**: Mass emails, newsletters, low-priority updates, spam-like content
     - **personal**: Personal correspondence, non-work related, social invitations
     - **professional**: Work-related, business correspondence, project updates, actionable items

   - Consider these factors:
     - Sender relationship (colleague, client, vendor, unknown)
     - Subject urgency indicators (urgent, ASAP, deadline, etc.)
     - Content type (FYI, action required, question, update)
     - Presence of deadlines or action items
     - Email thread importance

   - Provide classification confidence score (0.0-1.0)
   - Document classification reasoning in comments
   - Emails classified as unimportant should not proceed to further processing

### Phase 3: Task Extraction

4. **Identify Action Items**
   - Scan email for explicit tasks:
     - Action verbs (review, approve, send, create, update, etc.)
     - Questions requiring responses
     - Requests for information or deliverables
     - Meeting requests or scheduling needs

   - For each identified task:
     - Extract task description
     - Determine task type (respond, review, create, schedule, research, etc.)
     - Identify task owner (you, sender, other party)
     - Extract related context and requirements

5. **Determine Urgency and Deadlines**
   - Analyze for urgency indicators:
     - **Critical**: Explicit urgent markers, imminent deadlines (<24 hours), blocking issues
     - **High**: Near-term deadlines (1-3 days), important stakeholders, escalations
     - **Medium**: Standard deadlines (4-7 days), routine requests, normal priority
     - **Low**: Long-term deadlines (>7 days), FYI items, optional tasks

   - Extract deadlines:
     - Explicit dates ("by Friday", "before March 15")
     - Implicit timeframes ("ASAP", "end of week", "Q1")
     - Recurring deadlines ("weekly report", "monthly update")

   - Convert to standardized format (ISO 8601)
   - If no deadline specified, suggest reasonable deadline based on urgency

### Phase 4: Draft Response

6. **Analyze Response Requirements**
   - Determine if response is needed
   - Identify key points to address
   - Note any questions to answer
   - Consider required tone (formal, casual, apologetic, etc.)
   - Identify if response requires attachments or follow-up actions

7. **Generate Draft Response**
   - Create draft email response including:
     - Appropriate greeting based on sender relationship
     - Address all questions and requests
     - Confirm understanding of tasks and deadlines
     - Propose next steps if applicable
     - Professional closing

   - Match tone to original email and relationship
   - Keep response concise and actionable
   - Include placeholders for information you don't have ([YOUR_INPUT_NEEDED])
   - Add suggested subject line (Re: or continuation)

   - If no response needed, set draft_response to null and explain why

### Phase 5: Save Structured Output

8. **Prepare JSON Output File**
    - Determine sequence number for email analysis
    - Check `orchestrator/email-analysis/` directory for existing analyses
    - Use next sequential number (0001, 0002, 0003, etc.)
    - If directory doesn't exist, create it and start at 0001

9. **Save Analysis File**
    - Filename format: `orchestrator/email-analysis/[NNNN]-[YYYY-MM-DD]-[sender-name].json`
    - Example: `orchestrator/email-analysis/0042-2025-11-09-john-smith.json`
    - Use kebab-case for sender name
    - Document the filename in JSON output's `artifacts.analysis_filename`

## JSON Output Schema

The analysis JSON file must follow this structure:

```json
{
  "email_metadata": {
    "subject": "string",
    "sender": {
      "name": "string",
      "email": "string"
    },
    "recipients": {
      "to": ["email1@example.com", "email2@example.com"],
      "cc": ["email3@example.com"],
      "bcc": []
    },
    "date_received": "ISO 8601 datetime",
    "thread_id": "string or null",
    "message_id": "string or null",
    "attachments": ["filename1.pdf", "filename2.xlsx"]
  },

  "classification": {
    "category": "unimportant | personal | professional",
    "confidence": 0.95,
    "reasoning": "Detailed explanation of classification decision",
    "urgency_level": "critical | high | medium | low",
    "is_actionable": true,
    "sentiment": "positive | neutral | negative | mixed"
  },

  "tasks": [
    {
      "task_id": "T001",
      "description": "Review and approve the Q4 budget proposal",
      "task_type": "review | respond | create | schedule | research | approve | other",
      "owner": "self | sender | other",
      "urgency": "critical | high | medium | low",
      "deadline": {
        "date": "ISO 8601 datetime or null",
        "is_explicit": true,
        "original_text": "by end of week",
        "suggested_deadline": "ISO 8601 datetime - if no explicit deadline"
      },
      "status": "pending",
      "context": "Additional context from email about this task",
      "dependencies": ["T002"],
      "estimated_effort": "15 minutes | 1 hour | 2 hours | 1 day | 1 week"
    }
  ],

  "draft_response": {
    "should_respond": true,
    "response_urgency": "immediate | today | this_week | no_rush",
    "suggested_subject": "Re: Q4 Budget Review Request",
    "draft_body": "Full draft email body with appropriate greeting, content, and closing",
    "tone": "formal | professional | casual | friendly | apologetic",
    "requires_attachments": false,
    "placeholders": [
      {
        "placeholder": "[YOUR_INPUT_NEEDED]",
        "description": "Insert your availability for the meeting",
        "location": "paragraph 2"
      }
    ],
    "key_points_to_address": [
      "Confirm receipt of budget proposal",
      "Provide timeline for review",
      "Ask clarifying questions about line items"
    ]
  },

  "summary": {
    "one_line": "Budget approval request from Finance requiring review by Friday",
    "detailed": "Longer summary (2-3 sentences) of email content and required actions",
    "key_entities": [
      {"type": "person", "value": "Jane Doe"},
      {"type": "project", "value": "Q4 Budget Planning"},
      {"type": "document", "value": "Budget_Proposal_Q4.xlsx"},
      {"type": "date", "value": "2025-11-15"}
    ]
  },

  "analysis_metadata": {
    "analyzed_at": "ISO 8601 datetime",
    "analysis_version": "1.0",
    "model_used": "string",
    "processing_time_seconds": 3.45,
    "confidence_overall": 0.89,
    "requires_human_review": false,
    "review_reason": "string or null - why human review is needed"
  }
}
```

## Command JSON Output Requirements

Your command execution JSON output must include:

**Required Fields:**
- `command_type`: "analyze-email"
- `status`: "complete", "user_query", or "error"
- `session_summary`: Brief summary of email analysis
- `files.created`: Array with the analysis JSON file entry
- `artifacts.analysis_filename`: Path to the analysis JSON file
- `artifacts.email_data`: Copy of the email_metadata for quick reference
- `comments`: Array of notes about the analysis process

**For user_query status:**
- `queries_for_user`: Questions needing clarification
- `context`: Save partial analysis and email content

**Example Comments:**
- "Email classified as professional with high confidence (0.95)"
- "Identified 3 action items with deadlines ranging from 2-5 days"
- "Draft response prepared; requires user input for meeting availability"
- "No explicit deadlines found; suggested deadlines based on urgency level"

## Tasks to Track

Create tasks in the internal todo list:

```
1.0 Parse and extract email content
2.0 Classify email importance and urgency
3.0 Extract tasks and deadlines
4.0 Generate draft response
5.0 Save structured JSON file
```

Mark tasks as completed as you progress.

## Quality Checklist

Before marking complete, verify:
- ✅ Email metadata completely extracted and validated
- ✅ Classification includes confidence score and reasoning
- ✅ All action items extracted with urgency and deadlines
- ✅ Deadlines converted to ISO 8601 format
- ✅ Draft response addresses all key points (if response needed)
- ✅ JSON file saved with correct naming and structure
- ✅ All required JSON schema fields populated
- ✅ Comments include insights about classification and task extraction
- ✅ Edge cases handled (no deadline, no clear tasks, etc.)

## Error Handling

Handle these scenarios gracefully:

1. **Malformed Email**: Return error status with details
2. **No Clear Tasks**: Set tasks array to empty, note in comments
3. **Ambiguous Classification**: Use most likely category, lower confidence score
4. **No Response Needed**: Set draft_response.should_respond to false with explanation

## Privacy and Security Considerations

- Ensure sensitive information (passwords, SSNs, credentials) is not logged in comments
- Redact sensitive data in analysis file if present in email
- Document any sensitive content detected in analysis_metadata.requires_human_review
- Do not include full email body in command output JSON, only in analysis file
