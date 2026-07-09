"""
backend/pipeline/scoring.py

Implements the metadata component of PRD Section 8 (document scoring).

Public interface:

    calculate_metadata_score(extracted_metadata: dict, profile: dict) -> float

        extracted_metadata: output of metadata_extraction.extract_metadata(),
            i.e. {field_name: {"value": str|None, "confidence": float}}
        profile: the document profile dict (profiles/*.py), specifically
            uses profile["metadata_fields"] = {snake_case_key: "high"|"medium"|"low"}

        Returns a normalized score in [0.0, 1.0]:

            metadata_score = sum(priority_weight * confidence)
                              / sum(all possible priority weights for the profile)

        A profile with no metadata_fields (or all-zero weights) returns 0.0
        rather than raising a ZeroDivisionError.

Contract notes:
    - Missing/unfound fields (value=None, confidence=0.0) contribute 0
      and never raise.
    - The mapping between extracted_metadata's Title Case field names and
      profile["metadata_fields"]'s snake_case keys is derived, not looked
      up from a separate table:
          "Invoice Number" -> "invoice_number"
      via field_name.lower().replace(" ", "_").
    - If a derived key has no entry in profile["metadata_fields"], that
      field is skipped (contributes 0) rather than raising -- this keeps
      scoring resilient to profile/extraction drift instead of crashing
      the whole pipeline on one bad field.
"""

from backend import config


def _derive_metadata_key(field_name: str) -> str:
    """'Invoice Number' -> 'invoice_number'"""
    return field_name.lower().replace(" ", "_")


def calculate_metadata_score(extracted_metadata: dict, profile: dict) -> float:
    metadata_fields = profile.get("metadata_fields", {})

    # Denominator: total possible weight for this profile, independent of
    # what extraction actually found. This is what "fully complete, fully
    # confident extraction" would sum to.
    max_possible = sum(
        config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        for priority in metadata_fields.values()
    )

    if max_possible == 0:
        # No scorable fields defined for this profile (or config has no
        # weights) -- nothing to normalize against.
        return 0.0

    earned = 0.0
    for field_name, result in extracted_metadata.items():
        metadata_key = _derive_metadata_key(field_name)
        priority = metadata_fields.get(metadata_key)
        if priority is None:
            # Field extracted but not registered for scoring in this
            # profile (shouldn't happen once profiles are aligned, but
            # don't let it crash the pipeline).
            continue

        weight = config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        confidence = result.get("confidence", 0.0) or 0.0
        earned += weight * confidence

    return earned / max_possible