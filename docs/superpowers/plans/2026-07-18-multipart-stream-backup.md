# Stream Local Backups via S3MultipartStream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `main.py`'s normal backup path stream the tar archive directly into S3 via the existing `S3MultipartStream`, instead of writing a local `.tar.gz` first, and remove the unrelated S3-to-S3 re-archiving code that was scaffolded alongside it.

**Architecture:** `create_backup()` opens a `tarfile` with `fileobj=S3MultipartStream(...)` in streaming mode (`"w|gz"`) so tar output is written directly into S3 multipart upload parts as it's produced — no intermediate local file. `S3MultipartStream` gains an optional resume checkpoint (`CHECKPOINT_PATH`) and switches its progress output from `print()` to the project's existing `logger`, which already fans out to console, file, and Telegram. Dead code (`stream_s3_objects_to_targz`, `S3ObjectReader`, and the `S3Config` methods only they used) is deleted.

**Tech Stack:** Python 3, boto3 (S3 multipart upload API), Python's `tarfile`/`io` standard library, this repo's existing `settings.py` / `utils/logger.py`.

## Global Constraints

- No test framework exists in this repo (confirmed: no `pytest`/`unittest` files present). Verification in this plan uses `python -m py_compile` for syntax/import sanity checks and manual code review — there are no automated unit tests to write or run.
- Preserve existing coding style in each file (2-space indentation is used throughout `modules/s3/*.py`, `main.py`, and `settings.py` — match it exactly in new/edited lines).
- Do not touch `S3Uploader` (`modules/s3/uploader.py`) or the `SKIP_BACKUP` upload path — out of scope per the spec's non-goals.
- Do not touch `modules/s3/remover.py` or `modules/notification/telegram.py` — out of scope.

---

### Task 1: Add `CHECKPOINT_PATH` setting

**Files:**
- Modify: `settings.py`

