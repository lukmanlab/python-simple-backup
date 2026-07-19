# NOTICE log level for Telegram success notifications

## Problem

The Telegram handler's level was recently raised from `INFO` to `WARNING`
to stop per-part multipart-upload progress logs (`modules/s3/multipartstream.py`)
from flooding the configured Telegram chat with dozens of blocking network
calls on large backups. That fix worked, but it was a blunt instrument: it
also silenced the "backup uploaded successfully" confirmation, which was
logged at the same `INFO` level as the noisy per-part messages. There is
currently no way to tell from Telegram alone whether a backup run
succeeded — only failures (`logger.error`/`logger.critical`) are visible.

## Goals

- Restore a Telegram notification confirming a successful upload, for both
  the streaming backup path and the `SKIP_BACKUP` per-file upload path.
- Notify Telegram when a backup run *starts*, for both paths, so a run that
  never reaches completion (crashes, hangs, killed) is still visible as
  having been attempted.
- Do not reintroduce per-part progress spam to Telegram.
- Keep log severity semantically honest — a success should not be logged as
  a `WARNING`.

## Non-goals

- No change to what reaches Telegram on failure — `ERROR`/`CRITICAL` paths
  are already correct and untouched.
- Retention-cleanup detail (`"Old backups removed"`, per-object
  `"Deleting object ... success"` in `S3Remover`) stays `INFO`-only
  (console/file), not promoted to Telegram. These are operational detail,
  not run-outcome milestones, and are not "backup starting/finished" events.

## Design

### New log level: `NOTICE`

In `utils/logger.py`, register a custom level between `INFO` (20) and
`WARNING` (30):

```python
NOTICE = 25
logging.addLevelName(NOTICE, "NOTICE")

def _notice(self, message, *args, **kwargs):
    if self.isEnabledFor(NOTICE):
        self._log(NOTICE, message, args, **kwargs)

logging.Logger.notice = _notice
```

This is added once, near the top of `utils/logger.py`, before `setup_logger`
is defined, so `logger.notice(...)` is available anywhere `logger` is used
in the codebase (it's the same pattern Python's own `logging` module uses
internally for `Logger.warning`/`Logger.info`, just for a level the stdlib
doesn't define out of the box).

### Telegram handler threshold

In `modules/notification/telegram.py`, `setup_telegram_logger`'s clamp
changes from `logging.WARNING` to the new `NOTICE` level:

```python
telegram_handler.setLevel(max(log_level, NOTICE))
```

Effect: `NOTICE`, `WARNING`, `ERROR`, `CRITICAL` all reach Telegram.
`DEBUG`/`INFO` (per-part progress, start messages, retention detail) do
not.

### Call sites promoted to `NOTICE`

**Streaming backup path:**
1. `main.py:24` — the existing start line changes from `logger.info` to
   `logger.notice`:
   ```python
   logger.notice(f"Streaming backup of {_source_dir} directly to S3 as {key}")
   ```
2. `modules/s3/multipartstream.py` — the `"[done] {key} complete, ..."`
   line in `close()` changes from `logger.info` to `logger.notice`. This is
   the authoritative "this archive is fully uploaded to S3" confirmation
   for the streaming backup path.

(`main.py:31`'s `"Backup streamed to S3 successfully"` — printed
immediately after `create_backup()` returns — is now redundant with the
`[done]` NOTICE already sent from inside `close()`; drop this line rather
than sending two Telegram messages for one completion event.)

**`SKIP_BACKUP` path** (currently has no start or success log at all):
3. `main.py` — add a start line before the upload loop begins, inside the
   `if _backup_service == "s3":` block:
   ```python
   logger.notice(f"Uploading {len(files_to_upload)} file(s) to S3")
   ```
4. `main.py` — add a success line after the upload loop completes without
   a `sys.exit`:
   ```python
   logger.notice(f"Uploaded {len(files_to_upload)} file(s) to S3 successfully")
   ```

### Everything else unchanged

Per-part progress (`multipartstream.py`), `"Old backups removed"`, and
`S3Remover`'s per-object deletion log all remain `logger.info` — they do
not reach Telegram, matching current (post-fix) behavior.

## Testing

No automated test suite exists in this repo (consistent with the rest of
this branch). Verification is manual: run a backup with
`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` configured and confirm exactly two
Telegram messages arrive for a successful streaming run (start, then
`[done]`), exactly two for a successful `SKIP_BACKUP` run ("Uploading N
file(s)", then "Uploaded N file(s) successfully"), and that per-part
progress lines do not appear in Telegram while still appearing in the
console/log file.
