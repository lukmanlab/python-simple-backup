import os

def _required(key: str) -> str:
  value = os.environ.get(key)
  if not value:
    raise RuntimeError(f"Missing required environment variable: {key}")
  return value

SOURCE_DIR = os.environ.get("SOURCE_DIR")
BACKUP_DIR = os.environ.get("BACKUP_DIR")

SKIP_BACKUP = os.environ.get("SKIP_BACKUP")
BACKUP_SERVICE = os.environ.get("BACKUP_SERVICE")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "1"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_PREFIX_PATH = os.environ["S3_PREFIX_PATH"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
BUCKET_RETENTION_DAYS = os.environ.get("BUCKET_RETENTION_DAYS", "0")
