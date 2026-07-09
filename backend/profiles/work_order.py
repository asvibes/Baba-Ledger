"""Work Order profile (PRD Section 7.4)."""

PROFILE = {
    "type": "work_order",
    "display_name": "Work Order",
    "keywords": [
        "work order number", "work order no", "scope of work", "contractor",
        "completion timeline", "site", "mobilization", "handover",
    ],
    "structural_patterns": [
        r"work\s*order\s*(no\.?|number)\s*[:\-]",
        r"scope\s*of\s*work",
        r"completion\s*(timeline|date|period)\s*[:\-]",
    ],
    
    "fields": [
    "Work Order Number",
    "Project Name",
    "Contractor",
    "Completion Timeline",
    "Scope of Work",
],

"field_patterns": {
    "Work Order Number": r"work\s*order\s*(no\.?|number)\s*[:\-]?\s*(.+)",
    "Project Name": r"(project\s*name|project)\s*[:\-]?\s*(.+)",
    "Contractor": r"(contractor|agency|vendor)\s*[:\-]?\s*(.+)",
    "Completion Timeline": r"completion\s*(timeline|date|period)\s*[:\-]?\s*(.+)",
    "Scope of Work": r"scope\s*of\s*work\s*[:\-]?\s*(.+)",
},
    
    "metadata_fields": {
        "work_order_number": "high",
        "project_name": "medium",
        "contractor": "medium",
        "completion_timeline": "high",
        "scope_of_work": "high",
    },
    "semantic_anchors": [
        "work order", "scope of work", "contractor", "deadline",
        "completion", "handover", "site", "responsibility",
    ],
    "highlight_focus": [
        "assigned work", "delivery schedule", "completion deadlines",
        "responsibilities",
    ],
}
