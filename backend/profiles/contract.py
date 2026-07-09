"""Contract profile (PRD Section 7.3)."""

PROFILE = {
    "type": "contract",
    "display_name": "Contract",
    "keywords": [
        "agreement", "party a", "party b", "term", "termination",
        "liability", "warranty", "indemnity", "confidentiality",
        "governing law", "force majeure",
    ],
    "structural_patterns": [
        r"this\s+agreement\s+is\s+made",
        r"party\s+a\b",
        r"party\s+b\b",
        r"term\s+of\s+this\s+agreement",
        r"termination\s+of\s+this\s+agreement",
    ],
    "metadata_fields": {
        "contract_number": "high",
        "parties_involved": "high",
        "effective_date": "high",
        "contract_duration": "medium",
        "payment_terms": "high",
    },
    "semantic_anchors": [
        "termination", "liability", "confidentiality", "renewal",
        "warranty", "breach", "indemnity", "governing law",
    ],
    "highlight_focus": [
        "liability clauses", "termination clauses", "warranty clauses",
        "payment conditions", "penalties",
    ],
}
