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
- Do not reintroduce per-part progress spam to Telegram.
- Keep log severity semantically honest — a success should not be logged as
  a `WARNING`.

## Non-goals

- No change to what reaches Telegram on failure — `ERROR`/`CRITICAL` paths
  are already correct and untouched.
- Retention-cleanup detail (`"Old backups removed"`, per-object
  `"Deleting object ... success"` in `S3Remover`) stays `INFO`-only
  (console/file), not promoted to Telegram. These are operational detail,
  not run-outcome milestones.
- The "backup starting" log line stays `INFO`-only; only completion is
  promoted. One Telegram message per successful run, not two.

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

1. `modules/s3/multipartstream.py` — the `"[done] {key} complete, ..."`
   line in `close()` changes from `logger.info` to `logger.notice`. This is
   the authoritative "this archive is fully uploaded to S3" confirmation
   for the streaming backup path.
2. `main.py` — the `SKIP_BACKUP` path currently has no success log after
   its upload loop finishes. Add one after the `for file in
   files_to_upload:` loop completes without a `sys.exit`:
   ```python
   logger.notice(f"Uploaded {len(files_to_upload)} file(s) to S3 successfully")
   ```
   placed inside the `if _backup_service == "s3":` block, after the loop.

### Everything else unchanged

`main.py`'s "Streaming backup of ... as {key}" start message, per-part
progress (`multipartstream.py`), `"Old backups removed"`, and
`S3Remover`'s per-object deletion log all remain `logger.info` — they do
not reach Telegram, matching current (post-fix) behavior.

## Testing

No automated test suite exists in this repo (consistent with the rest of
this branch). Verification is manual: run a backup with
`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` configured and confirm exactly one
Telegram message arrives for a successful streaming run (the `[done]`
line), one for a successful `SKIP_BACKUP` run (the new "Uploaded N file(s)"
line), and that per-part progress lines do not appear in Telegram while
still appearing in the console/log file.
