import io
import json
import os
from modules.s3.config import S3Config
import settings
from utils.logger import logger

class S3MultipartStream(io.RawIOBase):
    """File-like object that streams writes into an s3 multipart upload,
    with checkpoint support, so an interupted upload can be resumed."""

    def __init__(self, checkpoint_path=None):
        self.s3_config = S3Config()
        self.s3_client = self.s3_config.create_client()
        self.s3_bucket = self.s3_config.bucket_name
        self.s3_prefix = self.s3_config.prefix
        self.buffer = bytearray()
        self.bytes_written = 0
        self.checkpoint_path = checkpoint_path

        state = self._load_checkpoint()
        if state:
            self.upload_id = state["upload_id"]
            self.parts = state["parts"]
            self.part_number = state["parts"][-1]["PartNumber"] + 1 if state["parts"] else 1
            logger.info(f"[resume] continuing upload_id={self.upload_id}, "
                        f"{len(self.parts)} parts already uploaded")
        else:
            self.upload_id = self.s3_config.create_multipart_upload()
            self.parts = []
            self.part_number = 1
            self._save_checkpoint()

    def _load_checkpoint(self):
        if self.checkpoint_path and os.path.exists(self.checkpoint_path):
            with open(self.checkpoint_path) as f:
                data: dict = json.load(f)
            if data.get("bucket") == self.s3_bucket and data.get("key") == self.s3_prefix:
                return data
        return None
    
    def _save_checkpoint(self):
        if not self.checkpoint_path:
            return
        with open(self.checkpoint_path, "w") as f:
            json.dump({
                "bucket": self.s3_bucket,
                "key": self.s3_prefix,
                "upload_id": self.upload_id,
                "parts": self.parts,
            }, f)

    def _clear_checkpoint(self):
        if self.checkpoint_path and os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)

    def write(self, b):
        self.buffer.extend(b)
        self.bytes_written += len(b)
        while len(self.buffer) >= settings.MULTIPART_SIZE:
            self._flush_part(settings.MULTIPART_SIZE)
        return len(b)
    
    def _flush_part(self, size):
        chunk = bytes(self.buffer[:size])
        del self.buffer[:size]
        response = self.s3_config.upload_part(
            part_number=self.part_number,
            upload_id=self.upload_id,
            body_chunk=chunk,
        )
        self.parts.append({"ETag": response["ETag"], "PartNumber": self.part_number})
        self._save_checkpoint()
        logger.info(f"[part {self.part_number}] uploaded {len(chunk)/1024/1024:.1f} MB"
                    f"(Total so far: {self.bytes_written/1024/1024:.1f} MB)")
        self.part_number += 1

    def close(self):
        try:
            if self.buffer:
                self._flush_part(len(self.buffer))
            self.s3_config.complete_multipart_upload(
                upload_id=self.upload_id,
                parts=self.parts
            )
            self._clear_checkpoint()
            logger.info(f"[done] {self.s3_prefix} complete, {self.bytes_written/1024/1024:.1f} MB total")
        except Exception:
            logger.error("[error] upload failed, checkpoint preserved for resume "
                         "(multipart upload NOT aborted so it can be resumed)")
            raise
        super().close()
    
    def abort(self):
        """Call explicitly if you want to give up entirely (not just pause)."""
        self.s3_config.abort_multipart_upload(upload_id=self.upload_id)
        self._clear_checkpoint()