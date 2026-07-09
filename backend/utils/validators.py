"""
Upload validation: filename sanitization and file-type/size checks (PRD 14.1).
"""

import re
from pathlib import Path

from backend import config

from .errors import (
    FileTooLargeError,
    UnsupportedFileTypeError,
)

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(filename: str) -> str:
    """Strip directory components and replace unsafe characters."""
    name = Path(filename).name  # drop any path traversal component
    name = _SAFE_FILENAME_RE.sub("_", name)
    if not name:
        name = "upload.pdf"
    return name


def validate_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in config.ACCEPTED_EXTENSIONS:
        raise UnsupportedFileTypeError(ext or "(none)")


def validate_file_size(size_bytes: int) -> None:
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        raise FileTooLargeError(size_mb, config.MAX_FILE_SIZE_MB)