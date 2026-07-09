"""
Pipeline Stage 4: Clean extracted text (PRD Section 5.3).

Hard rule: cleaning must never invent information. This module only
normalizes formatting - duplicate spaces, line breaks, invisible
characters. It never performs character substitution (e.g. 1 -> I,
0 -> O). Ambiguous/low-confidence characters are left as-is; that
uncertainty is surfaced later via per-field confidence scoring
(PRD 9.1), never silently corrected here.
"""

import re
import unicodedata

from .. import config

_INVISIBLE_CHARS_RE = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]"  # zero-width / soft-hyphen / BOM etc.
)
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")


def clean_text(raw_text: str) -> str:
    """
    Apply formatting-only normalization to a page/document's extracted text.
    Never changes what the characters ARE, only whitespace/invisible noise.
    """
    text = raw_text

    if config.STRIP_INVISIBLE_CHARS:
        text = _INVISIBLE_CHARS_RE.sub("", text)
        # NFC normalization recomposes accented characters split across
        # combining marks; it does not change which letters are present.
        text = unicodedata.normalize("NFC", text)

    if config.NORMALIZE_LINE_BREAKS:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _TRAILING_WS_RE.sub("\n", text)
        text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)

    text = _MULTI_SPACE_RE.sub(" ", text)

    return text.strip()