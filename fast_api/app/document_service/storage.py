import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from app.document_service.storage_backend import DocumentStorageBackend

from app.document_service.config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    DOCUMENTS_STORAGE_DIR,
    MAX_FILE_SIZE_BYTES,
    PREFERRED_CONTENT_TYPES,
    MAX_FILENAME_LENGTH,
    SIGNATURE_READ_BYTES,
)


@dataclass
class StoredFile:
    original_name: str
    stored_name: str
    content_type: str
    size_bytes: int
    sha256: str

def _looks_like_pdf(head: bytes) -> bool:
    return head.startswith(b"%PDF-")


def _looks_like_docx(head: bytes) -> bool:
    # DOCX is a ZIP-based format; most valid files start with PK\x03\x04
    return head.startswith(b"PK\x03\x04")


def _looks_like_text(head: bytes) -> bool:
    # Allow UTF-8 text (including empty text files).
    if not head:
        return True
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _validate_file_signature(extension: str, head: bytes) -> bool:
    if extension == ".pdf":
        return _looks_like_pdf(head)
    if extension == ".docx":
        return _looks_like_docx(head)
    if extension == ".txt":
        return _looks_like_text(head)
    return False    


class LocalDocumentStorage(DocumentStorageBackend):
    def __init__(self, base_dir: Path = DOCUMENTS_STORAGE_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, upload: UploadFile) -> StoredFile:
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

        if not _validate_file_signature(extension, head):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File signature does not match {extension}",
            )

        stored_name = f"{uuid.uuid4().hex}{extension}"
        destination = self.base_dir / stored_name

        total_size = 0
        digest = hashlib.sha256()

        try:
            upload.file.seek(0)

            with destination.open("wb") as output:
                while True:
                    chunk = upload.file.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break

                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        output.close()
                        destination.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="File too large",
                        )

                    digest.update(chunk)
                    output.write(chunk)
        except OSError:
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store file",
            )
        finally:
            upload.file.close()

        return StoredFile(
            original_name=original_name,
            stored_name=stored_name,
            content_type=PREFERRED_CONTENT_TYPES[extension],
            size_bytes=total_size,
            sha256=digest.hexdigest(),
        )

    def build_path(self, stored_name: str) -> Path:
        return self.base_dir / stored_name

    def delete(self, stored_name: str) -> None:
        path = self.build_path(stored_name)
        path.unlink(missing_ok=True)