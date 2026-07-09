"""
backend/pipeline/summarization.py

Implements PRD Section 8.8: chunked executive-summary generation
(Stage 8 of the pipeline, PRD Section 5).

Public interface (matches app.py's expectation):

    summarize_document(full_text: str) -> str
        Raises nothing fatal (PRD 14.4 spirit) -- on a per-chunk
        failure it degrades gracefully by skipping that chunk rather
        than aborting the whole document, and on total failure (e.g.
        the summarization model never loaded) it returns "" instead of
        raising, since a missing summary shouldn't take down a job that
        otherwise completed metadata extraction, clause detection,
        scoring, and highlighting.

Design notes:

    BART (facebook/bart-large-cnn, via models.model_loader.get_summarizer())
    has a fixed input window, far smaller than a real document's cleaned
    full_text can be. This module never loads its own model -- it
    reuses the pipeline object model_loader already loaded once at
    startup -- and instead handles the length mismatch itself:

    1. Chunk (PRD 8.8): full_text is split into overlapping windows of
       SUMMARY_CHUNK_SIZE_TOKENS tokens (config.py), using the BART
       tokenizer itself for the token count so a chunk boundary never
       lands mid-token. SUMMARY_CHUNK_OVERLAP_TOKENS of context is
       repeated between consecutive chunks so a sentence that happens
       to straddle a chunk boundary still has surrounding context on
       at least one side, instead of being cut cleanly in half with no
       context on either piece.

    2. Summarize each chunk independently. A chunk that fails (model
       error, degenerate/garbage input, etc.) is skipped -- its
       contribution to the final summary is simply absent, not a
       placeholder or an invented sentence, per the "never invent
       information" principle text_cleaning.py's docstring already
       establishes for this codebase.

    3. Reduce: chunk summaries are joined into an intermediate summary.
       If that intermediate text is itself still too long to hand to
       BART as a single input (i.e. it doesn't fit in one more
       chunk-sized window), it's summarized again, chunk-by-chunk, the
       same way -- this repeats until the combined summary fits in a
       single window, at which point one last summarization pass
       produces the final cohesive executive summary. A hard iteration
       cap (_MAX_REDUCE_PASSES) guards against ever looping forever on
       a pathological input.

    Empty/whitespace-only input, or an input that fails to load any
    token/no chunks, returns "" rather than raising or calling the
    model on nothing.
"""

from ..models.model_loader import get_summarizer
from ..utils.errors import ModelLoadingError
from .. import config

# Generation length bounds handed to BART per summarization call. These
# are independent of SUMMARY_CHUNK_SIZE_TOKENS (which bounds the INPUT),
# and instead bound the OUTPUT of a single summarize() call -- a chunk's
# summary should be meaningfully shorter than the chunk itself, but long
# enough to preserve the substance of a full chunk of source text.
_SUMMARY_MAX_LENGTH_TOKENS = 180
_SUMMARY_MIN_LENGTH_TOKENS = 30

# Safety cap on reduce passes (chunk-summarize-join-repeat) so a
# pathological input can't loop indefinitely; in practice a document
# would need to be enormous to ever approach this.
_MAX_REDUCE_PASSES = 5


def _split_into_chunks(text: str, tokenizer, chunk_size: int, overlap: int) -> list[str]:
    """
    Split `text` into overlapping windows of at most `chunk_size` tokens
    (per the BART tokenizer, so a window boundary never lands mid-token),
    with `overlap` tokens of shared context between consecutive windows.

    Returns [] for empty input rather than a list containing one empty
    chunk.
    """
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if not token_ids:
        return []

    step = max(chunk_size - overlap, 1)  # always make forward progress
    chunks = []
    start = 0
    n = len(token_ids)
    while start < n:
        end = min(start + chunk_size, n)
        chunk_ids = token_ids[start:end]
        chunks.append(tokenizer.decode(chunk_ids, skip_special_tokens=True))
        if end == n:
            break
        start += step
    return chunks


def _summarize_chunk(summarizer, chunk_text: str) -> str:
    """
    Summarize a single chunk. Returns "" (rather than raising) if this
    particular chunk fails -- per PRD 14.4, one bad chunk shouldn't
    abort the whole document's summary.
    """
    chunk_text = chunk_text.strip()
    if not chunk_text:
        return ""
    try:
        result = summarizer(
            chunk_text,
            max_length=_SUMMARY_MAX_LENGTH_TOKENS,
            min_length=_SUMMARY_MIN_LENGTH_TOKENS,
            truncation=True,
            do_sample=False,
        )
        return result[0]["summary_text"].strip()
    except Exception:
        # Degrade gracefully: this chunk contributes nothing rather
        # than crashing Stage 8 for the whole document.
        return ""


def _reduce_pass(summarizer, tokenizer, text: str) -> str:
    """
    One map-reduce pass: chunk `text`, summarize each chunk, and join
    the results into a single intermediate string.
    """
    chunks = _split_into_chunks(
        text, tokenizer,
        config.SUMMARY_CHUNK_SIZE_TOKENS,
        config.SUMMARY_CHUNK_OVERLAP_TOKENS,
    )
    if not chunks:
        return ""

    partial_summaries = [_summarize_chunk(summarizer, c) for c in chunks]
    partial_summaries = [s for s in partial_summaries if s]  # drop skipped chunks
    return " ".join(partial_summaries)


def summarize_document(full_text: str) -> str:
    """
    Produce a chunked executive summary of `full_text` (PRD 8.8),
    reusing the BART pipeline already loaded by models.model_loader.

    Returns "" for empty/whitespace-only input, or if the summarization
    model never finished loading -- a missing summary shouldn't fail
    the rest of the pipeline (metadata, clauses, scoring, highlighting
    can all still complete and be reported to the user).
    """
    if not full_text or not full_text.strip():
        return ""

    try:
        summarizer = get_summarizer()
    except ModelLoadingError:
        return ""

    tokenizer = summarizer.tokenizer

    # First pass: summarize the raw document, one chunk at a time.
    summary = _reduce_pass(summarizer, tokenizer, full_text)
    if not summary:
        return ""

    # Reduce further only if the combined summary is itself still too
    # long to hand to BART as a single input -- otherwise stop as soon
    # as it fits in one window, and do one last pass to produce a
    # single cohesive summary rather than a concatenation of chunk
    # summaries.
    passes = 0
    while passes < _MAX_REDUCE_PASSES:
        token_count = len(tokenizer.encode(summary, add_special_tokens=False))
        if token_count <= config.SUMMARY_CHUNK_SIZE_TOKENS:
            final = _summarize_chunk(summarizer, summary)
            return final or summary
        summary = _reduce_pass(summarizer, tokenizer, summary)
        if not summary:
            return ""
        passes += 1

    # Reduce cap hit on a pathological input: return the best
    # intermediate summary we have rather than looping forever or
    # raising.
    return summary