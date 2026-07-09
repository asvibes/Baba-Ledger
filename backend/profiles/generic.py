"""
Generic / Unknown fallback profile (PRD Section 8.4).
Used when Classification Strength is Low, both as the standalone
profile for genuinely unclassifiable documents and blended in
alongside the highest-ranked profile when a user chooses to continue
past a Low-Strength warning (PRD Section 6.1).
"""

PROFILE = {
    "type": "generic",
    "display_name": "Unknown / General",
    "keywords": [
        "payment", "deadline", "required", "agreement", "amount",
        "notice", "due", "obligation", "important",
    ],
    "structural_patterns": [
        r"\bdate\s*[:\-]",
        r"amount\s*[:\-]",
    ],
    # Generic metadata: dates, money, emails, phone numbers, organizations (PRD 8.4)
    "metadata_fields": {
        "dates": "medium",
        "money_amounts": "high",
        "emails": "low",
        "phone_numbers": "low",
        "organizations": "medium",
    },
    "semantic_anchors": [
        "payment", "deadline", "required", "agreement", "amount",
        "notice", "due", "obligation", "important",
    ],
    "highlight_focus": [
        "dates", "amounts", "obligations", "notices",
    ],
}
