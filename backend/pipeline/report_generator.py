"""
backend/pipeline/report_generator.py

Implements PRD Section 9: the Analysis Report PDF, the last pipeline
stage before Stage 11 (Deliver downloads, then delete all uploaded/
intermediate files, PRD Section 13).

Public interface (matches backend/app.py's expectation):

    generate_report(
        doc_type: str,
        classification: "ClassificationResult | None",
        metadata: dict,
        clauses: list[dict],
        summary: str,
        highlights: list["ScoredSentence"],
        out_path: str,
    ) -> None

    Raises ReportGenerationError (utils.errors) if the PDF cannot be
    built or saved at all. Missing/partial *content* -- an empty
    metadata dict, no detected clauses, an empty summary because
    summarization.py degraded gracefully, an empty highlights list --
    is never an error here; each section falls back to an explicit
    "not available" line instead (PRD 14.4: never fail silently, but
    also never fail loudly over something that's a legitimate, expected
    shape of a partially-successful pipeline run).

Design notes:

    This module reuses PyMuPDF (fitz) rather than introducing a new
    PDF-writing dependency -- highlighting.py already depends on it for
    Stage 10, so the report shares that dependency instead of adding
    reportlab/weasyprint/etc. for one more module.

    Unlike highlighting.py (which opens and edits the user's *existing*
    PDF), this module builds a brand-new PDF from scratch, so it can't
    reuse highlighting.py's page-by-page annotation approach. Instead
    it implements a small, self-contained text-flow layout: content is
    wrapped into lines that fit the page width (using
    fitz.get_text_length against the actual font/size being drawn, not
    a guessed character count) and paginated top-to-bottom, opening a
    new page whenever the next line/heading would run past the bottom
    margin. This is intentionally simple -- PRD 9 asks for a readable,
    structured report, not pixel-perfect desktop-publishing layout.

    Section order mirrors the order app.py already passes arguments in
    (classification -> metadata -> clauses -> summary -> highlights),
    so the report reads in the same sequence the pipeline produced the
    data, rather than an arbitrary reshuffling.

    A single `_get(obj, name, default)` accessor is used everywhere a
    value is pulled from pipeline output, because those outputs mix
    dataclasses (ClassificationResult, ScoredSentence) and plain dicts
    (metadata's per-field dict, each clause dict) -- one helper avoids
    duplicating "is this a dict or an object" branching in every
    section, and papers over a caller passing a slightly different
    shape (e.g. a dict instead of a dataclass) without crashing Stage
    10/11 of the pipeline over a report-formatting detail.
"""

from typing import Any, Optional

import fitz  # PyMuPDF

from ..utils.errors import ReportGenerationError

# --- Page geometry ---
_PAGE_WIDTH, _PAGE_HEIGHT = fitz.paper_size("a4")
_MARGIN = 50
_CONTENT_WIDTH = _PAGE_WIDTH - (2 * _MARGIN)

# --- Typography (PyMuPDF base-14 fonts only, so no font files to ship) ---
_FONT_BODY = "helv"
_FONT_BOLD = "hebo"
_SIZE_TITLE = 20
_SIZE_SECTION_HEADING = 14
_SIZE_BODY = 10
_LINE_HEIGHT_FACTOR = 1.45  # vertical spacing between wrapped lines

_COLOR_TEXT = (0.10, 0.10, 0.10)
_COLOR_MUTED = (0.45, 0.45, 0.45)
_COLOR_HEADING = (0.05, 0.05, 0.30)
_COLOR_RULE = (0.75, 0.75, 0.75)

# Strength labels get a small color cue so a reader scanning the report
# can spot a Low-confidence classification at a glance.
_STRENGTH_COLORS = {
    "high": (0.10, 0.45, 0.10),
    "medium": (0.60, 0.45, 0.0),
    "low": (0.65, 0.10, 0.10),
}

