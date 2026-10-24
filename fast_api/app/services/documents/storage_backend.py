from pathlib import Path
from uuid import UUID
from typing import Protocol

from fastapi import UploadFile


class StoredFileLike(Protocol):
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str


class DocumentStorageBackend(Protocol):
    def save(self, upload: UploadFile, document_id: UUID) -> StoredFileLike:
        ...

    def build_path(self, document_id: UUID) -> Path:
        ...

    def delete(self, document_id: UUID) -> None:
        ...
    
    def generate_download_url(
        self,
        *,
        document_id: UUID,
        original_name: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        ...    