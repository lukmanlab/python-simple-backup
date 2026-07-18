from datetime import datetime, timedelta
from modules.s3.config import S3Config
from utils.logger import logger
from botocore.exceptions import ClientError

class S3Remover():
  def __init__(self) -> None:
    self.s3_config = S3Config()
    self.s3_client = self.s3_config.create_client()
    self.bucket_name = self.s3_config.bucket_name
    self.prefix = self.s3_config.prefix
    self.retention = self.s3_config.retention

  def remove_objects(self):
    try:
      response = self.s3_client.list_objects_v2(
        Bucket=self.bucket_name,
        Prefix=self.prefix
      )
    except ClientError as e:
      logger.error(f"Error listing objects for retention cleanup: {e}")
      return

    contents = response.get('Contents')
    if not contents:
      return

    current_time = datetime.now(tz=contents[0]['LastModified'].tzinfo)
    retention_date = current_time - timedelta(days=int(self.retention))

    for item in contents:
      if item['LastModified'] < retention_date and len(contents) > 1:
        # clean up
        try:
          self.s3_client.delete_object(
            Bucket=self.bucket_name,
            Key=item['Key'],
          )

          logger.info(f"Deleting object {item['Key']} success!")

        except ClientError as e:
          logger.error(f"Error deleting object: {e}")