"""
backend/pipeline/scoring.py

Implements PRD Section 8 (document scoring):
  8.1-8.2  Metadata Score (document-level, unchanged)
  8.1-8.4  Sentence-level scoring (metadata + keyword + semantic),
           feeding the diversity filter (8.5) and highlighting (Stage 9).

Public interface:

    calculate_metadata_score(extracted_metadata: dict, profile: dict) -> float
        Unchanged. See original docstring below.

    score_sentences(sentences: list[str], metadata: dict, profile: dict
                     ) -> list[ScoredSentence]
        Matches the interface app.py already expects:
            scoring.score_sentences(sp.sentences, metadata, profile)
        Returns one ScoredSentence per input sentence with:
            .sentence, .score, .metadata_score, .keyword_score, .semantic_score
        The list is sorted by .score descending (highest first) as a
        convenience for callers; diversity_filter.apply_diversity_filter
        still does its own MMR re-ranking/truncation to top_n on top of
        this, so the sort here doesn't have to be authoritative -- it
        just means "top of list = most promising" if diversity_filter
        or a caller ever wants to peek before filtering.

--------------------------------------------------------------------
calculate_metadata_score() contract notes (unchanged, do not modify):
    - extracted_metadata: output of metadata_extraction.extract_metadata(),
      i.e. {field_name: {"value": str|None, "confidence": float}}
    - profile: the document profile dict (profiles/*.py), specifically
      uses profile["metadata_fields"] = {snake_case_key: "high"|"medium"|"low"}
    - metadata_score = sum(priority_weight * confidence)
                        / sum(all possible priority weights for the profile)
    - A profile with no metadata_fields (or all-zero weights) returns 0.0
      rather than raising a ZeroDivisionError.
    - Missing/unfound fields (value=None, confidence=0.0) contribute 0
      and never raise.
    - "Invoice Number" -> "invoice_number" via field_name.lower().replace(" ", "_").
    - Unregistered derived keys are skipped (contribute 0), not raised.
--------------------------------------------------------------------

score_sentences() design notes (PRD 8.1-8.4):

    Each sentence gets three sub-scores in [0.0, 1.0], combined via the
    configured weights (config.METADATA_SCORE_WEIGHT / KEYWORD_SCORE_WEIGHT
    / SEMANTIC_SCORE_WEIGHT):

    - metadata_score (8.2, sentence-level):
        Reuses the *same* priority-weighted, same-denominator scheme as
        calculate_metadata_score(), but only credits a metadata field's
        weight*confidence to a sentence if that field's extracted value
        actually appears (case-insensitive substring) in the sentence.
        This keeps the sentence-level metric consistent with, and
        comparable to, the document-level metadata score, and it means
        the sentence(s) that actually state "Invoice Number: INV-1001"
        etc. are the ones that get credit -- not every sentence in the
        document. Capped at 1.0 defensively (a sentence could in theory
        contain several field values and exceed the nominal max in edge
        cases with overlapping substrings).

    - keyword_score (8.3, "surface" evidence):
        Term-hit ratio against profile["keywords"] -- the same keyword
        set classification.py already uses to detect this document type
        in the first place, so a sentence rich in those terms is surface-
        level relevant to the kind of document this is.

    - semantic_score (8.3/8.4, "conceptual" evidence):
        Term-hit ratio against profile["semantic_anchors"] -- concepts
        curated per-profile as the ideas Business Highlights should key
        on (e.g. contract.py's "termination", "liability", "indemnity").
        This is a lightweight heuristic stand-in for the PRD's MiniLM
        embedding similarity (models.model_loader loads MiniLM at
        startup for that purpose): term-hit ratio against curated
        anchor phrases rather than vector similarity. The function
        signature and output shape are unchanged either way, so this
        can be swapped for an embedding-based implementation later
        without touching callers.

    Neither term-hit helper divides by document-wide frequency (unlike
    classification._keyword_score, which scores whole documents) --
    each sentence is short, so "how many of the profile's terms show up
    in this one sentence" is the right denominator, not "how many times
    across the whole document."
"""

from backend import config


# ---------------------------------------------------------------------
# Document-level metadata score (existing, unmodified)
# ---------------------------------------------------------------------

def _derive_metadata_key(field_name: str) -> str:
    """'Invoice Number' -> 'invoice_number'"""
    return field_name.lower().replace(" ", "_")


