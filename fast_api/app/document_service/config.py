import os
from pathlib import Path

# Base directory where uploaded files are stored.
# Keep this configurable for different environments.
DOCUMENTS_STORAGE_DIR = Path(
    os.getenv("DOCUMENTS_STORAGE_DIR", "uploaded_documents")
)

# Max upload size per file (default: 10 MB).
MAX_FILE_SIZE_BYTES = int(
    os.getenv("DOCUMENTS_MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024))
)

# Allowed file extensions for this learning module.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Canonical media type we serve back during download.
PREFERRED_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

# Accepted upload media types by extension.
# application/octet-stream is included because some clients send generic content type.
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
}

MAX_FILENAME_LENGTH = int(
    os.getenv("DOCUMENTS_MAX_FILENAME_LENGTH", "180")
)

SIGNATURE_READ_BYTES = int(
    os.getenv("DOCUMENTS_SIGNATURE_READ_BYTES", "4096")
)

RETENTION_DAYS_SOFT_DELETED = int(
    os.getenv("DOCUMENTS_RETENTION_DAYS_SOFT_DELETED", "30")
)

STORAGE_BACKEND = os.getenv("DOCUMENTS_STORAGE_BACKEND", "local").lower()

S3_BUCKET_NAME = os.getenv("DOCUMENTS_S3_BUCKET_NAME", "")
S3_REGION = os.getenv("DOCUMENTS_S3_REGION", "ap-south-1")
S3_ENDPOINT_URL = os.getenv("DOCUMENTS_S3_ENDPOINT_URL", "").strip() or None
S3_PRESIGNED_TTL_SECONDS = int(
    os.getenv("DOCUMENTS_S3_PRESIGNED_TTL_SECONDS", "300")
)

INDEX_QUEUE_BATCH_SIZE = int(os.getenv("DOCUMENTS_INDEX_QUEUE_BATCH_SIZE", "20"))
INDEX_MAX_ATTEMPTS = int(os.getenv("DOCUMENTS_INDEX_MAX_ATTEMPTS", "5"))

INDEX_RETRY_BASE_SECONDS = int(os.getenv("DOCUMENTS_INDEX_RETRY_BASE_SECONDS", "30"))
INDEX_RETRY_MAX_SECONDS = int(os.getenv("DOCUMENTS_INDEX_RETRY_MAX_SECONDS", "900"))
INDEX_DEAD_STATUS = "dead"