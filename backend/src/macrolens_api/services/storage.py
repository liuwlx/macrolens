from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO

import boto3
from botocore.client import BaseClient

from ..config import get_settings


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    uri: str
    sha256: str
    byte_size: int
    content_type: str


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )

    async def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        digest = sha256(data).hexdigest()
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return StoredObject(
            key=key,
            uri=f"s3://{self.settings.s3_bucket}/{key}",
            sha256=digest,
            byte_size=len(data),
            content_type=content_type,
        )

    async def get_bytes(self, key: str) -> bytes:
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.settings.s3_bucket, Key=key)
        body: BinaryIO = response["Body"]
        return await asyncio.to_thread(body.read)

    def presigned_get(self, key: str, expires_seconds: int = 900) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
