from pathlib import Path
from typing import Protocol

from fastapi import UploadFile


class StoredFileLike(Protocol):
    original_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    sha256: str


class DocumentStorageBackend(Protocol):
    def save(self, upload: UploadFile) -> StoredFileLike:
        ...

    def build_path(self, stored_name: str) -> Path:
        ...

    def delete(self, stored_name: str) -> None:
        ...
    
    def generate_download_url(
        self,
        *,
        stored_name: str,
        original_name: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        ...    