# Stream local backups directly to S3 via S3MultipartStream

## Problem

`main.py`'s normal backup path currently does: tar `SOURCE_DIR` to a local
`backup-<timestamp>.tar.gz` file in `BACKUP_DIR`, then upload that file with
`S3Uploader.upload_file_v2()` (boto3's high-level `upload_file`, which does
its own multipart handling internally). This means the full backup archive
is written to local disk before upload even starts, which wastes disk I/O
and requires enough free disk space to hold the whole archive.

`modules/s3/multipartstream.py` already contains `S3MultipartStream`, a
file-like object that streams writes directly into an S3 multipart upload
with checkpoint-based resume support. This spec wires it into `main.py`'s
backup flow so the tar stream goes straight to S3, and cleans up the
unrelated code that was scaffolded alongside it.

## Goals

- `create_backup()`'s normal path streams the tar directly to S3 — no local
  `.tar.gz` file is ever written.
- Interrupted uploads can be resumed via a checkpoint file, whose path is
  configured through a new `CHECKPOINT_PATH` setting.
- Progress/resume/success/failure messages go through the existing `logger`
  (which already fans out to console, file, and Telegram) instead of raw
  `print()`.
- Remove code in `modules/s3/multipartstream.py` and related files that
  isn't used by this flow.

## Non-goals

- The `SKIP_BACKUP` path (uploading individual pre-existing `.sql` files via
  `S3Uploader.upload_file_v2()`) is unchanged. Those files are already local
  and typically much smaller, so boto3's own multipart handling remains
  adequate there.
- `S3Uploader` (presigned POST, `upload_file`, `upload_file_v2`) is
  unchanged and stays in use for the `SKIP_BACKUP` path.
- No new local backup retention logic is added. S3-side retention already
  happens via `S3Remover.remove_objects()`.

## Design

### `main.py`

`create_backup()` changes from writing a local file to streaming directly
into `S3MultipartStream`:

```python
from modules.s3.multipartstream import S3MultipartStream

def create_backup():
    stream = S3MultipartStream(checkpoint_path=settings.CHECKPOINT_PATH)
    logger.info(f"Streaming backup of {_source_dir} directly to S3")

    with tarfile.open(fileobj=stream, mode="w|gz") as tar:
        tar.add(_source_dir, arcname=os.path.basename(_source_dir))

    stream.close()
    logger.info("Backup streamed to S3 successfully")
```

- `BACKUP_DIR`, `os.makedirs(_backup_dir, ...)`, and the `cleanup_old_backup()`
  call for the normal (non-`SKIP_BACKUP`) path are removed, since there is no
  longer a local archive to manage retention for.
- `cleanup_old_backup()` itself and its `SKIP_BACKUP`-path call (which
  targets `*.sql` files in `SOURCE_DIR`, not the tar output) are unchanged.
- Errors raised inside the `with tarfile.open(...)` block (e.g. a mid-upload
  S3 failure) propagate up through `create_backup()` and are caught by
  `main()`'s existing `try/except Exception` block, which already logs and
  exits — no new error handling is needed there. Per the existing comment in
  `S3MultipartStream.close()`, the checkpoint file is preserved on failure so
  a rerun with the same `CHECKPOINT_PATH` resumes from the last completed
  part instead of restarting the whole tar.

### `settings.py`

Add one new optional setting:

```python
CHECKPOINT_PATH = os.environ.get("CHECKPOINT_PATH")
```

If unset, `S3MultipartStream` receives `checkpoint_path=None`; its existing
`_load_checkpoint`/`_save_checkpoint` methods are already no-ops in that
case (`if self.checkpoint_path and ...`), so resume is simply disabled
rather than erroring.

### `modules/s3/multipartstream.py`

- Delete `stream_s3_objects_to_targz()` and its
  `from modules.s3.objectreader import S3ObjectReader` import. That function
  re-archives objects that already exist in S3 — a different use case from
  streaming a local directory to S3, and not needed by this flow.
- Add `from utils.logger import logger` and replace all `print(...)` calls
  with `logger` calls, so this output flows through the same pipeline
  already wired to console, file, and Telegram:
  - `print(f"[resume] continuing upload_id=...")` → `logger.info(...)`
  - `print(f"[part {n}] uploaded ...")` → `logger.info(...)`
  - `print(f"[done] ... complete")` → `logger.info(...)`
  - `print("[error] upload failed...")` → `logger.error(...)`, kept
    immediately before the existing `raise`

### `modules/s3/objectreader.py`

Delete the file. `S3ObjectReader` has no other caller once
`stream_s3_objects_to_targz` is removed.

### `modules/s3/config.py`

Remove `get_object()` and `head_bucket()` (currently lines 68-78). Their
only callers were `S3ObjectReader.__init__` and
`stream_s3_objects_to_targz`, both being deleted. `S3Config` keeps the
methods the streaming flow actually uses: `create_client()`,
`create_resource()`, `create_multipart_upload()`, `upload_part()`,
`complete_multipart_upload()`, `abort_multipart_upload()`.

## Testing

No test suite currently exists in this repo. Verification will be manual:
run `main.py` against a small `SOURCE_DIR` with real (or test) S3
credentials, confirm the backup lands in the bucket with no local
`.tar.gz` created, confirm log lines (including a Telegram message, if
`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are configured) appear for
progress/completion, and confirm an interrupted run (e.g. killed mid-upload
with `CHECKPOINT_PATH` set) resumes on rerun instead of restarting from
scratch.
