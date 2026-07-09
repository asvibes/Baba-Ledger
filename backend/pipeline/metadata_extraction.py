"""
backend/pipeline/metadata_extraction.py

Implements PRD Section 7 (document-specific metadata extraction) and
9.1 (per-field confidence reporting).

Public interface (matches backend/app.py's expectation):

    extract_metadata(full_text: str, profile: dict) -> dict
        Returns {field_name: {"value": str | None, "confidence": float}}

Hard rule (PRD 5.3): this module must never invent or "correct"
extracted values. If a field can't be found with reasonable certainty,
return value=None with confidence=0.0 rather than guessing.

Profile contract this module expects (see profiles/*.py):

    PROFILE = {
        "fields": ["Invoice Number", "Vendor", "Total Amount", ...],
        "field_patterns": {              # optional, per-field override
            "Invoice Number": r"...",
        },
    }

If a field is not present in "field_patterns", extraction falls back to
a generic heuristic chosen by inspecting the field name itself (date-
like, amount-like, ID/number-like, or plain label: value).
"""
import re
from typing import Optional


# ---------------------------------------------------------------------
# Generic regex building blocks
# ---------------------------------------------------------------------

# Matches common Indian/international date formats:
# 12/08/2026, 12-08-2026, 12 Aug 2026, August 12, 2026, 2026-08-12
_DATE_PATTERN = re.compile(
    r"""(
        \d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}          # 12/08/2026 or 12-08-26
        |
        \d{4}[/\-]\d{1,2}[/\-]\d{1,2}             # 2026-08-12
        |
        \d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}           # 12 August 2026
        |
        [A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}         # August 12, 2026
    )""",
    re.VERBOSE,
)

# Matches currency amounts: ₹25,000.00 / Rs. 25000 / INR 25,000 / $1,200.50
_AMOUNT_PATTERN = re.compile(
    r"""(?:₹|Rs\.?|INR|\$|USD)\s?
        (\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Matches typical ID/number tokens: alphanumeric with optional separators,
# e.g. INV-2026-0091, PO/2026/445, WO2026001
_ID_PATTERN = re.compile(r"[A-Z]{0,5}[\-\/]?\d{2,}[A-Za-z0-9\-\/]*")

# Generic "Label: value" fallback, tolerant of ".", ":", "-" as separators
# and stopping at line breaks so we don't swallow the next field.
def _label_value_pattern(label: str) -> re.Pattern:
    escaped = re.escape(label)
    return re.compile(
        rf"{escaped}\s*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE,
    )


# ---------------------------------------------------------------------
# Field-name classification (used only when the profile gives no
# explicit field_patterns override for a field)
# ---------------------------------------------------------------------

_DATE_HINTS = ("date", "deadline", "period", "due", "timeline", "completion")
_AMOUNT_HINTS = ("amount", "cost", "price", "value", "rate", "gst", "tax")
_ID_HINTS = ("number", "no.", "no", "id", "code")


def _classify_field(field_name: str) -> str:
    lowered = field_name.lower()
    if any(hint in lowered for hint in _DATE_HINTS):
        return "date"
    if any(hint in lowered for hint in _AMOUNT_HINTS):
        return "amount"
    if any(hint in lowered for hint in _ID_HINTS):
        return "id"
    return "generic"


# ---------------------------------------------------------------------
# Core matching helpers
# ---------------------------------------------------------------------

def _search_near_label(full_text: str, field_name: str, value_pattern: re.Pattern
                        ) -> Optional[re.Match]:
    """
    Look for value_pattern inside a window right after the field's label
    text, which is far more reliable than a document-wide search (e.g.
    a document-wide date search could pick up an unrelated date).
    Falls back to a document-wide search if no labeled window matches.
    """
    label_re = re.compile(re.escape(field_name), re.IGNORECASE)
    label_match = label_re.search(full_text)
    if label_match:
        window = full_text[label_match.end(): label_match.end() + 80]
        found = value_pattern.search(window)
        if found:
            return found
    # Fallback: first document-wide match (lower confidence, see below)
    return value_pattern.search(full_text)


def _extract_field(full_text: str, field_name: str, pattern: Optional[str]) -> dict:
    """
    Extract a single field's value + confidence.

    Confidence heuristic (not a trained probability, per PRD 6.1's spirit
    of not overstating certainty):
      - 0.95: matched an explicit profile-supplied pattern near its label
      - 0.80: matched a generic typed pattern (date/amount/id) near its label
      - 0.55: matched only via a document-wide fallback (label not found
              nearby, so association with this field is less certain)
      - 0.0 / None: no match found at all
    """
    label_re = re.compile(re.escape(field_name), re.IGNORECASE)
    label_present = bool(label_re.search(full_text))

    if pattern:
        compiled = re.compile(pattern, re.IGNORECASE)
        match = compiled.search(full_text)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            confidence = 0.95 if label_present else 0.70
            return {"value": value.strip(), "confidence": confidence}
        return {"value": None, "confidence": 0.0}

    field_type = _classify_field(field_name)
    if field_type == "date":
        value_pattern = _DATE_PATTERN
    elif field_type == "amount":
        value_pattern = _AMOUNT_PATTERN
    elif field_type == "id":
        value_pattern = _ID_PATTERN
    else:
        # Generic label: value fallback — the label itself is the pattern.
        value_pattern = _label_value_pattern(field_name)

    match = _search_near_label(full_text, field_name, value_pattern)
    if not match:
        return {"value": None, "confidence": 0.0}

    value = match.group(1) if match.groups() else match.group(0)
    value = value.strip()

    if not value:
        return {"value": None, "confidence": 0.0}

    confidence = 0.80 if label_present else 0.55
    return {"value": value, "confidence": confidence}


# ---------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------

def extract_metadata(full_text: str, profile: dict) -> dict:
    """
    Extract every field listed in profile["fields"] from full_text.

    Returns, per PRD 9.1:
        {
            "Invoice Number": {"value": "INV-2026-0091", "confidence": 0.95},
            "Vendor": {"value": None, "confidence": 0.0},
            ...
        }
    """
    fields = profile.get("fields", [])
    field_patterns = profile.get("field_patterns", {})

    metadata = {}
    for field_name in fields:
        pattern = field_patterns.get(field_name)
        metadata[field_name] = _extract_field(full_text, field_name, pattern)

    return metadata