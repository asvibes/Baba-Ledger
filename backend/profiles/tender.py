"""Tender document profile (PRD Section 7.2)."""

PROFILE = {
    "type": "tender",
    "display_name": "Tender Document",
    "keywords": [
        "tender notice", "tender number", "bid submission", "eligibility criteria",
        "scope of work", "estimated project cost", "completion period",
        "earnest money deposit", "emd", "pre-bid meeting", "bidder",
    ],
    "structural_patterns": [
        r"tender\s*(no\.?|number|id)\s*[:\-]",
        r"bid\s*submission\s*date\s*[:\-]",
        r"eligibility\s*criteria",
        r"scope\s*of\s*work",
    ],
    "metadata_fields": {
        "tender_number": "high",
        "project_name": "medium",
        "client": "medium",
        "estimated_project_cost": "high",
        "bid_submission_date": "high",
        "completion_period": "high",
    },
    "semantic_anchors": [
        "tender", "bid", "submission deadline", "eligibility", "scope of work",
        "technical requirements", "penalty", "earnest money", "contract award",
    ],
    "highlight_focus": [
        "scope of work", "eligibility criteria", "submission deadlines",
        "technical requirements", "penalty clauses",
    ],
}
