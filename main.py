import logging
import sys
import tarfile
import time
import os
from pathlib import Path
from modules.s3.remover import S3Remover
from modules.s3.uploader import S3Uploader
from utils.logger import logger
import settings

_backup_dir = settings.BACKUP_DIR
_source_dir = settings.SOURCE_DIR
_retention_days = settings.RETENTION_DAYS
_backup_service = settings.BACKUP_SERVICE
_s3_prefix_path = settings.S3_PREFIX_PATH
_skip_backup = settings.SKIP_BACKUP

def create_backup():
  timestamp = time.strftime("%Y-%m-%d_%H%M%S")
  backup_name = f"backup-{timestamp}.tar.gz"
  backup_path = Path(_backup_dir) / backup_name

  os.makedirs(_backup_dir, exist_ok=True)

  logger.info(f"Creating backup: {backup_path}")

  with tarfile.open(backup_path, "w:gz") as tar:
    tar.add(_source_dir, arcname=os.path.basename(_source_dir))

  logger.info(f"Backup completed: {backup_path}")

  return backup_path

def cleanup_old_backup(target_dir=_backup_dir, pattern="backup-*.tar.gz"):
  time_now = time.time()
  deleted = 0

  for file in Path(target_dir).glob(pattern):
    # 60 * 60 * 24 = 1 day
    age_days = (time_now - file.stat().st_mtime) / 86400

    if (age_days) > _retention_days:
      file.unlink()
      deleted += 1
      logger.info(f"Old backups removed: {deleted}")
      
def get_source_files(pattern="*.sql") -> list[Path]:
  contents = Path(_source_dir).glob(pattern)
  
  file_list = []

  for file in contents:
    file_list.append(file)

  return file_list

def main():
  if not os.path.exists(_source_dir):
    logger.error(f"Source directory not found: {_source_dir}")
    sys.exit(2)

  try:
      if _skip_backup:
          # When skipping backup, process all SQL files
          files_to_upload = get_source_files()
          if not files_to_upload:
              logger.error("No files found to upload")
              sys.exit(1)
      else:
          # Create a new backup and upload just that
          backup = create_backup()
          if not backup or not os.path.exists(backup):
              logger.error("Backup creation failed")
              sys.exit(1)
          files_to_upload = [backup]

      # Upload all files
      if _backup_service == "s3":
          uploader = S3Uploader()
          if not uploader:
              logger.error("Failed to initialize S3 uploader")
              sys.exit(1)
          
          for file in files_to_upload:
              if not uploader.upload_file_v2(file, dst=_s3_prefix_path):
                  logger.error(f"Failed to upload {file} to S3")
                  sys.exit(1)

  except Exception as e:
    logger.error(e)
    sys.exit(1)

  finally:
    if _skip_backup:
      cleanup_old_backup(_source_dir, pattern="*.sql")
    else:  
      cleanup_old_backup()

    remover = S3Remover()
    remover.remove_objects()

if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
    logging.shutdown()
    sys.exit(1)
