"""
Demonstrates pipeline.report_generator.generate_report() in isolation,
using mocked outputs from the earlier stages it normally consumes
(classification, metadata_extraction, clause_detection, scoring,
summarization) so this can run without a real PDF upload or the NLP
models being loaded.

Run with:  python3 -m backend.demo_report_generator   (from /home/claude/baba-ledger)

Produces two PDFs under /tmp so you can inspect both the happy path
and the "everything degraded gracefully" path described in
report_generator.py's docstring:
    /tmp/baba_ledger_demo_report.pdf        (full data)
    /tmp/baba_ledger_demo_report_empty.pdf  (all sections empty/None)
"""
from .pipeline.classification import ClassificationResult, ClassificationStrength, TypeScore
from .pipeline.report_generator import generate_report
from .pipeline.scoring import ScoredSentence

# --- Mocked Stage 5 output (classification.py) ---
_CLASSIFICATION = ClassificationResult(
    predicted_type="invoice",
    strength=ClassificationStrength.HIGH,
    top_score=0.87,
    margin=0.31,
    all_scores=[
        TypeScore("invoice", keyword_score=0.90, structural_score=0.85, combined_score=0.87),
        TypeScore("tender", keyword_score=0.20, structural_score=0.15, combined_score=0.18),
    ],
    use_generic_fallback=False,
)

# --- Mocked Stage 6 output (metadata_extraction.py) ---
_METADATA = {
    "Invoice Number": {"value": "INV-2026-0417", "confidence": 0.95},
    "Vendor": {"value": "Acme Engineering & Fabrication Pvt. Ltd.", "confidence": 0.90},
    "Total Amount": {"value": "INR 1,84,320.00", "confidence": 0.85},
    "Purchase Order Reference": {"value": None, "confidence": 0.0},  # not found, on purpose
}

# --- Mocked Stage 7 output (clause_detection.py) ---
_CLAUSES = [
    {
        "category": "Payment Terms",
        "text": "Payment shall be made within 15 days of the invoice date.",
        "page": 1,
    },
    {
        "category": "Penalty",
        "text": "Late payments will incur a penalty of 2% per month on the outstanding balance.",
        "page": 1,
    },
]

# --- Mocked Stage 8 output (summarization.py) ---
_SUMMARY = (
    "This invoice from Acme Engineering & Fabrication Pvt. Ltd. bills Baba "
    "Constructions INR 1,84,320.00 for MS Angle steel supplied under invoice "
    "INV-2026-0417. Payment is due within 15 days, with a 2% monthly penalty "
    "on late payments."
)

# --- Mocked Stage 9 output (scoring.py + diversity_filter.py) ---
_HIGHLIGHTS = [
    ScoredSentence(
        sentence="Total Amount Due: INR 1,84,320.00",
        score=0.91, metadata_score=0.95, keyword_score=0.80, semantic_score=0.70,
    ),
    ScoredSentence(
        sentence="Late payments will incur a penalty of 2% per month on the outstanding balance.",
        score=0.78, metadata_score=0.40, keyword_score=0.85, semantic_score=0.90,
    ),
    ScoredSentence(
        sentence="Payment shall be made within 15 days of the invoice date.",
        score=0.74, metadata_score=0.30, keyword_score=0.75, semantic_score=0.88,
    ),
]


def run_full_demo():
    out_path = "/tmp/baba_ledger_demo_report.pdf"
    generate_report(
        doc_type="Invoice",
        classification=_CLASSIFICATION,
        metadata=_METADATA,
        clauses=_CLAUSES,
        summary=_SUMMARY,
        highlights=_HIGHLIGHTS,
        out_path=out_path,
    )
    print(f"Full-data report written to {out_path}")


def run_degraded_demo():
    """
    Mirrors a job where classification landed on Low Strength, no
    metadata/clauses were found, summarization degraded to "", and
    diversity_filter produced no highlights -- every section should
    still render an explicit fallback line instead of a blank page.
    """
    out_path = "/tmp/baba_ledger_demo_report_empty.pdf"
    generate_report(
        doc_type="",
        classification=None,
        metadata={},
        clauses=[],
        summary="",
        highlights=[],
        out_path=out_path,
    )
    print(f"Degraded-input report written to {out_path}")


if __name__ == "__main__":
    run_full_demo()
    run_degraded_demo()