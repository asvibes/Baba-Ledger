"""
Pipeline Stage 1: Upload PDF (PRD Section 5, stage 1).

Validates the incoming file (size, extension, page count, password
protection, corruption) before anything downstream touches it.
"""

from dataclasses import dataclass

from .. import config
from ..utils.errors import (
    CorruptedPDFError,
    PasswordProtectedPDFError,
    TooManyPagesError,
)
from ..utils.validators import sanitize_filename, validate_extension, validate_file_size


@dataclass
class IngestedDocument:
    original_filename: str
    safe_filename: str
    file_path: str
    page_count: int


def ingest_upload(file_path: str, original_filename: str, size_bytes: int) -> IngestedDocument:
    """
    Run all Stage-1 validation. Raises a PipelineError subclass on any
    known failure case (PRD 14.4) rather than letting an exception
    surface uncaught.
    """
    safe_name = sanitize_filename(original_filename)
    validate_extension(safe_name)
    validate_file_size(size_bytes)

    page_count = _open_and_count_pages(file_path)
    if page_count > config.MAX_PAGE_COUNT:
        raise TooManyPagesError(page_count, config.MAX_PAGE_COUNT)

    return IngestedDocument(
        original_filename=original_filename,
        safe_filename=safe_name,
        file_path=file_path,
        page_count=page_count,
    )


def _open_and_count_pages(file_path: str) -> int:
    """
    Open the PDF to confirm it isn't corrupted/password-protected and
    return its page count.

    Production implementation uses PyMuPDF (fitz):

        import fitz
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise CorruptedPDFError() from e
        if doc.needs_pass:
            raise PasswordProtectedPDFError()
        return doc.page_count

    This sandbox has no network access to install PyMuPDF, so pypdf
    (already available) is used here instead. Swap this function body
    for the PyMuPDF version above when running with full dependencies -
    everything downstream only depends on the returned page_count.
    """
    import pypdf
    from pypdf.errors import PdfReadError

    try:
        reader = pypdf.PdfReader(file_path)
    except PdfReadError as e:
        raise CorruptedPDFError() from e
    except Exception as e:
        raise CorruptedPDFError() from e

    if reader.is_encrypted:
        # pypdf can sometimes decrypt with an empty password; if it still
        # reports encrypted after that attempt, treat it as password-protected.
        try:
            result = reader.decrypt("")
            if result == 0:
                raise PasswordProtectedPDFError()
        except Exception:
            raise PasswordProtectedPDFError()

    return len(reader.pages)