"""
Drives PRD Section 8.6: Top-N is based on the number of VALID extracted
sentences after preprocessing, not raw pages and not raw OCR/PDF output.

Pipeline (per PRD 8.6):
    Extract Text -> Clean Text -> Remove Headers/Footers ->
    Remove Empty & Duplicate Sentences -> Sentence Segmentation ->
    Count Valid Sentences -> Determine Top-N

This avoids a repeated header ("ABC Constructions Pvt. Ltd.") on every
page inflating the sentence count and pushing a small document into a
higher Top-N bracket than it should occupy.
"""

import re
from dataclasses import dataclass

from .. import config
from .text_cleaning import clean_text

# A line that recurs on this fraction of pages (or more) is treated as
# running header/footer boilerplate rather than real content.
_HEADER_FOOTER_REPEAT_THRESHOLD = 0.5

# Lightweight sentence boundary: split on . ! ? followed by whitespace
# and a capital letter/quote/digit, while tolerating common abbreviations.
# Production should swap this for a proper tokenizer (nltk punkt / spaCy)
# once those are installable; the interface (str -> list[str]) is unchanged.
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "no", "vs", "pvt", "ltd", "inc",
                   "co", "e.g", "i.e", "etc", "fig", "sec", "govt"}
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


@dataclass
class SentencePipelineResult:
    sentences: list[str]
    valid_sentence_count: int
    top_n: int


def remove_headers_and_footers(page_texts: list[str]) -> list[str]:
    """
    Strip lines that repeat across a majority of pages (running headers/
    footers, letterhead, page numbers) before segmentation, so they
    don't inflate the sentence count used for Top-N sizing.
    """
    if len(page_texts) <= 1:
        return page_texts

    line_page_counts: dict[str, int] = {}
    per_page_lines = []
    for text in page_texts:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        per_page_lines.append(lines)
        for ln in set(lines):
            line_page_counts[ln] = line_page_counts.get(ln, 0) + 1

    n_pages = len(page_texts)
    boilerplate = {
        ln for ln, count in line_page_counts.items()
        if count / n_pages >= _HEADER_FOOTER_REPEAT_THRESHOLD
    }

    cleaned_pages = []
    for lines in per_page_lines:
        kept = [ln for ln in lines if ln not in boilerplate]
        cleaned_pages.append("\n".join(kept))
    return cleaned_pages


def segment_sentences(text: str) -> list[str]:
    """Split cleaned text into candidate sentences."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    raw_sentences = _SENTENCE_SPLIT_RE.split(normalized)
    return [s.strip() for s in raw_sentences if s.strip()]


def remove_empty_and_duplicate_sentences(sentences: list[str]) -> list[str]:
    """De-duplicate while preserving first-seen order; drop empties/near-empties."""
    seen = set()
    result = []
    for s in sentences:
        key = re.sub(r"\s+", " ", s.strip().lower())
        if len(key) < 3:  # not a real sentence (stray punctuation, page numbers, etc.)
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
    return result


def determine_top_n(valid_sentence_count: int) -> int:
    """Look up the Top-N bracket for a given valid sentence count (PRD 8.6 table)."""
    for low, high, top_n in config.TOP_N_BRACKETS:
        if high is None:
            if valid_sentence_count >= low:
                return top_n
        elif low <= valid_sentence_count <= high:
            return top_n
    # Fallback: should be unreachable given TOP_N_BRACKETS covers 1..inf,
    # but never silently return nothing (PRD 14.4 spirit: no silent failure).
    return config.TOP_N_BRACKETS[-1][2]


def run_sentence_pipeline(raw_page_texts: list[str]) -> SentencePipelineResult:
    """
    Full pipeline: raw per-page text -> cleaned -> header/footer stripped
    -> segmented -> deduped -> counted -> Top-N determined.
    """
    cleaned_pages = [clean_text(t) for t in raw_page_texts]
    de_boilerplated = remove_headers_and_footers(cleaned_pages)

    all_sentences: list[str] = []
    for page_text in de_boilerplated:
        all_sentences.extend(segment_sentences(page_text))

    valid_sentences = remove_empty_and_duplicate_sentences(all_sentences)
    count = len(valid_sentences)
    top_n = determine_top_n(count)

    return SentencePipelineResult(
        sentences=valid_sentences,
        valid_sentence_count=count,
        top_n=top_n,
    )