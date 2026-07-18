import logging
import sys
import tarfile
import time
import os
from pathlib import Path
from modules.s3.remover import S3Remover
from modules.s3.uploader import S3Uploader
from modules.s3.multipartstream import S3MultipartStream
from utils.logger import logger
import settings

_source_dir = settings.SOURCE_DIR
_retention_days = settings.RETENTION_DAYS
_backup_service = settings.BACKUP_SERVICE
_s3_prefix_path = settings.S3_PREFIX_PATH
_skip_backup = settings.SKIP_BACKUP

def create_backup():
  timestamp = time.strftime("%Y-%m-%d_%H%M%S")
  key = f"{settings.S3_PREFIX_PATH}/backup-{timestamp}.tar.gz"
  stream = S3MultipartStream(key=key)

  logger.info(f"Streaming backup of {_source_dir} directly to S3 as {key}")

  with tarfile.open(fileobj=stream, mode="w|gz") as tar:
    tar.add(_source_dir, arcname=os.path.basename(_source_dir))

  stream.close()

  logger.info("Backup streamed to S3 successfully")

def cleanup_old_backup(target_dir, pattern="backup-*.tar.gz"):
  time_now = time.time()
  deleted = 0

  for file in Path(target_dir).glob(pattern):
    if not file.is_file():
      continue

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

  skip_backup_succeeded = False

  try:
      if _skip_backup:
          # When skipping backup, process all SQL files
          files_to_upload = get_source_files()
          if not files_to_upload:
              logger.error("No files found to upload")
              sys.exit(1)

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

          skip_backup_succeeded = True
      else:
          # Stream a new backup directly to S3 (no local file involved)
          create_backup()

  except Exception as e:
    logger.error(e)
    sys.exit(1)

  finally:
    if _skip_backup and skip_backup_succeeded:
      cleanup_old_backup(_source_dir, pattern="*.sql")

    remover = S3Remover()
    remover.remove_objects()

if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
    logging.shutdown()
    sys.exit(1)
