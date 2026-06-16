import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config
from fastapi import HTTPException, UploadFile, status

from app.document_service.config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILENAME_LENGTH,
    PREFERRED_CONTENT_TYPES,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    SIGNATURE_READ_BYTES,
)
from app.document_service.storage_backend import DocumentStorageBackend


@dataclass
class S3StoredFile:
    original_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    sha256: str


def _looks_like_pdf(head: bytes) -> bool:
    return head.startswith(b"%PDF-")


def _looks_like_docx(head: bytes) -> bool:
    return head.startswith(b"PK\x03\x04")


def _looks_like_text(head: bytes) -> bool:
    if not head:
        return True
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _validate_signature(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return _looks_like_pdf(head)
    if ext == ".docx":
        return _looks_like_docx(head)
    if ext == ".txt":
        return _looks_like_text(head)
    return False


class S3DocumentStorage(DocumentStorageBackend):
    def __init__(self):
        if not S3_BUCKET_NAME:
            raise RuntimeError("DOCUMENTS_S3_BUCKET_NAME is required for s3 backend")

        self.bucket = S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            region_name=S3_REGION,
            endpoint_url=S3_ENDPOINT_URL,
            config=Config(signature_version="s3v4"),
        )

    def save(self, upload: UploadFile) -> S3StoredFile:
        if not upload.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required",
            )

        original_name = Path(upload.filename).name
        if len(original_name) > MAX_FILENAME_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename too long",
            )

        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF, DOCX, and TXT files are allowed",
            )

        content_type = upload.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES[extension]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type for {extension} file",
            )

        upload.file.seek(0)
        head = upload.file.read(SIGNATURE_READ_BYTES)
        upload.file.seek(0)
        if not _validate_signature(extension, head):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File signature does not match {extension}",
            )

        stored_name = f"{uuid.uuid4().hex}{extension}"

        total_size = 0
        digest = hashlib.sha256()
        chunks: list[bytes] = []

        try:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large",
                    )
                digest.update(chunk)
                chunks.append(chunk)

            body = b"".join(chunks)
            self.client.put_object(
                Bucket=self.bucket,
                Key=stored_name,
                Body=body,
                ContentType=PREFERRED_CONTENT_TYPES[extension],
            )

        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store file in S3",
            )
        finally:
            upload.file.close()

        return S3StoredFile(
            original_name=original_name,
            stored_name=stored_name,
            content_type=PREFERRED_CONTENT_TYPES[extension],
            size_bytes=total_size,
            sha256=digest.hexdigest(),
        )

    def build_path(self, stored_name: str) -> Path:
        # Not used in S3 mode. Kept for protocol compatibility.
        return Path(stored_name)

    def delete(self, stored_name: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=stored_name)
        except Exception:
            # Best-effort delete.
            return

    def generate_download_url(
        self,
        *,
        stored_name: str,
        original_name: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket,
                "Key": stored_name,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": f'attachment; filename="{original_name}"',
            },
            ExpiresIn=expires_in_seconds,
        )