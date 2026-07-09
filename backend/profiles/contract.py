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
    
    "fields": [
    "Contract Number",
    "Parties Involved",
    "Effective Date",
    "Contract Duration",
    "Payment Terms",
],

"field_patterns": {
    "Contract Number": r"contract\s*(no\.?|number)\s*[:\-]?\s*(.+)",
    "Parties Involved": r"(party\s*a.*?|party\s*b.*?)",
    "Effective Date": r"effective\s*date\s*[:\-]?\s*(.+)",
    "Contract Duration": r"(term|duration)\s*[:\-]?\s*(.+)",
    "Payment Terms": r"payment\s*terms\s*[:\-]?\s*(.+)",
},
    
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
