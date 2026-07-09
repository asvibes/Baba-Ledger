"""
backend/pipeline/diversity_filter.py

Implements PRD Section 8.5: MMR near-duplicate suppression, applied
after scoring.score_sentences() and before highlighting/report
generation (Stage 9 in app.py).

Public interface (matches backend/app.py's expectation):

    apply_diversity_filter(
        scored_sentences: list[ScoredSentence], top_n: int
    ) -> list[ScoredSentence]

Design notes:

    Greedy score-first, similarity-gated selection: walk the candidates
    highest .score first, and only accept a candidate into the result
    if it isn't a near-duplicate (similarity >= config
    .DIVERSITY_SIMILARITY_THRESHOLD) of anything already accepted. This
    is the practical core of MMR for this pipeline -- always prefer the
    highest-scoring sentence available, but skip ones that would just
    restate a highlight we already have (e.g. the same clause repeated
    verbatim on two pages) so the Top-N highlights spread across more
    of the document's actual content instead of clustering on one
    high-scoring passage and its near-duplicates.

    Similarity is lexical (difflib.SequenceMatcher ratio on normalized
    text), not embedding-based -- same documented trade-off as
    scoring.py's semantic_score: no embedding model is wired into this
    heuristic implementation, so this is a stand-in with the same
    function signature, swappable later for real embedding similarity
    (e.g. cosine similarity over the MiniLM vectors models.model_loader
    already loads) without touching callers.

    Backfill guarantee: PRD 8.6's Top-N sizing is a promise to the user
    ("this document gets N highlights"), so if diversity suppression
    would leave the result short of top_n (e.g. a short document where
    most sentences are near-duplicates of each other), remaining slots
    are backfilled with the next-best-scoring candidates regardless of
    similarity. Showing a possible near-duplicate is preferable to
    silently under-delivering on Top-N (PRD 14.4 spirit: no silent
    under-delivery).

    Never raises on edge cases:
      - empty scored_sentences -> returns []
      - top_n <= 0 -> returns []
      - top_n >= len(scored_sentences) -> returns everything, in score order
"""

import difflib
import re


from .. import config


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _similarity(a: str, b: str) -> float:
    """
    Lexical near-duplicate signal in [0.0, 1.0]. Two sentences that
    differ only in whitespace/case/punctuation score close to 1.0;
    genuinely different sentences score low. See module docstring for
    why this is lexical rather than embedding-based here.
    """
    a_norm = _normalize(a)
    b_norm = _normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


def _is_near_duplicate(candidate_sentence: str, selected: list) -> bool:
    return any(
        _similarity(candidate_sentence, s.sentence) >= config.DIVERSITY_SIMILARITY_THRESHOLD
        for s in selected
    )


def apply_diversity_filter(scored_sentences: list, top_n: int) -> list:
    """
    Select up to top_n sentences from scored_sentences, preferring
    higher .score and suppressing near-duplicates of sentences already
    selected. See module docstring for the backfill guarantee.
    """
    if not scored_sentences or top_n <= 0:
        return []

    # Don't assume the caller's ordering; score.py's score_sentences()
    # already sorts descending, but this function's contract shouldn't
    # depend on that.
    candidates = sorted(scored_sentences, key=lambda s: s.score, reverse=True)

    if top_n >= len(candidates):
        return candidates

    selected: list = []
    for candidate in candidates:
        if len(selected) >= top_n:
            break
        if _is_near_duplicate(candidate.sentence, selected):
            continue
        selected.append(candidate)

    if len(selected) < top_n:
        selected_ids = {id(s) for s in selected}
        for candidate in candidates:
            if len(selected) >= top_n:
                break
            if id(candidate) in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(id(candidate))

    return selected