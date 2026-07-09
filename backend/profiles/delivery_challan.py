"""Delivery Challan profile (PRD Section 7.7)."""

PROFILE = {
    "type": "delivery_challan",
    "display_name": "Delivery Challan",
    "keywords": [
        "delivery challan", "material delivered", "received by",
        "challan number", "quantity delivered", "vendor", "project", "site",
    ],
    "structural_patterns": [
        r"delivery\s*challan\s*(no\.?|number)?\s*[:\-]",
        r"material\s*delivered",
        r"received\s*by\s*[:\-]",
    ],
    "metadata_fields": {
        "challan_number": "high",
        "vendor": "medium",
        "project_site": "medium",
        "material_delivered": "high",
        "quantity": "high",
        "delivery_date": "high",
        "received_by": "medium",
    },
    "semantic_anchors": [
        "delivery", "material delivered", "received by", "quantity",
        "challan", "dispatch",
    ],
    "highlight_focus": [
        "delivered materials", "quantity discrepancies", "delivery date vs. order date",
    ],
}
