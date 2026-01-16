# Simple Backup Program

## How to extract dependency needed
```bash
pip freeze > requirements.txt
```

### How to run this program
```bash
SOURCE_DIR="cobasrc" \
BACKUP_DIR="cobadest" \
RETENTION_DAYS=7 \
python main.py
```

### How to send the backup to s3
- Export Key
```bash
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=yyy
```

```bash
SOURCE_DIR="cobasrc" \
BACKUP_DIR="cobadest" \
RETENTION_DAYS=2 \
BACKUP_SERVICE=s3 \
S3_BUCKET_NAME="bucketTest" \
S3_PREFIX_PATH="serviceTest" \
python main.py
```