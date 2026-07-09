"""
Pipeline Stage 2: Detect whether each page is text-based or scanned
(PRD Section 5.1).

Routing is per-page, not per-document, because real-world bundles mix
scanned and digital pages in the same file. A secondary sanity check
screens for corrupted/garbled extraction (e.g. broken font encodings)
so garbage text isn't mistaken for valid text.
"""

import re
from dataclasses import dataclass
from enum import Enum

from .. import config


class PageType(Enum):
    TEXT_BASED = "text_based"
    SCANNED = "scanned"


@dataclass
class PageRoutingResult:
    page_number: int
    page_type: PageType
    raw_text: str


# A page whose extracted text is mostly non-printable / replacement
# characters is almost certainly a broken extraction, not real text -
# route it to OCR rather than trusting it.
_GARBLED_CHAR_RE = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")


def _looks_garbled(text: str) -> bool:
    if not text:
        return False
    garbled_count = len(_GARBLED_CHAR_RE.findall(text))
    return garbled_count / max(len(text), 1) > 0.05


def route_page(page_number: int, extracted_text: str) -> PageRoutingResult:
    """
    Decide whether a single page should be treated as text-based or
    routed to OCR.

    Production implementation extracts `extracted_text` via PyMuPDF
    (page.get_text()); this module only needs the resulting string, so
    it stays extraction-library-agnostic.
    """
    text = extracted_text or ""

    if len(text.strip()) < config.MIN_TEXT_CHARS_PER_PAGE:
        return PageRoutingResult(page_number, PageType.SCANNED, text)

    if _looks_garbled(text):
        return PageRoutingResult(page_number, PageType.SCANNED, text)

    return PageRoutingResult(page_number, PageType.TEXT_BASED, text)


def route_document(pages_text: list[str]) -> list[PageRoutingResult]:
    """Route every page in a document. pages_text[i] is page i+1's extracted text."""
    return [route_page(i + 1, text) for i, text in enumerate(pages_text)]