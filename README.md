# 📁 Simple Backup Program

A Python utility for creating backups of directories and optionally uploading them to S3-compatible storage.

## 📋 Prerequisites

- Python 3.x
- Required packages (install via `pip install -r requirements.txt`)

## 🔑 Environment Variables

### Required for S3 Uploads
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## 🚀 Usage

### Basic Backup
```bash
SOURCE_DIR="source_directory" \
BACKUP_DIR="backup_destination" \
RETENTION_DAYS=7 \
python main.py
```

### Backup and Upload to S3
```bash
SOURCE_DIR="source_directory" \
BACKUP_DIR="backup_destination" \
RETENTION_DAYS=2 \
BACKUP_SERVICE=s3 \
S3_ENDPOINT="https://your-s3-endpoint.com" \
S3_BUCKET_NAME="your-bucket-name" \
S3_PREFIX_PATH="backup/service" \
python main.py
```

### Upload Existing Backups to S3 (Without Creating New Backups)
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

## ⚙️ Parameters

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SOURCE_DIR` | Source directory to back up, or source directory to upload if `SKIP_BACKUP` is `True` | - | ✅ |
| `BACKUP_DIR` | Directory to store backups | - (don't set if just wanna upload the backup) | ✅ |
| `RETENTION_DAYS` | Delete files older than X days | 1 | ✅ |
| `BACKUP_SERVICE` | Set to 's3' for S3 upload | None | ❌ |
| `S3_ENDPOINT` | S3-compatible endpoint | - | If using S3 |
| `S3_BUCKET_NAME` | S3 bucket name | - | If using S3 |
| `S3_PREFIX_PATH` | S3 path prefix | - | If using S3 |
| `SKIP_BACKUP` | Skip backup, only upload existing files | False | ❌ |

## 🔄 Retention Policy

- Files older than `RETENTION_DAYS` will be automatically removed from both local backup directory and S3 (if enabled).
- The retention is based on file modification time.

## 📦 Dependencies

To generate `requirements.txt`:
```bash
pip freeze > requirements.txt
```

## 📝 Notes
- The script creates `.tar.gz` archives of the source directory
- S3 upload requires valid AWS credentials with proper permissions
- All paths should be absolute or relative to the script's execution directory

## 📝 TODO
- When skip the backup and need to upload to s3, currently the pattern is only support `*.sql`, this can be dynamicaly using parameter in the future.