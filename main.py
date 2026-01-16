import sys
import tarfile
import time
import os
from pathlib import Path

SOURCE_DIR = os.environ.get("SOURCE_DIR")
BACKUP_DIR = os.environ.get("BACKUP_DIR")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS"))

def create_backup():
  timestamp = time.strftime("%Y-%m-%d_%H%M%S")
  backup_name = f"backup-{timestamp}.tar.gz"
  backup_path = Path(BACKUP_DIR) / backup_name

  os.makedirs(BACKUP_DIR, exist_ok=True)

  print(f"Creating backup: {backup_path}")

  with tarfile.open(backup_path, "w:gz") as tar:
    tar.add(SOURCE_DIR, arcname=os.path.basename(SOURCE_DIR))

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

  return deleted

def main():
  if not os.path.exists(SOURCE_DIR):
    print(f"Source directory not found: {SOURCE_DIR}")
    sys.exit(2)

  backup = create_backup()
  deleted = cleanup_old_backup()

  print(f"Backup completed: {backup}")
  print(f"Old backups removed: {deleted}")

  sys.exit(0)


if __name__ == "__main__":
  main()
