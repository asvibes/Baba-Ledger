"""
Structured failure handling (PRD 14.4). Every known failure case gets
its own exception type so app.py can return a meaningful error instead
of a generic 500 / silent crash.
"""


class PipelineError(Exception):
    """Base class for all expected, handled pipeline failures."""
    user_message = "Something went wrong while processing this document."
    status_code = 500


class FileTooLargeError(PipelineError):
    status_code = 413

    def __init__(self, size_mb: float, max_mb: float):
        self.user_message = (
            f"This file is {size_mb:.1f} MB, which exceeds the {max_mb:.0f} MB limit. "
            f"Please upload a smaller file."
        )
        super().__init__(self.user_message)


class TooManyPagesError(PipelineError):
    status_code = 413

    def __init__(self, page_count: int, max_pages: int):
        self.user_message = (
            f"This document has {page_count} pages, which exceeds the {max_pages}-page limit."
        )
        super().__init__(self.user_message)


class UnsupportedFileTypeError(PipelineError):
    status_code = 400

    def __init__(self, extension: str):
        self.user_message = f"Unsupported file type '{extension}'. Version 1 supports PDF only."
        super().__init__(self.user_message)


class PasswordProtectedPDFError(PipelineError):
    status_code = 422
    user_message = "This PDF is password-protected. Please remove the password and re-upload."


class CorruptedPDFError(PipelineError):
    status_code = 422
    user_message = "This PDF appears to be corrupted and could not be read."


class OCRFailureError(PipelineError):
    status_code = 500

    def __init__(self, page_number: int):
        self.user_message = f"OCR failed on page {page_number}. Other pages were processed normally."
        super().__init__(self.user_message)


class UnsupportedLanguageError(PipelineError):
    status_code = 422
    user_message = (
        "This document appears to be in an unsupported language. "
        "Version 1 currently supports English documents only."
    )


class ModelLoadingError(PipelineError):
    status_code = 503
    user_message = "The analysis service is still starting up. Please try again in a moment."


class ReportGenerationError(PipelineError):
    status_code = 500
    user_message = "The document was analyzed, but the report could not be generated. Please try again."
