# EmailAssistant Architecture Details

## Data Flow: Email Fetching

```
User: python main.py --folders INBOX --since 2025-01-01
                    │
                    ▼
            ┌───────────────┐
            │EmailAssistant │
            │  __init__()   │
            │               │
            │ Load backends │
            │ from config   │
            └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │process_emails │
            │               │
            │ For each      │
            │ backend...    │
            └───────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│ GmailBackend  │       │  EmailCache   │
│               │       │               │
│ Query Gmail   │       │ is_processed? │
│ API with      │       │               │
│ filters       │       │ Skip if yes   │
└───────────────┘       └───────────────┘
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
            ┌───────────────┐
            │EmailConverter │
            │               │
            │ email_to_job()│
            │ + encryption  │
            └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │   JobQueue    │
            │               │
            │ add_job()     │
            │ → queued_jobs/│
            └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  EmailCache   │
            │               │
            │mark_processed │
            │ (SQLite)      │
            └───────────────┘
```

## Data Flow: Job Processing

```
User: python job_consumer.py <job_id>
                    │
                    ▼
            ┌───────────────┐
            │ JobConsumer   │
            │  __init__()   │
            │               │
            │ Load queue    │
            │ directories   │
            └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │ process_job() │
            │               │
            │ 1. Load JSON  │
            │ 2. Move to    │
            │    running/   │
            └───────────────┘
                    │
                    ▼
            ┌───────────────┐
            │_process_email │
            │               │
            │ 1. Create     │
            │    tmp dir    │
            │ 2. Decrypt    │
            │ 3. Write JSON │
            └───────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         _run_claude_analysis()          │
│                                         │
│ Build prompt with email content         │
│                                         │
│ cmd = [                                 │
│   "claude", "-p", prompt,               │
│   "--output-format", "json",            │
│   "--dangerously-skip-permissions"      │
│ ]                                       │
│                                         │
│ subprocess.run(cmd, ...)                │
└─────────────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │ Parse JSON    │
            │ response      │
            │               │
            │ Store in job  │
            │ Move to       │
            │ finished/     │
            └───────────────┘
```

## Email Backend Interface

```python
class EmailBackend(ABC):
    """Abstract base class for email backends"""

    @abstractmethod
    def get_all_folders(self) -> List[str]:
        """Get list of all folder names"""
        pass

    @abstractmethod
    def get_emails_from_folder(
        self,
        folder_path: str,
        limit: Optional[int] = None,
        since_date: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Retrieve emails from folder (newest first)

        Yields email dictionaries with:
        - id: Unique message identifier
        - subject: Email subject
        - sender_name, sender_address
        - to_recipients, cc_recipients
        - received_time, sent_time
        - body_text, body_html
        - attachment_count, attachments
        """
        pass

    def get_all_emails(
        self,
        folder_filter: Optional[List[str]] = None,
        limit_per_folder: Optional[int] = None,
        since_date: Optional[str] = None
    ) -> Generator:
        """Retrieve from multiple folders"""
        # Default implementation iterates folders
```

## Job JSON Structure

```json
{
  "config": {
    "job_id": "uuid-string",
    "queue_time": "2025-01-12T10:30:00Z",
    "working_directory": "/Users/chenry/Dropbox/Projects/EmailAssistant",
    "timeout_seconds": null,
    "environment": {},
    "data": {
      "subject": "Email subject",
      "sender": "sender@example.com",
      "recipients": ["recipient@example.com"],
      "received_time": "2025-01-12T10:00:00",
      "content": {
        "body_text": "Plain text content (possibly encrypted)",
        "body_html": "HTML content (possibly encrypted)"
      },
      "folder": "Personal Gmail/INBOX",
      "account": "Personal Gmail"
    }
  },
  "runtime": {
    "status": "queued|running|completed|failed",
    "start_time": null,
    "finish_time": null,
    "process_id": null,
    "error": null,
    "exit_code": null
  }
}
```

## Encryption

When `ENABLE_ENCRYPTION=True` in config.py:

```python
# email_converter.py encrypts body_text and body_html:
{
  "body_text": {
    "encrypted": true,
    "data": "base64-encrypted-content",
    "salt": "base64-salt",
    "nonce": "base64-nonce"
  }
}

# job_consumer.py decrypts before processing:
password = config.get_encryption_password()
content = EmailEncryption.decrypt_with_password(encrypted_data, password)
```

## SQLite Cache Schema

```sql
-- email_cache.db
CREATE TABLE processed_emails (
    entry_id TEXT PRIMARY KEY,
    subject TEXT,
    sender TEXT,
    received_time TEXT,
    folder TEXT,
    job_id TEXT,
    processed_at TEXT
);
```

## Gmail Query Syntax

The Gmail backend uses Gmail's search operators:

```python
# Current filter in gmail_api.py:
query = f'label:{folder_path} (label:important OR label:category_personal)'

# Common operators:
# label:INBOX          - In inbox
# label:important      - Marked important by Gmail
# label:category_personal - Personal category
# after:2025/01/01     - After date
# before:2025/12/31    - Before date
# from:sender@email.com
# is:unread
# has:attachment
```

## Error Handling

### Job Consumer Failure Flow

```
Job fails at any step
        │
        ▼
┌───────────────────────────┐
│ Catch exception           │
│                           │
│ job['runtime']['status']  │
│   = 'failed'              │
│ job['runtime']['error']   │
│   = str(exception)        │
│                           │
│ Move to failed_jobs/      │
└───────────────────────────┘
```

### Dryrun Mode

`--dryrun` flag in job_consumer.py:
1. Creates work directory
2. Decrypts and writes email.json
3. Prints Claude command
4. Exits without running Claude
5. Restores job to queued state
