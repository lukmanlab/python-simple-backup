import io
from modules.s3.config import S3Config
import settings
from utils.logger import logger

class S3MultipartStream(io.RawIOBase):
    """File-like object that streams writes into an s3 multipart upload."""

    def __init__(self, key: str):
        self.s3_config = S3Config()
        self.s3_key = key
        self.buffer = bytearray()
        self.bytes_written = 0

        self.upload_id = self.s3_config.create_multipart_upload(self.s3_key)
        self.parts = []
        self.part_number = 1

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
            key=self.s3_key,
            part_number=self.part_number,
            upload_id=self.upload_id,
            body_chunk=chunk,
        )
        self.parts.append({"ETag": response["ETag"], "PartNumber": self.part_number})
        logger.info(f"[part {self.part_number}] uploaded {len(chunk)/1024/1024:.1f} MB"
                    f"(Total so far: {self.bytes_written/1024/1024:.1f} MB)")
        self.part_number += 1

    def close(self):
        try:
            if self.buffer:
                self._flush_part(len(self.buffer))
            self.s3_config.complete_multipart_upload(
                key=self.s3_key,
                upload_id=self.upload_id,
                parts=self.parts
            )
            logger.notice(f"[done] {self.s3_key} complete, {self.bytes_written/1024/1024:.1f} MB total")
        except Exception:
            logger.error(f"[error] upload failed, aborting multipart upload {self.upload_id}")
            try:
                self.abort()
            except Exception:
                logger.error(f"[error] failed to abort multipart upload {self.upload_id}", exc_info=True)
            raise
        super().close()

    def abort(self):
        """Abort the multipart upload, discarding any parts already uploaded."""
        self.s3_config.abort_multipart_upload(key=self.s3_key, upload_id=self.upload_id)
