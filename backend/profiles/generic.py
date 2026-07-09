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
    
    "fields": [
    "Dates",
    "Money Amounts",
    "Emails",
    "Phone Numbers",
    "Organizations",
],

"field_patterns": {
    "Dates": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "Money Amounts": r"(?:₹|Rs\.?|INR|\$)?\s*\d+(?:,\d{3})*(?:\.\d{2})?",
    "Emails": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "Phone Numbers": r"\b(?:\+91[- ]?)?[6-9]\d{9}\b",
    "Organizations": r"\b(?:Ltd|Limited|Pvt\.?\s*Ltd\.?|LLP|Corporation|Company|Inc\.?)\b",
},
    
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
