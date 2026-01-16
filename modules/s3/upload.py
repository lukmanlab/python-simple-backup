import os
import boto3
from botocore.exceptions import ClientError
import requests
from utils.logger import logger
from boto3.session import Config

session = boto3.Session(
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)

s3_client = session.client(
    service_name="s3",
    endpoint_url="https://is3.cloudhost.id",
    config=Config(signature_version='s3v4')
)

bucket_name = os.environ["S3_BUCKET_NAME"]

def create_presigned_post(
  object_name, fields=None, conditions=None, expiration=3600
):
    try:
        response = s3_client.generate_presigned_post(
            bucket_name,
            object_name,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.error(f"Create presigned error: {str(e)}")
        return None

    return response

def upload_to_s3(file_name: str, object_name):
  prefix_path = os.environ.get("S3_PREFIX_PATH", "default_s3")
  key = f"{prefix_path}/{object_name}"

  response = create_presigned_post(key)
  if response is None:
      exit(1)

  try:
    with open(file_name, 'rb') as f:
        files = {'file': (object_name, f)}
        http_response = requests.post(
            response['url'],
            data=response['fields'],
            files=files
        )
    
    if http_response.status_code == 204:
        logger.info("Upload successful")
        return True
    else:
        logger.error(f"Upload failed with status code: {http_response.status_code}")
        return False

  except Exception as e:
    logger.error(f"Upload to s3 error: {str(e)}")
    return False