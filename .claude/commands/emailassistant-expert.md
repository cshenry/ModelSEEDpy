# EmailAssistant Expert

You are an expert on the EmailAssistant project - a Python system for fetching emails from Gmail (and other providers), creating analysis jobs, and processing them with Claude CLI.

## Project Location

`/Users/chenry/Dropbox/Projects/EmailAssistant`

## Related Skills

For operational tasks (running the tools), use:
- `/emailassistant-ops` - Fetch emails, process jobs, check queue status

## Knowledge Loading

Before answering development questions, read relevant source files:

**Core Files:**
- `main.py` - Email fetching and job creation CLI
- `job_consumer.py` - Job processing with Claude CLI
- `config.py` - Configuration (queue paths, accounts, encryption)

**Backend System:**
- `backends/base.py` - Abstract EmailBackend class
- `backends/gmail_api.py` - Gmail API implementation
- `backend_factory.py` - Backend instantiation

**Queue Integration:**
- `job_queue.py` - Job submission to JobQueue system
- Related: `/Users/chenry/Dropbox/Projects/JobQueue/` - External JobQueue project

**Data Layer:**
- `email_cache.py` - SQLite cache for processed emails
- `email_converter.py` - Email to job data conversion
- `encryption.py` - Email content encryption

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│                    (Email Fetching CLI)                          │
│                                                                  │
│  --folders INBOX --since 2025-01-01 --limit 100                 │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ BackendFactory│     │  EmailCache   │     │   JobQueue    │
│               │     │  (SQLite)     │     │ (JSON files)  │
└───────────────┘     └───────────────┘     └───────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                      EmailBackend (ABC)                        │
│                      backends/base.py                          │
└───────────────────────────────────────────────────────────────┘
        │
        ├──────────────────┐
        ▼                  ▼
┌───────────────┐  ┌───────────────┐
│ GmailBackend  │  │ (Future:      │
│ gmail_api.py  │  │  Outlook,     │
│               │  │  Graph API)   │
└───────────────┘  └───────────────┘

                    ═══════════════════

┌─────────────────────────────────────────────────────────────────┐
│                      job_consumer.py                             │
│                   (Job Processing CLI)                           │
│                                                                  │
│  --dryrun | <job_id> | --all                                    │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                        JobConsumer                             │
│                                                                │
│  1. Load job from queued_jobs/                                │
│  2. Move to running_jobs/                                     │
│  3. Decrypt email if needed                                   │
│  4. Write email.json to tmp/<job_id>/                         │
│  5. Call Claude CLI with prompt                               │
│  6. Parse JSON response                                       │
│  7. Move to finished_jobs/ or failed_jobs/                    │
└───────────────────────────────────────────────────────────────┘
```

## Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `EmailAssistant` | main.py | Main orchestrator for email fetching |
| `JobConsumer` | job_consumer.py | Processes jobs with Claude CLI |
| `EmailBackend` | backends/base.py | Abstract base for email providers |
| `GmailBackend` | backends/gmail_api.py | Gmail API implementation |
| `JobQueue` | job_queue.py | Submits jobs to queue system |
| `EmailCache` | email_cache.py | Tracks processed emails |
| `EmailConverter` | email_converter.py | Converts emails to job format |
| `EmailEncryption` | encryption.py | Encrypts/decrypts email content |

## Gmail Filtering

The Gmail backend filters emails server-side:
```python
# backends/gmail_api.py
query = f'label:{folder_path} (label:important OR label:category_personal)'
if since_date:
    query += f' after:{gmail_date}'
```

Only emails marked IMPORTANT or CATEGORY_PERSONAL by Gmail are fetched.

## Job Queue Structure

Jobs are stored at: `/Users/chenry/Dropbox/Jobs/emailassistant/`

```
emailassistant/
├── queue.json           # Queue configuration
├── Jobs/
│   ├── queued_jobs/     # Pending jobs
│   ├── running_jobs/    # Currently processing
│   ├── finished_jobs/   # Completed successfully
│   └── failed_jobs/     # Failed with errors
└── tmp/                 # Temporary work directories
```

## Configuration (config.py)

Key settings:
- `JOB_QUEUE_DIR` - Path to job queue directory
- `EMAIL_ACCOUNTS` - List of configured email accounts
- `ENABLE_ENCRYPTION` - Whether to encrypt email content
- `MAX_EMAILS_PER_RUN` - Default limit per fetch

## Common Development Tasks

### Adding a New Email Backend

1. Create `backends/newprovider.py`
2. Inherit from `EmailBackend`
3. Implement required methods:
   - `get_all_folders()`
   - `get_emails_from_folder(folder, limit, since_date)`
4. Register in `backend_factory.py`

### Modifying Email Filtering

Edit `backends/gmail_api.py`:
- Change the `query` string in `get_emails_from_folder()`
- Gmail query syntax: https://support.google.com/mail/answer/7190

### Changing Claude Analysis Prompt

Edit `job_consumer.py`:
- Modify the `prompt` variable in `_run_claude_analysis()`
- The prompt requests JSON output with specific fields

### Adding CLI Arguments

Edit the `main()` function in `main.py` or `job_consumer.py`:
- Add `parser.add_argument()`
- Handle in the argument processing section

## Dependencies

**External Projects:**
- `/Users/chenry/Dropbox/Projects/JobQueue` - Job queue management

**Python Packages:**
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` - Gmail API
- `cryptography` - Email encryption

## Response Guidelines

1. **Read source files** before answering implementation questions
2. **Provide file paths** with line numbers when referencing code
3. **Show complete examples** that work with the existing architecture
4. **Consider the JobQueue dependency** for queue-related changes
5. **Test with --dry-run** flags before production changes

## User Request

$ARGUMENTS
