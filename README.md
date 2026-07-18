# 📁 Simple Backup Program

A Python utility for backing up a directory straight to S3-compatible storage.

## 📋 Prerequisites

- Python 3.x
- Required packages (install via `pip install -r requirements.txt`)

## 🔑 Environment Variables

### Required for S3 Uploads
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## 🚀 How It Works

`SOURCE_DIR` is tarred and gzipped **in memory, streamed directly into an S3
multipart upload** — no local `.tar.gz` file is ever written to disk. Each
run uploads to a uniquely timestamped key
(`<S3_PREFIX_PATH>/backup-<timestamp>.tar.gz>`), so backups don't overwrite
each other. After a successful (or failed) run, `S3Remover` deletes objects
under `S3_PREFIX_PATH` older than `BUCKET_RETENTION_DAYS`.

If `SKIP_BACKUP` is set, no archive is created — instead, individual `.sql`
files already present in `SOURCE_DIR` are uploaded one by one via a
presigned-POST upload, and local files older than `RETENTION_DAYS` are
cleaned up from `SOURCE_DIR` afterward.

Progress, resume-in-progress-part, and error messages are logged through the
shared logger, which fans out to console, a local log file, and (if
configured) a Telegram chat.

## 🚀 Usage

### Backup and Upload to S3
```bash
SOURCE_DIR="source_directory" \
BUCKET_RETENTION_DAYS=2 \
S3_ENDPOINT="https://your-s3-endpoint.com" \
S3_BUCKET_NAME="your-bucket-name" \
S3_PREFIX_PATH="backup/service" \
python main.py
```

### Upload Existing `.sql` Files to S3 (Without Creating a New Backup)
```bash
SOURCE_DIR="existing_backup_directory" \
SKIP_BACKUP=True \
RETENTION_DAYS=1 \
BACKUP_SERVICE=s3 \
S3_ENDPOINT="https://your-s3-endpoint.com" \
S3_BUCKET_NAME="your-bucket-name" \
S3_PREFIX_PATH="backup/service" \
python main.py
```

### Optional: Telegram Notifications
```bash
TELEGRAM_BOT_TOKEN="123456:your-bot-token" \
TELEGRAM_CHAT_ID="your-chat-id" \
...
python main.py
```
If unset, Telegram logging is silently skipped — everything else still logs to console/file.

## ⚙️ Parameters

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SOURCE_DIR` | Directory to back up, or directory to upload `.sql` files from if `SKIP_BACKUP` is `True` | - | ✅ |
| `RETENTION_DAYS` | (`SKIP_BACKUP` path only) delete local `.sql` files in `SOURCE_DIR` older than X days after upload | 1 | ❌ |
| `BACKUP_SERVICE` | (`SKIP_BACKUP` path only) set to `s3` to upload `.sql` files to S3 | None | ❌ |
| `SKIP_BACKUP` | Skip archiving; upload existing `.sql` files in `SOURCE_DIR` instead | False | ❌ |
| `S3_BUCKET_NAME` | S3 bucket name | - | ✅ |
| `S3_PREFIX_PATH` | S3 key prefix backups are written under | - | ✅ |
| `S3_ENDPOINT` | S3-compatible endpoint | - | ✅ |
| `BUCKET_RETENTION_DAYS` | Delete S3 objects under `S3_PREFIX_PATH` older than X days | 0 | ❌ |
| `MULTIPART_SIZE_MB` | Megabytes per multipart upload part for the streaming backup path | 50 | ❌ |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for log notifications | - | ❌ |
| `TELEGRAM_CHAT_ID` | Telegram chat ID to send log notifications to | - | ❌ |

## 🔄 Retention Policy

- The streaming backup path: each run writes a new timestamped object under `S3_PREFIX_PATH`; `S3Remover` deletes objects older than `BUCKET_RETENTION_DAYS` from S3.
- The `SKIP_BACKUP` path: local `.sql` files in `SOURCE_DIR` older than `RETENTION_DAYS` are removed after upload, in addition to the same S3-side retention above.

## 📦 Dependencies

To generate `requirements.txt`:
```bash
pip freeze > requirements.txt
```

## 📝 Notes
- The normal backup path never writes a `.tar.gz` to local disk — the tar stream goes straight into an S3 multipart upload.
- S3 upload requires valid AWS credentials with proper permissions.
- All paths should be absolute or relative to the script's execution directory.

## 📝 TODO
- When skipping the backup and uploading existing files to S3, the pattern is currently hardcoded to `*.sql` — this could become a configurable parameter in the future.