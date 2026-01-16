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