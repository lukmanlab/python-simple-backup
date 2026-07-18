from botocore.config import Config
import settings
import boto3

from utils.logger import logger

class S3Config:
    def __init__(self):
        self._config = Config(signature_version='s3v4')
        self._session = boto3.Session()
        self.bucket_name = settings.S3_BUCKET_NAME
        self.prefix = settings.S3_PREFIX_PATH
        self.endpoint_url = settings.S3_ENDPOINT
        self.retention = settings.BUCKET_RETENTION_DAYS

    def create_client(self):
        """Creates and returns an S3 client with the configured settings"""
        try:
          create_client = self._session.client(
            service_name='s3',
            endpoint_url=self.endpoint_url,
            config=self._config
          )
          return create_client
        except KeyError as e:
          logger.error(f"Error creating s3 config", exc_info=True)
          return None

    def create_resource(self):
        """Creates and returns an S3 resource with the configured settings"""
        return self._session.resource(
            's3',
            endpoint_url=self.endpoint_url,
            config=self._config
        )

    def create_multipart_upload(self):
       response = self.create_client().create_multipart_upload(
          Bucket=self.bucket_name,
          Key=self.prefix
       )
       return response["UploadId"]
    
    def upload_part(self, part_number: any, upload_id: str, body_chunk: bytes):
       return self.create_client().upload_part(
            Bucket=self.bucket_name,
            Key=self.prefix,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=body_chunk,
       )
    
    def complete_multipart_upload(self, upload_id: str, parts: list):
       return self.create_client().complete_multipart_upload(
          Bucket=self.bucket_name,
          Key=self.prefix,
          UploadId=upload_id,
          MultipartUpload={"Parts": parts},
       )
    
    def abort_multipart_upload(self, upload_id: str):
       return self.create_client().abort_multipart_upload(
          Bucket=self.bucket_name,
          Key=self.prefix,
          UploadId=upload_id,
       )
