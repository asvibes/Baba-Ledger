"""Invoice profile (PRD Section 7.1)."""

PROFILE = {
    "type": "invoice",
    "display_name": "Invoice",
    # PRD 6: keyword signals used for classification
    "keywords": [
        "invoice number", "invoice no", "tax invoice", "gst", "total amount",
        "amount due", "payment terms", "due date", "bill to", "vendor",
        "gstin", "hsn", "sac code",
    ],
    # PRD 6.1: structural patterns - deterministic layout cues, not AI predictions
    "structural_patterns": [
        r"invoice\s*(no\.?|number)\s*[:\-]",
        r"due\s*date\s*[:\-]",
        r"total\s*amount\s*(due)?\s*[:\-]",
        r"gst(in)?\s*[:\-]?\s*\d",
    ],
    # PRD 7.1: extracted metadata fields, with priority for the Metadata Score (PRD 8.2)
    "metadata_fields": {
        "invoice_number": "high",
        "vendor": "medium",
        "client": "medium",
        "invoice_date": "medium",
        "due_date": "high",
        "total_amount": "high",
        "gst_tax": "high",
        "payment_terms": "high",
    },
    # PRD 8.3: semantic anchor concepts for the Semantic Score
    "semantic_anchors": [
        "payment", "due date", "gst", "vendor", "invoice", "total amount",
        "penalty", "tax", "billing", "outstanding balance",
    ],
    # PRD 7.1: highlight / clause focus
    "highlight_focus": [
        "payment obligations", "due dates", "penalty clauses",
        "total amount", "tax information",
    ],
}