def calculate_metadata_score(extracted_metadata: dict, profile: dict) -> float:
    metadata_fields = profile.get("metadata_fields", {})

    # Denominator: total possible weight for this profile, independent of
    # what extraction actually found. This is what "fully complete, fully
    # confident extraction" would sum to.
    max_possible = sum(
        config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        for priority in metadata_fields.values()
    )

    if max_possible == 0:
        # No scorable fields defined for this profile (or config has no
        # weights) -- nothing to normalize against.
        return 0.0

    earned = 0.0
    for field_name, result in extracted_metadata.items():
        metadata_key = _derive_metadata_key(field_name)
        priority = metadata_fields.get(metadata_key)
        if priority is None:
            # Field extracted but not registered for scoring in this
            # profile (shouldn't happen once profiles are aligned, but
            # don't let it crash the pipeline).
            continue

        weight = config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        confidence = result.get("confidence", 0.0) or 0.0
        earned += weight * confidence

    return earned / max_possible


# ---------------------------------------------------------------------
# Sentence-level scoring (new, PRD Section 8.1-8.4)
# ---------------------------------------------------------------------

class ScoredSentence:
    """
    Matches the interface app.py already expects from
    pipeline.scoring.score_sentences():
        .sentence, .score, .metadata_score, .keyword_score, .semantic_score
    """

    __slots__ = ("sentence", "score", "metadata_score", "keyword_score", "semantic_score")

    def __init__(self, sentence: str, score: float, metadata_score: float,
                 keyword_score: float, semantic_score: float):
        self.sentence = sentence
        self.score = score
        self.metadata_score = metadata_score
        self.keyword_score = keyword_score
        self.semantic_score = semantic_score

    def __repr__(self):
        return (
            f"ScoredSentence(score={self.score:.4f}, "
            f"metadata={self.metadata_score:.4f}, "
            f"keyword={self.keyword_score:.4f}, "
            f"semantic={self.semantic_score:.4f}, "
            f"sentence={self.sentence!r})"
        )


def _term_hit_ratio(text_lower: str, terms: list[str]) -> float:
    """
    Fraction of `terms` that appear (case-insensitive substring) in
    text_lower. Returns 0.0 for an empty/missing term list rather than
    raising -- profiles vary in how many keywords/anchors they define
    (PRD note on technical_spec.py: some profiles are deliberately
    lighter here), and a sentence simply can't out-score what the
    profile gives it to work with.
    """
    if not terms:
        return 0.0
    hits = sum(1 for term in terms if term.lower() in text_lower)
    return hits / len(terms)


def _sentence_metadata_score(sentence: str, metadata: dict, profile: dict) -> float:
    """
    Credits a sentence with priority_weight * confidence for each
    metadata field whose *extracted value* actually appears in that
    sentence, normalized against the same max_possible denominator
    calculate_metadata_score() uses -- so this stays on the same 0-1
    scale and the same meaning ("fraction of the profile's total
    possible metadata weight that this sentence accounts for").
    """
    metadata_fields = profile.get("metadata_fields", {})
    max_possible = sum(
        config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        for priority in metadata_fields.values()
    )
    if max_possible == 0:
        return 0.0

    sentence_lower = sentence.lower()
    earned = 0.0
    for field_name, result in metadata.items():
        value = result.get("value")
        if not value:
            continue
        if value.strip().lower() not in sentence_lower:
            continue

        metadata_key = _derive_metadata_key(field_name)
        priority = metadata_fields.get(metadata_key)
        if priority is None:
            continue

        weight = config.FIELD_PRIORITY_WEIGHTS.get(priority, 0.0)
        confidence = result.get("confidence", 0.0) or 0.0
        earned += weight * confidence

    return min(earned / max_possible, 1.0)


def score_sentences(sentences: list[str], metadata: dict, profile: dict
                     ) -> list["ScoredSentence"]:
    """
    PRD Section 8.1-8.4: score every candidate sentence on metadata,
    keyword, and semantic evidence, then combine via the configured
    weights into a single .score. Sentences that carry no evidence of
    any kind simply score 0.0 across the board rather than raising --
    diversity_filter / Top-N selection is responsible for dropping the
    low scorers, not this function.
    """
    keywords = profile.get("keywords", [])
    semantic_anchors = profile.get("semantic_anchors", [])

    scored: list[ScoredSentence] = []
    for sentence in sentences:
        sentence_lower = sentence.lower()

        metadata_score = _sentence_metadata_score(sentence, metadata, profile)
        keyword_score = _term_hit_ratio(sentence_lower, keywords)
        semantic_score = _term_hit_ratio(sentence_lower, semantic_anchors)

        final_score = (
            metadata_score * config.METADATA_SCORE_WEIGHT
            + keyword_score * config.KEYWORD_SCORE_WEIGHT
            + semantic_score * config.SEMANTIC_SCORE_WEIGHT
        )

        scored.append(
            ScoredSentence(
                sentence=sentence,
                score=final_score,
                metadata_score=metadata_score,
                keyword_score=keyword_score,
                semantic_score=semantic_score,
            )
        )

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored