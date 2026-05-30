# app/Repositories/S3Client.py
"""
S3 / MinIO client. Same interface as before — just moved into Repositories.
"""
import os

import boto3
from botocore.client import Config as BotoConfig


# Read from environment
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "asr-bucket")
S3_REGION = os.getenv("S3_REGION", "us-east-1")


class S3Client:
    def __init__(self):
        self.bucket = S3_BUCKET
        self.client = boto3.client("s3",
                                   endpoint_url=S3_ENDPOINT,
                                   aws_access_key_id=S3_ACCESS_KEY,
                                   aws_secret_access_key=S3_SECRET_KEY,
                                   region_name=S3_REGION,
                                   config=BotoConfig(signature_version="s3v4"),)
    def download_file(self,s3_key:str,local_path:str)-> str:
        os.makedirs(os.path.dirname(local_path),exist_ok=True)
        self.client.download_file(self.bucket,s3_key,local_path)
        return local_path
    def upload_file(self,local_path:str,s3_key:str)-> str:
        self.client.upload_file(local_path,self.bucket,s3_key)
        return s3_key
    def upload_json_string(self,data:str,s3_key:str)-> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=data.encode("utf-8"),
            ContentType="application/json",
        )
        return s3_key
    


