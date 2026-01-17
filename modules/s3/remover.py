from datetime import datetime, timedelta
import os
from modules.s3.config import S3Config
from utils.logger import logger
from botocore.exceptions import ClientError

class S3Remover():
  def __init__(self) -> None:
    self.s3_config = S3Config()
    self.s3_client = self.s3_config.create_client()
    self.bucket_name = self.s3_config.bucket_name
    self.prefix = self.s3_config.prefix
    self.retention = os.environ.get("BUCKET_RETENTION_DAYS", "0")

  def remove_objects(self):
    response = self.s3_client.list_objects_v2(
      Bucket=self.bucket_name,
      Prefix=self.prefix
    )

    current_time = datetime.now(tz=response['Contents'][0]['LastModified'].tzinfo)
    retention_date = current_time - timedelta(days=int(self.retention))

    for item in response['Contents']:
      if item['LastModified'] < retention_date and len(response['Contents']) > 1:
        # clean up
        try:
          self.s3_client.delete_object(
            Bucket=os.environ["S3_BUCKET_NAME"],
            Key=item['Key'],
          )

          logger.info(f"Deleting object {item['Key']} success!")

        except ClientError as e:
          logger.error(f"Error deleting object: {e}")