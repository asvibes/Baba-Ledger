"""
Demonstrates the pipeline spine built so far:
  text cleaning -> classification + Classification Strength -> sentence
  pipeline (header/footer removal, dedup, Top-N sizing)

Run with:  python3 -m backend.demo_pipeline   (from /home/claude/baba-ledger)
"""
from .pipeline.classification import classify_document
from .pipeline.sentence_pipeline import run_sentence_pipeline
from .profiles import get_profile

INVOICE_TEXT = """
ACME ENGINEERING & FABRICATION PVT. LTD.
TAX INVOICE
Invoice Number: INV-2026-0417
Vendor: Acme Engineering & Fabrication Pvt. Ltd.
Client: Baba Constructions
Invoice Date: 03 July 2026
Due Date: 18 July 2026
Description of Goods Supplied: MS Angle 50x50x6mm, Grade Fe410
Quantity: 2400 kg
Payment shall be made within 15 days of the invoice date.
Late payments will incur a penalty of 2% per month on the outstanding balance.
Total Amount Due: INR 1,84,320.00
GST (18%): INR 28,120.00
Please remit payment to the bank account specified in the attached annexure
and quote the invoice number as reference.
"""

TENDER_TEXT = """
BABA CONSTRUCTIONS
TENDER NOTICE
Tender Number: TND-2026-0091
Project Name: Warehouse Expansion, Site B
Client: Baba Constructions
Estimated Project Cost: INR 2,40,00,000
Scope of Work: Structural steel fabrication and erection for a 3,200 sqm
warehouse extension, including foundation work and roofing.
Eligibility Criteria: Bidders must have completed at least two similar
projects exceeding INR 1 crore in the last five years.
Bid Submission Date: 25 July 2026
Completion Period: 120 days from date of award.
Bidders failing to meet the submission deadline will be disqualified
without exception. A penalty of 1% of contract value per week of delay
applies to the successful bidder for late completion.
"""

# Ambiguous / bundled document: mixes tender-style and contract-style
# language deliberately, to demonstrate the Low-Strength / margin-check path.
AMBIGUOUS_TEXT = """
TENDER NOTICE AND GENERAL CONDITIONS OF CONTRACT
Tender Number: TND-2026-0140
Scope of Work: Supply and installation of structural steel members.
This Agreement is made between Party A and Party B for the term of the
project. Termination of this Agreement may occur upon breach by either
party. Liability for damages shall be limited as set out in Clause 12.
Eligibility Criteria: as per Annexure A.
Payment Terms: as per the Purchase Order referenced herein.
"""

# Weak/insufficient evidence for any known type - should hit the
# absolute minimum-evidence floor and fall back to Low Strength / generic.
LOW_EVIDENCE_TEXT = """
Please find attached the required documents for your reference.
Kindly confirm receipt at your earliest convenience.
We look forward to your response.
"""


def run_demo(label: str, text: str):
    print(f"\n=== {label} ===")
    result = classify_document(text)
    print(f"Predicted type      : {result.predicted_type}")
    print(f"Classification Strength: {result.strength.value.upper()}")
    print(f"Top score / margin  : {result.top_score:.2f} / {result.margin:.2f}")
    print("All type scores:")
    for s in result.all_scores:
        print(f"   {s.doc_type:10s} combined={s.combined_score:.2f}  "
              f"(keyword={s.keyword_score:.2f}, structural={s.structural_score:.2f})")
    if result.use_generic_fallback:
        print("-> Low strength: would show mixed-document warning; "
              "generic profile blended in as safety net if user continues.")

    profile = get_profile(result.predicted_type)
    print(f"Resolved profile    : {profile['display_name']}")

    sp = run_sentence_pipeline([text])
    print(f"Valid sentence count: {sp.valid_sentence_count}  ->  Top-N = {sp.top_n}")


if __name__ == "__main__":
    run_demo("Invoice (expect HIGH-ish)", INVOICE_TEXT)
    run_demo("Tender (expect HIGH)", TENDER_TEXT)
    run_demo("Ambiguous / bundled (Tender+Contract language)", AMBIGUOUS_TEXT)
    run_demo("Low evidence / generic note (expect LOW)", LOW_EVIDENCE_TEXT)