**Interfaces:**
- Produces: `settings.CHECKPOINT_PATH` (`str | None`) — consumed by Task 5 (`main.py`'s `create_backup()`).

- [ ] **Step 1: Add the setting**

In `settings.py`, add this line after `MULTIPART_SIZE` (currently the last line, line 25):

```python
CHECKPOINT_PATH = os.environ.get("CHECKPOINT_PATH")
```

The full end of the file should read:

```python
# default 50MB
MULTIPART_SIZE = int(os.environ.get("MULTIPART_SIZE", 50 * 1024 * 1024))

CHECKPOINT_PATH = os.environ.get("CHECKPOINT_PATH")
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -m py_compile settings.py`
Expected: no output, exit code 0.

- [ ] **Step 3: Verify the value is readable**

Run: `python -c "import settings; print(settings.CHECKPOINT_PATH)"`
Expected: prints `None` (since `CHECKPOINT_PATH` isn't set in your shell environment).

- [ ] **Step 4: Commit**

```bash
git add settings.py
git commit -m "feat: add CHECKPOINT_PATH setting for multipart upload resume"
```

---

### Task 2: Remove `stream_s3_objects_to_targz` and delete `S3ObjectReader`

**Files:**
- Modify: `modules/s3/multipartstream.py`
- Delete: `modules/s3/objectreader.py`

**Interfaces:**
- Consumes: none (pure deletion).
- Produces: `modules/s3/multipartstream.py` no longer imports `S3ObjectReader` or defines `stream_s3_objects_to_targz`; later tasks (3, 4) edit the file assuming this function and import are already gone.

- [ ] **Step 1: Remove the `S3ObjectReader` import**

In `modules/s3/multipartstream.py`, delete line 7:

```python
from modules.s3.objectreader import S3ObjectReader
```

- [ ] **Step 2: Remove `stream_s3_objects_to_targz`**

Delete the entire function (currently lines 101-136, everything from `def stream_s3_objects_to_targz(` through the end of the file, including its docstring and trailing blank line).

After this step and Step 1, `modules/s3/multipartstream.py` should end at the `abort()` method (currently lines 96-99):

```python
    def abort(self):
        """Call explicitly if you want to give up entirely (not just pause)."""
        self.s3_config.abort_multipart_upload(upload_id=self.upload_id)
        self._clear_checkpoint()
```

Also remove the now-unused `import tarfile` and `import time` at the top of the file (lines 4-5) — they were only used by `stream_s3_objects_to_targz`. The top of the file should read:

```python
import io
import json
import os
from modules.s3.config import S3Config
import settings
```

- [ ] **Step 3: Delete `objectreader.py`**

```bash
rm modules/s3/objectreader.py
```

- [ ] **Step 4: Verify no remaining references**

Run: `grep -rn "S3ObjectReader\|stream_s3_objects_to_targz\|objectreader" --include="*.py" . | grep -v virtualenv`
Expected: no output (empty).

- [ ] **Step 5: Verify the file still compiles**

Run: `python -m py_compile modules/s3/multipartstream.py`
Expected: no output, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add modules/s3/multipartstream.py
git rm modules/s3/objectreader.py
git commit -m "refactor: remove unused S3-to-S3 re-archiving code"
```

---

### Task 3: Replace `print()` with `logger` in `S3MultipartStream`

**Files:**
- Modify: `modules/s3/multipartstream.py`

**Interfaces:**
- Consumes: `logger` from `utils/logger.py` (module-level singleton, already used the same way in `main.py`, `modules/s3/config.py`, `modules/s3/remover.py`).
- Produces: no new interfaces — internal behavior change only (log output instead of stdout).

- [ ] **Step 1: Import the logger**

In `modules/s3/multipartstream.py`, add this import after `import settings`:

```python
from utils.logger import logger
```

- [ ] **Step 2: Replace the resume message**

Change (currently lines 28-29, after Task 2's deletions the line numbers shift up — locate by content, not line number):

```python
            print(f"[resume] continuing upload_id={self.upload_id}, "
                  f"{len(self.parts)} parts already uploaded")
```

to:

```python
            logger.info(f"[resume] continuing upload_id={self.upload_id}, "
                        f"{len(self.parts)} parts already uploaded")
```

- [ ] **Step 3: Replace the part-uploaded message**

Change:

```python
        print(f"[part {self.part_number}] uploaded {len(chunk)/1024/1024:.1f} MB"
              f"(Total so far: {self.bytes_written/1024/1024:.1f} MB)")
```

to:

```python
        logger.info(f"[part {self.part_number}] uploaded {len(chunk)/1024/1024:.1f} MB"
                    f"(Total so far: {self.bytes_written/1024/1024:.1f} MB)")
```

- [ ] **Step 4: Replace the done message**

Change:

```python
            print(f"[done] {self.s3_prefix} complete, {self.bytes_written/1024/1024:.1f} MB total")
```

to:

```python
            logger.info(f"[done] {self.s3_prefix} complete, {self.bytes_written/1024/1024:.1f} MB total")
```

- [ ] **Step 5: Replace the error message**

Change:

```python
        except Exception:
            print("[error] upload failed, checkpoint preserved for resume "
                  "(multipart upload NOT aboarted so it can be resumed)")
            raise
```

to:

```python
        except Exception:
            logger.error("[error] upload failed, checkpoint preserved for resume "
                         "(multipart upload NOT aborted so it can be resumed)")
            raise
```

(Note: this also fixes the pre-existing "aboarted" typo → "aborted".)

- [ ] **Step 6: Verify no `print()` calls remain in the file**

Run: `grep -n "print(" modules/s3/multipartstream.py`
Expected: no output (empty).

- [ ] **Step 7: Verify the file compiles**

Run: `python -m py_compile modules/s3/multipartstream.py`
Expected: no output, exit code 0.

- [ ] **Step 8: Commit**

```bash
git add modules/s3/multipartstream.py
git commit -m "refactor: route S3MultipartStream progress output through logger"
```

---

### Task 4: Remove unused `get_object`/`head_bucket` from `S3Config`

**Files:**
- Modify: `modules/s3/config.py`

**Interfaces:**
- Consumes: none.
- Produces: `S3Config` public surface is now exactly `create_client()`, `create_resource()`, `create_multipart_upload()`, `upload_part()`, `complete_multipart_upload()`, `abort_multipart_upload()` — this is the surface Task 5 relies on.

- [ ] **Step 1: Confirm nothing outside this file still calls these methods**

Run: `grep -rn "\.get_object(\|\.head_bucket(" --include="*.py" . | grep -v virtualenv`
Expected: only matches inside `modules/s3/config.py` itself (the method definitions) — confirms Task 2's deletion of `S3ObjectReader`/`stream_s3_objects_to_targz` already removed all external callers.

- [ ] **Step 2: Remove the two methods**

In `modules/s3/config.py`, delete lines 67-78 (the blank line before `get_object`, both method definitions, through the end of file):

```python
    
    def get_object(self, source_key: str):
       return self.create_client().get_object(
          Bucket=self.bucket_name,
          Key=source_key,
       )["Body"]
    
    def head_bucket(self, source_key: str):
       return self.create_client().head_object(
          Bucket=self.bucket_name,
          Key=source_key,
       )
```

The file should now end with `abort_multipart_upload` (currently lines 61-66):

```python
    def abort_multipart_upload(self, upload_id: str):
       return self.create_client().abort_multipart_upload(
          Bucket=self.bucket_name,
          Key=self.prefix,
          UploadId=upload_id,
       )
```

- [ ] **Step 3: Verify the file compiles**

Run: `python -m py_compile modules/s3/config.py`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add modules/s3/config.py
git commit -m "refactor: remove unused get_object/head_bucket from S3Config"
```

---

### Task 5: Stream `create_backup()` directly to S3 in `main.py`

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes:
  - `S3MultipartStream(checkpoint_path: str | None)` from `modules/s3/multipartstream.py` (Tasks 2-3) — a `tarfile`-compatible `fileobj`; call `.close()` after the `with tarfile.open(...)` block to finalize the multipart upload.
  - `settings.CHECKPOINT_PATH` (Task 1).
- Produces: `create_backup()` now returns `None` (previously returned `backup_path: Path`) — no other function in this file calls `create_backup()`'s return value except `main()`, which is updated in this task to match.

- [ ] **Step 1: Import `S3MultipartStream`**

In `main.py`, add this import after `from modules.s3.uploader import S3Uploader` (line 8):

```python
from modules.s3.multipartstream import S3MultipartStream
```

- [ ] **Step 2: Remove the now-unused `_backup_dir` module variable**

Delete line 12:

```python
_backup_dir = settings.BACKUP_DIR
```

- [ ] **Step 3: Rewrite `create_backup()` to stream directly to S3**

Replace the entire function (currently lines 19-33):

```python
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
```

with:

```python
def create_backup():
  stream = S3MultipartStream(checkpoint_path=settings.CHECKPOINT_PATH)

  logger.info(f"Streaming backup of {_source_dir} directly to S3")

  with tarfile.open(fileobj=stream, mode="w|gz") as tar:
    tar.add(_source_dir, arcname=os.path.basename(_source_dir))

  stream.close()

  logger.info("Backup streamed to S3 successfully")
```

- [ ] **Step 4: Fix `cleanup_old_backup`'s default argument**

The function's default parameter references the now-deleted `_backup_dir`:

```python
def cleanup_old_backup(target_dir=_backup_dir, pattern="backup-*.tar.gz"):
```

Change to a required parameter (its only remaining caller, in Step 5, always passes `target_dir` explicitly):

```python
def cleanup_old_backup(target_dir, pattern="backup-*.tar.gz"):
```

- [ ] **Step 5: Update `main()` — normal path no longer creates or uploads a local file, `SKIP_BACKUP` path unchanged**

Replace the body of `main()` (currently lines 58-101):

```python
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
```

with:

```python
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
      else:
          # Stream a new backup directly to S3 (no local file involved)
          create_backup()

  except Exception as e:
    logger.error(e)
    sys.exit(1)

  finally:
    if _skip_backup:
      cleanup_old_backup(_source_dir, pattern="*.sql")

    remover = S3Remover()
    remover.remove_objects()
```

Note what changed and why:
- The `else` branch (normal path) now just calls `create_backup()`, which handles its own upload internally via `S3MultipartStream` — it no longer produces a `files_to_upload` list or goes through `S3Uploader`.
- The `if _backup_service == "s3":` upload block moved inside the `if _skip_backup:` branch, since it's now only relevant to the `SKIP_BACKUP` path. (If `_backup_service != "s3"` in the non-skip path, `create_backup()` still runs and uploads via `S3MultipartStream` — this preserves existing behavior where `BACKUP_SERVICE` wasn't actually checked for the tar path before either, since `S3Config`/`S3MultipartStream` always target S3 regardless of that variable.)
- The `finally` block's `else: cleanup_old_backup()` call is removed — there's no local file to clean up on the streaming path.

- [ ] **Step 6: Verify the file compiles**

Run: `python -m py_compile main.py`
Expected: no output, exit code 0.

- [ ] **Step 7: Verify no leftover references to removed names**

Run: `grep -n "_backup_dir\b" main.py`
Expected: no output (empty) — confirms the deleted module variable isn't referenced anywhere else in the file.

- [ ] **Step 8: Manual smoke test**

This repo has no automated test suite, so verify behavior manually against real (or test) S3 credentials:

1. Set required env vars: `S3_BUCKET_NAME`, `S3_PREFIX_PATH`, `S3_ENDPOINT`, `SOURCE_DIR` (point it at a small directory), and optionally `CHECKPOINT_PATH` (e.g. `/tmp/backup-checkpoint.json`).
2. Run: `python main.py`
3. Confirm in the logs: `"Streaming backup of ... directly to S3"` followed by one or more `"[part N] uploaded ..."` lines and `"[done] ... complete"` / `"Backup streamed to S3 successfully"`.
4. Confirm no `backup-*.tar.gz` file was written anywhere on local disk.
5. Confirm the object exists in the S3 bucket at `S3_PREFIX_PATH`.
6. If `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are configured, confirm the same log lines arrived as Telegram messages.

- [ ] **Step 9: Commit**

```bash
git add main.py
git commit -m "feat: stream local backups directly to S3 via S3MultipartStream"
```

---

## Self-Review Notes

- **Spec coverage:** `main.py` streaming change → Task 5. `CHECKPOINT_PATH` setting → Task 1. `stream_s3_objects_to_targz`/`S3ObjectReader` removal → Task 2. `print()` → `logger` → Task 3. `S3Config.get_object`/`head_bucket` removal → Task 4. All five spec sections covered.
- **Type consistency:** `S3MultipartStream(checkpoint_path=...)` signature (Task's existing code, unchanged) matches the call in Task 5 Step 3. `cleanup_old_backup(target_dir, pattern=...)` signature from Task 5 Step 4 matches its only call site in Task 5 Step 5 (`cleanup_old_backup(_source_dir, pattern="*.sql")`).
- **Placeholder scan:** no TBD/TODO markers; every step shows exact before/after code.
