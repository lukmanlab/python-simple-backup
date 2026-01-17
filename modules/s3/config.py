from botocore.config import Config
import os
import boto3

from utils.logger import logger

class S3Config:
    def __init__(self):
        self._config = Config(signature_version='s3v4')
        self._session = boto3.Session()
        self.bucket_name = os.environ["S3_BUCKET_NAME"]
        self.prefix = os.environ["S3_PREFIX_PATH"]

    def create_client(self):
        """Creates and returns an S3 client with the configured settings"""
        try:
          self.endpoint_url = os.environ["S3_ENDPOINT"]
          self.bucket_name = os.environ["S3_BUCKET_NAME"]

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