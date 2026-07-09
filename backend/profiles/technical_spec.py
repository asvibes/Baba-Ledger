"""
Technical Specification profile (PRD Section 7.8).

Note (per PRD): this document type is more complex than the others —
detailed engineering requirements rather than clearly structured
business fields — so it is expected to produce fewer structured
metadata fields but still valuable summaries and highlighted clauses.
Deeper structured specification parsing is reserved for a future version.
"""

PROFILE = {
    "type": "technical_spec",
    "display_name": "Technical Specification",
    "keywords": [
        "applicable standard", "is code", "astm", "iso", "material grade",
        "tolerance", "testing", "inspection", "quality control",
        "acceptance criteria", "safety requirements",
    ],
    "structural_patterns": [
        r"\bis\s*\d{2,5}\b",
        r"\bastm\s*[a-z]?\d+\b",
        r"\biso\s*\d+\b",
        r"grade\s*[:\-]?\s*[a-z0-9]+",
    ],
    "metadata_fields": {
        "applicable_standards": "high",
        "material_specifications": "high",
        "grade_class_information": "high",
        "construction_requirements": "medium",
        "testing_inspection_requirements": "medium",
        "safety_requirements": "high",
        "quality_control_requirements": "medium",
        "acceptance_criteria": "medium",
    },
    "semantic_anchors": [
        "standard", "material grade", "tolerance", "testing", "inspection",
        "safety", "quality control", "acceptance criteria",
    ],
    "highlight_focus": [
        "material specifications", "quality requirements",
        "safety requirements", "engineering standards",
    ],
}
