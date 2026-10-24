import hashlib
from uuid import UUID
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from app.services.documents.storage_backend import DocumentStorageBackend

from app.core.config import get_settings, ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS, PREFERRED_CONTENT_TYPES

settings = get_settings()


@dataclass
class StoredFile:
    original_name: str
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
    def __init__(self, base_dir: Path = settings.documents_storage_dir):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, upload: UploadFile, document_id: UUID) -> StoredFile:
        if not upload.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required",
            )

        original_name = Path(upload.filename).name

        if len(original_name) > settings.documents_max_filename_length:
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
        head = upload.file.read(settings.documents_signature_read_bytes)
        upload.file.seek(0)

        if not _validate_file_signature(extension, head):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File signature does not match {extension}",
            )

        stored_name = str(document_id)
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
                    if total_size > settings.documents_max_file_size_bytes:
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
            content_type=PREFERRED_CONTENT_TYPES[extension],
            size_bytes=total_size,
            sha256=digest.hexdigest(),
        )

    def build_path(self, document_id: UUID) -> Path:
        return self.base_dir / str(document_id)

    def delete(self, document_id: UUID) -> None:
        path = self.build_path(document_id)
        path.unlink(missing_ok=True)