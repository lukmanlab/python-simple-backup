import sys
import tarfile
import time
import os
from pathlib import Path
from modules.s3.uploader import create_s3_uploader
from utils.logger import logger

SOURCE_DIR = os.environ.get("SOURCE_DIR")
BACKUP_DIR = os.environ.get("BACKUP_DIR")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "1"))

def create_backup():
  timestamp = time.strftime("%Y-%m-%d_%H%M%S")
  backup_name = f"backup-{timestamp}.tar.gz"
  backup_path = Path(BACKUP_DIR) / backup_name

  os.makedirs(BACKUP_DIR, exist_ok=True)

  logger.info(f"Creating backup: {backup_path}")

  with tarfile.open(backup_path, "w:gz") as tar:
    tar.add(SOURCE_DIR, arcname=os.path.basename(SOURCE_DIR))

  logger.info(f"Backup completed: {backup_path}")

  return backup_path

def cleanup_old_backup():
  time_now = time.time()
  deleted = 0

  for file in Path(BACKUP_DIR).glob("backup-*.tar.gz"):
    # 60 * 60 * 24 = 1 day
    age_days = (time_now - file.stat().st_mtime) / 86400

    if (age_days) > RETENTION_DAYS:
      file.unlink()
      deleted += 1
      logger.info(f"Old backups removed: {deleted}")
      

def main():
  if not os.path.exists(SOURCE_DIR):
    logger.error(f"Source directory not found: {SOURCE_DIR}")
    sys.exit(2)

  try:
    backup = create_backup()

    if not backup or not os.path.exists(backup):
      sys.exit(1)
    
    if os.environ.get("BACKUP_SERVICE") == "s3":
      uploader = create_s3_uploader()
      if uploader and not uploader.upload_file_v2(backup, dst=os.environ["S3_PREFIX_PATH"]):
        logger.error("Failed to upload to S3")
        sys.exit(1)

  except Exception as e:
    logger.error(e)
    sys.exit(1)

  finally:
    cleanup_old_backup()


if __name__ == "__main__":
  main()