# Highlights are capped in the report even if a huge document produced
# an unusually large Top-N, so the report stays a report and not a
# reprint of the entire document (PRD 8.6 sizes highlighting; this is
# just a defensive display cap independent of that).
_MAX_HIGHLIGHTS_DISPLAYED = 50


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """
    Read `name` off `obj` regardless of whether obj is a dataclass/object
    (ClassificationResult, ScoredSentence, ...) or a plain dict (a
    metadata field's {"value", "confidence"}, a clause dict). Returns
    `default` rather than raising if obj is None or lacks the attribute/
    key -- callers here should never crash the report over an
    unexpectedly-shaped upstream value.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _enum_value(x: Any, default: str = "unknown") -> str:
    """Unwrap an Enum's .value (ClassificationStrength) or fall back to
    str(x); tolerates being handed a plain string too."""
    if x is None:
        return default
    value = getattr(x, "value", x)
    return str(value)


def _wrap_text(text: str, fontname: str, fontsize: float, max_width: float) -> list[str]:
    """
    Greedy word-wrap `text` into lines that fit within `max_width`,
    measured with the real font metrics (fitz.get_text_length) rather
    than an approximate character count, so justified-looking margins
    hold regardless of font.
    """
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if fitz.get_text_length(candidate, fontname=fontname, fontsize=fontsize) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            # A single word wider than the whole line (long URL/ID with
            # no spaces) still has to go somewhere; place it on its own
            # line rather than dropping it.
            current = word
    if current:
        lines.append(current)
    return lines


class _ReportBuilder:
    """
    Minimal top-to-bottom text-flow writer over a fresh fitz.Document.
    Tracks a vertical cursor on the current page and opens a new page
    whenever the next element would overflow the bottom margin.
    """

    def __init__(self) -> None:
        self.doc = fitz.open()
        self._page = None
        self._cursor_y = 0.0
        self._new_page()

    def _new_page(self) -> None:
        self._page = self.doc.new_page(width=_PAGE_WIDTH, height=_PAGE_HEIGHT)
        self._cursor_y = _MARGIN

    def _ensure_space(self, height_needed: float) -> None:
        if self._cursor_y + height_needed > _PAGE_HEIGHT - _MARGIN:
            self._new_page()

    def add_title(self, text: str) -> None:
        self._ensure_space(_SIZE_TITLE * _LINE_HEIGHT_FACTOR)
        self._page.insert_text(
            (_MARGIN, self._cursor_y + _SIZE_TITLE),
            text, fontsize=_SIZE_TITLE, fontname=_FONT_BOLD, color=_COLOR_HEADING,
        )
        self._cursor_y += _SIZE_TITLE * _LINE_HEIGHT_FACTOR + 6
        self._add_rule()

    def add_section_heading(self, text: str) -> None:
        self._ensure_space(_SIZE_SECTION_HEADING * _LINE_HEIGHT_FACTOR + 10)
        self._cursor_y += 10  # breathing room before a new section
        self._page.insert_text(
            (_MARGIN, self._cursor_y + _SIZE_SECTION_HEADING),
            text, fontsize=_SIZE_SECTION_HEADING, fontname=_FONT_BOLD, color=_COLOR_HEADING,
        )
        self._cursor_y += _SIZE_SECTION_HEADING * _LINE_HEIGHT_FACTOR

    def _add_rule(self) -> None:
        self._page.draw_line(
            (_MARGIN, self._cursor_y), (_PAGE_WIDTH - _MARGIN, self._cursor_y),
            color=_COLOR_RULE, width=0.75,
        )
        self._cursor_y += 10

    def add_paragraph(self, text: str, *, bold: bool = False,
                       size: float = _SIZE_BODY, color=_COLOR_TEXT,
                       indent: float = 0.0) -> None:
        """Wrap and draw `text` line-by-line, paginating as needed."""
        fontname = _FONT_BOLD if bold else _FONT_BODY
        max_width = _CONTENT_WIDTH - indent
        for line in _wrap_text(text, fontname, size, max_width):
            line_height = size * _LINE_HEIGHT_FACTOR
            self._ensure_space(line_height)
            self._page.insert_text(
                (_MARGIN + indent, self._cursor_y + size),
                line, fontsize=size, fontname=fontname, color=color,
            )
            self._cursor_y += line_height

    def add_spacer(self, height: float = 8.0) -> None:
        self._cursor_y += height

    def finalize_with_page_numbers(self) -> None:
        """Stamp 'Page N of M' on every page once the total is known --
        this has to happen after all content is laid out, since laying
        out earlier sections is what determines how many pages exist."""
        total = self.doc.page_count
        for i in range(total):
            page = self.doc[i]
            label = f"Page {i + 1} of {total}"
            label_width = fitz.get_text_length(label, fontname=_FONT_BODY, fontsize=8)
            page.insert_text(
                (_PAGE_WIDTH - _MARGIN - label_width, _PAGE_HEIGHT - (_MARGIN / 2)),
                label, fontsize=8, fontname=_FONT_BODY, color=_COLOR_MUTED,
            )

    def save(self, out_path: str) -> None:
        self.doc.save(out_path, garbage=4, deflate=True)

    def close(self) -> None:
        self.doc.close()


# ---------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------

def _write_header_section(rb: _ReportBuilder, doc_type: str, classification: Any) -> None:
    rb.add_title("Document Analysis Report")

    rb.add_paragraph(f"Document Type: {doc_type or 'Unknown'}", bold=True, size=12)

    strength = _enum_value(_get(classification, "strength"), default=None)
    if strength:
        color = _STRENGTH_COLORS.get(strength, _COLOR_TEXT)
        rb.add_paragraph(f"Classification Strength: {strength.upper()}", bold=True, color=color)
    else:
        rb.add_paragraph("Classification Strength: Not available.", color=_COLOR_MUTED)

    top_score = _get(classification, "top_score")
    margin = _get(classification, "margin")
    if top_score is not None and margin is not None:
        rb.add_paragraph(f"Top match score: {top_score:.2f}  |  Margin over next best type: {margin:.2f}",
                          size=9, color=_COLOR_MUTED)

    if _get(classification, "use_generic_fallback", False):
        rb.add_paragraph(
            "This document did not strongly match a known type; results below "
            "use a generic profile and should be reviewed carefully.",
            size=9, color=_STRENGTH_COLORS["low"],
        )

    rb.add_spacer(6)


def _write_metadata_section(rb: _ReportBuilder, metadata: dict) -> None:
    rb.add_section_heading("Extracted Metadata")

    if not metadata:
        rb.add_paragraph("No metadata fields were extracted for this document.", color=_COLOR_MUTED)
        return

    for field_name, result in metadata.items():
        value = _get(result, "value")
        confidence = _get(result, "confidence", 0.0) or 0.0

        if value:
            rb.add_paragraph(f"{field_name}:", bold=True, indent=0)
            rb.add_paragraph(f"{value}   (confidence: {confidence * 100:.0f}%)",
                              indent=14, size=9.5,
                              color=_COLOR_TEXT if confidence >= 0.6 else _COLOR_MUTED)
        else:
            rb.add_paragraph(f"{field_name}: Not found.", indent=0, color=_COLOR_MUTED)
        rb.add_spacer(3)


def _write_clauses_section(rb: _ReportBuilder, clauses: list) -> None:
    rb.add_section_heading("Detected Business Clauses")

    if not clauses:
        rb.add_paragraph("No business clauses were detected in this document.", color=_COLOR_MUTED)
        return

    for clause in clauses:
        category = _get(clause, "category", "Uncategorized")
        page = _get(clause, "page")
        text = _get(clause, "text", "")

        label = f"[{category}]" + (f" (page {page})" if page is not None else "")
        rb.add_paragraph(label, bold=True, size=9.5)
        if text:
            rb.add_paragraph(text, indent=14, size=9.5)
        rb.add_spacer(5)


def _write_summary_section(rb: _ReportBuilder, summary: str) -> None:
    rb.add_section_heading("Executive Summary")

    if summary and summary.strip():
        rb.add_paragraph(summary.strip())
    else:
        rb.add_paragraph(
            "A summary could not be generated for this document.", color=_COLOR_MUTED,
        )


def _write_highlights_section(rb: _ReportBuilder, highlights: list) -> None:
    rb.add_section_heading("Business Highlights")

    if not highlights:
        rb.add_paragraph("No business-critical sentences were identified.", color=_COLOR_MUTED)
        return

    shown = highlights[:_MAX_HIGHLIGHTS_DISPLAYED]
    omitted = len(highlights) - len(shown)

    for i, item in enumerate(shown, start=1):
        sentence = _get(item, "sentence", "")
        score = _get(item, "score")
        if not sentence:
            continue

        rb.add_paragraph(f"{i}. {sentence}", size=9.5)
        if score is not None:
            rb.add_paragraph(f"(relevance score: {score:.2f})", indent=14, size=8, color=_COLOR_MUTED)
        rb.add_spacer(4)

    if omitted > 0:
        rb.add_paragraph(f"...and {omitted} additional highlight(s) not shown in this report.",
                          color=_COLOR_MUTED, size=9)


# ---------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------

def generate_report(
    doc_type: str,
    classification: Optional[Any],
    metadata: dict,
    clauses: list,
    summary: str,
    highlights: list,
    out_path: str,
) -> None:
    """
    Build the Analysis Report PDF (PRD Section 9) from the outputs of
    every earlier pipeline stage and save it to `out_path`.

    Every argument is treated as optional/possibly-partial content
    (PRD 14.4): a falsy/empty/None value for any of metadata, clauses,
    summary, highlights, or classification produces an explicit
    "not available"-style line in that section rather than raising or
    leaving the section blank with no explanation.

    Raises ReportGenerationError if the PDF cannot be constructed or
    saved at all (e.g. an unwritable out_path) -- that failure is
    real and should propagate to app.py's existing PipelineError
    handling, unlike missing *content*, which is expected and handled
    per-section above.
    """
    rb = _ReportBuilder()
    try:
        _write_header_section(rb, doc_type, classification)
        _write_metadata_section(rb, metadata or {})
        _write_clauses_section(rb, clauses or [])
        _write_summary_section(rb, summary or "")
        _write_highlights_section(rb, highlights or [])

        rb.finalize_with_page_numbers()
        rb.save(out_path)
    except Exception as e:
        raise ReportGenerationError() from e
    finally:
        rb.close()