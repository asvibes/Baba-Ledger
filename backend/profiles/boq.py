"""Bill of Quantities (BOQ) profile (PRD Section 7.6)."""

PROFILE = {
    "type": "boq",
    "display_name": "Bill of Quantities",
    "keywords": [
        "item description", "quantity", "unit", "estimated cost",
        "rate", "amount", "bill of quantities", "boq",
    ],
    "structural_patterns": [
        r"item\s*(no\.?|description)",
        r"\bunit\b\s*[:\-]?\s*(qty|quantity)?",
        r"rate\s*[:\-]",
        r"estimated\s*cost\s*[:\-]",
    ],
    
    "fields": [
    "Item Description",
    "Quantity",
    "Unit",
    "Estimated Cost",
],

"field_patterns": {
    "Item Description": r"item\s*(description)?\s*[:\-]?\s*(.+)",
    "Quantity": r"quantity\s*[:\-]?\s*(.+)",
    "Unit": r"unit\s*[:\-]?\s*(.+)",
    "Estimated Cost": r"estimated\s*cost\s*[:\-]?\s*(.+)",
},
    
    "metadata_fields": {
        "item_description": "high",
        "quantity": "high",
        "unit": "medium",
        "estimated_cost": "high",
    },
    "semantic_anchors": [
        "item", "quantity", "unit", "rate", "estimated cost", "material",
    ],
    "highlight_focus": [
        "high-value items", "material requirements", "quantity-related information",
    ],
}
