"""Purchase Order profile (PRD Section 7.5)."""

PROFILE = {
    "type": "purchase_order",
    "display_name": "Purchase Order",
    "keywords": [
        "po number", "purchase order", "ordered materials", "unit price",
        "delivery date", "vendor", "quantity", "material details",
    ],
    "structural_patterns": [
        r"po\s*(no\.?|number)\s*[:\-]",
        r"purchase\s*order\s*(no\.?|number)?\s*[:\-]",
        r"unit\s*price\s*[:\-]",
        r"delivery\s*date\s*[:\-]",
    ],
    "metadata_fields": {
        "po_number": "high",
        "vendor": "medium",
        "material_details": "high",
        "quantity": "high",
        "unit_price": "high",
        "delivery_date": "high",
    },
    "semantic_anchors": [
        "purchase order", "vendor", "delivery", "quantity", "unit price",
        "material", "payment terms",
    ],
    "highlight_focus": [
        "ordered materials", "delivery commitments", "payment terms",
    ],
}
