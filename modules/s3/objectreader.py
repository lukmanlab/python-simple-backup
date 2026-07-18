import io
from modules.s3.config import S3Config

class S3ObjectReader(io.RawIOBase):
    """Minimal streaming reader for a single S3 object, used so tarfile
    can add it without downloading the whole thing to disk first"""
    
    def __init__(self, source_key: str):
        self.s3_client = S3Config()
        self.body = self.s3_client.get_object(source_key=source_key)

    def readinto(self, b):
        data = self.body.read(len(b))
        n = len(data)
        b[:n] = data
        return n
    
    def readable(self):
        return True