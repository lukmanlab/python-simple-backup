import os
from typing import Optional, Dict

import boto3
from boto3.session import Config
from botocore.exceptions import ClientError
import requests

from utils.logger import logger

class S3Uploader:
  def __init__(self,
    endpoint_url: str,
    bucket_name: str,
  ):
    self.bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")
    session = boto3.Session()
    self.s3_client = session.client(
      service_name="s3",
      endpoint_url=os.environ["S3_ENDPOINT"],
      config=Config(
        signature_version='s3v4'
      )
    )

  def create_presigned_post(self,
    object_name: str,
    fields: Optional[Dict] = None,
    conditions: Optional[list] = None,
    expiration: int = 3600
  ) -> Optional[Dict]:
    try:
      return self.s3_client.generate_presigned_post(
        self.bucket_name,
        object_name,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expiration
      )
    except ClientError as e:
      logger.error("Failed to generate presigned URL", exc_info=True)

  def upload_file(self, file_path: str, dst: str) -> bool:
    key = f"{dst}/{file_path}"

    try:
      response = self.create_presigned_post(key)
      if not response:
        return False

      basename = os.path.basename(file_path)

      with open(file_path, 'rb') as file_obj:
        files = {'file': (basename, file_obj)}

        http_response = requests.post(
          response['url'],
          data=response['fields'],
          files=files
        )

      if http_response.status_code == 204:
        logger.info(f"Upload {basename} successful to {key}")
        return True
      else:
        logger.error(f"Upload failed with status {http_response.status_code}: {http_response.text}")
        return False

    
    except Exception as e:
      logger.error(f"Error uploading file {file_path}", exc_info=True)
      return False

def create_s3_uploader() -> Optional[S3Uploader]:
  try:
    return S3Uploader(
      endpoint_url=os.environ.get("S3_ENDPOINT_URL", "https://s3.amazonaws.com"),
      bucket_name=os.environ["S3_BUCKET_NAME"]
    )

  except KeyError as e:
    logger.error(f"Missing required environment variable: {e}")
    return None