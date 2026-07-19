from typing import Optional, Dict
import os
import time
import requests

from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

from modules.s3.config import S3Config
from utils.logger import logger

class S3Uploader:
  def __init__(self):
    self.s3_config = S3Config()
    self.bucket_name = self.s3_config.bucket_name
    self.s3_client = self.s3_config.create_client()

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

  def upload_file_v2(self, file_path: str, dst: str, max_retries: int = 3) -> bool:
      basename = os.path.basename(file_path)
      key = f"{dst}/{basename}"

      try:     
          file_size = os.path.getsize(file_path)
          if file_size == 0:
              logger.error(f"File is empty: {file_path}")
              return False
          
          logger.info(f"Starting upload of {basename} ({file_size/1024/1024:.2f} MB)")
          
          # Configure transfer settings (100MB chunks)
          chunk_size = 100 * 1024 * 1024
          config = TransferConfig(
              multipart_threshold=chunk_size,
              max_concurrency=4,
              multipart_chunksize=chunk_size,
              use_threads=True,
              max_io_queue=100,
              io_chunksize=256 * 1024
          )

          # Progress tracking
          bytes_seen = 0
          last_log = 0
          log_interval = 100 * 1024 * 1024  # Log every 100MB
          
          def progress_callback(bytes_transferred):
              nonlocal bytes_seen, last_log
              bytes_seen += bytes_transferred
              
              if bytes_seen - last_log >= log_interval or bytes_seen >= file_size:
                  percent = (bytes_seen / file_size) * 100
                  if percent >= 95:
                    logger.info(f"Progress: {bytes_seen/1024/1024:.2f} MB / {file_size/1024/1024:.2f} MB ({percent:.1f}%)")
                  last_log = bytes_seen

          # Retry logic
          for attempt in range(max_retries):
            try:
              bytes_seen = 0
              
              self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                key,
                Config=config,
                Callback=progress_callback,
                ExtraArgs={'ContentType': 'application/gzip'}
              )
              
              logger.info(f"Successfully uploaded {basename}")
              return True
                  
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                is_retryable = error_code == 'NoSuchUpload' or 'MissingContentLength' in str(e)
                
                if is_retryable and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Upload attempt {attempt + 1}/{max_retries} failed: {error_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    self._cleanup_incomplete_uploads(key)
                else:
                    logger.error(f"Upload failed after {attempt + 1} attempts: {error_code}")
                    raise
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Upload attempt {attempt + 1}/{max_retries} failed: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    self._cleanup_incomplete_uploads(key)
                else:
                    raise
          
          return False
      
      except Exception as e:
        logger.error(f"Upload failed for {basename}: {str(e)}", exc_info=True)
        return False

  def _cleanup_incomplete_uploads(self, key: str) -> None:
    try:
      response = self.s3_client.list_multipart_uploads(
          Bucket=self.bucket_name,
          Prefix=key
      )
      
      for upload in response.get('Uploads', []):
        if upload['Key'] == key:
          logger.info(f"Aborting incomplete upload: {upload['UploadId']}")
          self.s3_client.abort_multipart_upload(
              Bucket=self.bucket_name,
              Key=key,
              UploadId=upload['UploadId']
            )
    except Exception as e:
      logger.warning(f"Failed to cleanup incomplete uploads for {key}: {str(e)}")
