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

    "fields": [
        "Challan Number",
        "Vendor",
        "Project Site",
        "Material Delivered",
        "Quantity",
        "Delivery Date",
        "Received By",
    ],

    "field_patterns": {
        "Challan Number": r"challan\s*(no\.?|number)\s*[:\-]?\s*(.+)",
        "Vendor": r"vendor\s*[:\-]?\s*(.+)",
        "Project Site": r"(project|site)\s*[:\-]?\s*(.+)",
        "Material Delivered": r"material\s*delivered\s*[:\-]?\s*(.+)",
        "Quantity": r"quantity\s*[:\-]?\s*(.+)",
        "Delivery Date": r"delivery\s*date\s*[:\-]?\s*(.+)",
        "Received By": r"received\s*by\s*[:\-]?\s*(.+)",
    },
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
        "delivery",
        "material delivered",
        "received by",
        "quantity",
        "challan",
        "dispatch",
    ],

    "highlight_focus": [
        "delivered materials",
        "quantity discrepancies",
        "delivery date vs. order date",
    ],
}
