"""
Pipeline Stage 7: Detect important business clauses (PRD Section 7 /
per-type "Highlight / clause focus" lists, PRD Sections 7.1-7.8).

Signature note (approved change from the interface originally sketched
in app.py's docstring): this module takes per-page text, not one joined
full_text string, so each clause can carry an accurate page number (PRD
Section 9's report requires "page" per clause, which is only
recoverable if page boundaries survive into this stage). app.py's call
site changes accordingly - see the diff below this module.

--------------------------------------------------------------------
HEURISTIC LAYER - read before editing thresholds or synonym lists
--------------------------------------------------------------------
Profiles (backend/profiles/*.py) define *labels* for each document
type's clause focus (e.g. "penalty clauses", "due dates") but no
explicit trigger-phrase set per category - only the label itself, plus
a shared per-type `semantic_anchors`/`keywords` list not broken down by
category. Rather than leave categories with zero detectable signal,
this module:

  1. Tokenizes each category label into significant words (dropping
     generic suffixes like "clauses", "information").
  2. Expands those words via a small hand-written synonym table
     (_CATEGORY_SYNONYMS) covering concepts recurring across the PRD's
     document types (payment, penalty, deadline, delivery, termination,
     liability, warranty, quality, safety, tax, etc.).
  3. Pulls in any profile `keywords`/`semantic_anchors` entries that
     share a token with the category label, as extra type-specific signal.
  4. Scores each sentence per category by trigger-word hit count and
     keeps sentences with at least one hit.

This is a keyword/token-overlap heuristic, not a learned or semantic
classifier - it will over- or under-match on paraphrased clauses. It's
intentionally isolated in _category_triggers / _score_sentence_for_category
so it can be swapped for explicit per-category trigger definitions in
the profiles later without touching the rest of this module.
--------------------------------------------------------------------
"""
import re
from collections import defaultdict

from .sentence_pipeline import segment_sentences

# Generic words stripped from a category label before it's used as a
# set of trigger tokens - these describe the *kind* of grouping, not a
# searchable concept.
_LABEL_STOPWORDS = {
    "clauses", "clause", "information", "conditions", "requirements",
    "related", "and", "or", "the", "of",
}

# Hand-written synonym expansion per recurring business concept (see
# module docstring). Keys are individual significant words that may
# appear in a category label; values are additional trigger phrases.
_CATEGORY_SYNONYMS = {
    "payment": ["payment", "paid", "remit", "invoice amount", "consideration", "amount due"],
    "obligations": ["shall pay", "shall deliver", "responsible for", "obligated"],
    "due": ["due date", "due on", "payable by", "within"],
    "dates": ["date", "on or before", "by the"],
    "deadlines": ["deadline", "submission date", "last date", "before"],
    "submission": ["submission", "submit", "bid submission"],
    "penalty": ["penalty", "liquidated damages", "fine", "interest", "breach"],
    "penalties": ["penalty", "liquidated damages", "fine", "interest", "breach"],
    "amount": ["amount", "total amount", "sum of", "value of"],
    "tax": ["tax", "gst", "gstin", "hsn", "sac"],
    "delivery": ["delivery", "delivered", "dispatch", "consignment", "handover"],
    "materials": ["material", "materials", "goods", "item"],
    "quantity": ["quantity", "qty", "units", "nos."],
    "discrepancies": ["discrepancy", "shortage", "excess", "mismatch"],
    "scope": ["scope of work", "responsibilities", "deliverables"],
    "work": ["scope of work", "assigned work", "task"],
    "eligibility": ["eligibility", "eligible", "qualification", "criteria"],
    "criteria": ["criteria", "requirement", "must meet"],
    "technical": ["technical requirement", "specification", "standard"],
    "liability": ["liability", "liable", "indemnify", "indemnity", "damages"],
    "termination": ["termination", "terminate", "cancellation", "cancel"],
    "warranty": ["warranty", "guarantee", "defect", "defect liability"],
    "high-value": ["high value", "high-value", "significant cost"],
    "items": ["item", "line item"],
    "specifications": ["specification", "spec", "standard", "grade"],
    "safety": ["safety", "hazard", "precaution", "ppe"],
    "engineering": ["engineering standard", "code", "is code", "astm", "iso"],
    "standards": ["standard", "code", "astm", "iso"],
    "quality": ["quality", "quality control", "inspection", "acceptance criteria"],
    "responsibilities": ["responsible for", "shall be responsible", "duty"],
    "completion": ["completion", "complete by", "finish"],
    "schedule": ["schedule", "timeline", "timetable"],
}

# Not PRD-specified; a reasonable production default so one dominant
# clause type (e.g. "payment" hitting nearly every sentence in a
# finance-heavy document) doesn't crowd out the report's Critical
# Business Clauses section (PRD Section 9), which is meant to be curated.
_MAX_CLAUSES_PER_CATEGORY = 6


def _tokenize_label(category: str) -> list[str]:
    words = re.findall(r"[a-z]+(?:-[a-z]+)?", category.lower())
    return [w for w in words if w not in _LABEL_STOPWORDS]


def _category_triggers(category: str, profile: dict) -> set[str]:
    """Build the trigger-phrase set for one highlight_focus category."""
    label_tokens = _tokenize_label(category)
    triggers = set(label_tokens)

    for token in label_tokens:
        triggers.update(_CATEGORY_SYNONYMS.get(token, []))

    supporting = list(profile.get("keywords", [])) + list(profile.get("semantic_anchors", []))
    for phrase in supporting:
        phrase_tokens = set(re.findall(r"[a-z]+", phrase.lower()))
        if phrase_tokens & set(label_tokens):
            triggers.add(phrase.lower())

    return {t for t in triggers if t}


def _score_sentence_for_category(sentence_lower: str, triggers: set[str]) -> int:
    return sum(1 for trigger in triggers if trigger in sentence_lower)


def detect_clauses(pages: list[str], profile: dict) -> list[dict]:
    """
    Scan each page's cleaned text for sentences matching any of the
    document type's highlight_focus categories (PRD Section 7).

    Returns [{"category": str, "text": str, "page": int}, ...], ordered
    by category (profile order), then by trigger-hit count within category.
    """
    categories = profile.get("highlight_focus", [])
    if not categories:
        return []

    trigger_map = {category: _category_triggers(category, profile) for category in categories}

    candidates: dict[str, list[tuple]] = defaultdict(list)
    for page_number, page_text in enumerate(pages, start=1):
        for sentence in segment_sentences(page_text):
            sentence_lower = sentence.lower()
            for category, triggers in trigger_map.items():
                hits = _score_sentence_for_category(sentence_lower, triggers)
                if hits > 0:
                    candidates[category].append((hits, page_number, sentence))

    clauses = []
    for category in categories:  # preserve profile-defined category order
        ranked = sorted(candidates.get(category, []), key=lambda c: c[0], reverse=True)
        seen_text = set()
        kept = 0
        for _hits, page_number, sentence in ranked:
            key = re.sub(r"\s+", " ", sentence.strip().lower())
            if key in seen_text:
                continue
            seen_text.add(key)
            clauses.append({"category": category.title(), "text": sentence, "page": page_number})
            kept += 1
            if kept >= _MAX_CLAUSES_PER_CATEGORY:
                break

    return clauses