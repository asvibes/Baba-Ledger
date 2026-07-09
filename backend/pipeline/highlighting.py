"""
Pipeline Stage 10: Generate the searchable highlighted PDF (PRD Sections
10, 10.1, 10.2).

app.py always passes an empty page_map (routing/OCR bounding-box data
from Stages 2/3 is discarded after those stages - app.py's Stage 2/3
loop keeps only `.text`). Rather than plumb that data through app.py,
this module independently re-derives page routing (reusing page_router
so the text-vs-scanned decision logic is never duplicated) and re-runs
OCR on scanned pages to obtain the bounding boxes it needs. `page_map`
is accepted for interface compatibility but is not used.

10.1 Text-based pages: locate each highlighted sentence via PyMuPDF's
text search and draw a highlight annotation directly on existing content.

10.2 Scanned pages: EasyOCR's bounding boxes are used to (a) embed an
invisible OCR text layer behind the page image, so the whole output PDF
stays searchable/copyable even though a page is really just a photo,
and (b) draw highlight annotations over the fragments making up a
selected sentence. Per PRD 10.2, highlights are real PDF annotations on
a real text layer - never baked into a re-rendered image.
"""
import difflib
import re

import fitz  # PyMuPDF

from . import ocr as ocr_module
from . import page_router
from ..utils.errors import ReportGenerationError

# Below this ratio, a fuzzy match against OCR'd text on a scanned page is
# considered unreliable and the highlight is skipped for that page rather
# than risk highlighting the wrong sentence (extends PRD 5.3's "never
# invent/guess" principle to highlight placement).
_FUZZY_MATCH_THRESHOLD = 0.75

# PDF text render mode (Tr operator): 3 = neither fill nor stroke, i.e.
# present for search/copy but not visible - this is the "invisible" in
# "invisible OCR text layer" (PRD 10.2).
_INVISIBLE_RENDER_MODE = 3


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _embed_invisible_text_layer(page, ocr_result: "ocr_module.OcrPageResult") -> None:
    """Insert each OCR fragment as invisible text at its recognized
    location, so the page becomes searchable/copyable without changing
    how it looks."""
    for frag in ocr_result.bounding_boxes:
        xs = [pt[0] for pt in frag.bbox]
        ys = [pt[1] for pt in frag.bbox]
        left, top, bottom = min(xs), min(ys), max(ys)
        height = max(bottom - top, 1.0)
        fontsize = max(height * 0.85, 4.0)  # approximate glyph size from box height
        try:
            page.insert_text(
                (left, bottom),
                frag.text,
                fontsize=fontsize,
                render_mode=_INVISIBLE_RENDER_MODE,
            )
        except Exception:
            # One fragment failing to embed (e.g. unsupported glyph)
            # shouldn't drop the rest of the page's text layer.
            continue


def _highlight_on_text_page(page, sentence: str) -> bool:
    quads = page.search_for(sentence, quads=True)
    if not quads:
        # Text cleaning (whitespace/line-break normalization, PRD 5.3)
        # can shift a long sentence just enough that an exact full-
        # sentence search misses even though the words are unchanged.
        # Fall back to a shorter leading fragment before giving up.
        words = sentence.split()
        if len(words) > 6:
            quads = page.search_for(" ".join(words[:6]), quads=True)
    if not quads:
        return False
    page.add_highlight_annot(quads)
    return True


def _highlight_on_scanned_page(page, ocr_result: "ocr_module.OcrPageResult", sentence: str) -> bool:
    fragments = ocr_result.bounding_boxes
    if not fragments:
        return False

    joined_parts, offsets, cursor = [], [], 0
    for frag in fragments:
        norm = _normalize(frag.text)
        offsets.append((cursor, cursor + len(norm)))
        joined_parts.append(norm)
        cursor += len(norm) + 1  # +1 for the joining space
    page_text = " ".join(joined_parts)
    sentence_norm = _normalize(sentence)

    matcher = difflib.SequenceMatcher(None, page_text, sentence_norm)
    match = matcher.find_longest_match(0, len(page_text), 0, len(sentence_norm))
    if match.size == 0:
        return False
    if match.size / max(len(sentence_norm), 1) < _FUZZY_MATCH_THRESHOLD:
        return False

    match_start, match_end = match.a, match.a + match.size
    matched_fragments = [
        frag for frag, (start, end) in zip(fragments, offsets)
        if end > match_start and start < match_end
    ]
    if not matched_fragments:
        return False

    quads = [fitz.Quad([fitz.Point(x, y) for x, y in frag.bbox]) for frag in matched_fragments]
    page.add_highlight_annot(quads)
    return True


def _place_highlight(doc, routing, scanned_ocr: dict, sentence: str) -> bool:
    for r in routing:
        page = doc[r.page_number - 1]
        if r.page_type.value == "text_based":
            if _highlight_on_text_page(page, sentence):
                return True
        else:
            ocr_result = scanned_ocr.get(r.page_number)
            if ocr_result and _highlight_on_scanned_page(page, ocr_result, sentence):
                return True
    # Not found anywhere - skipping this one highlight is preferable to
    # guessing at its location. The report lists it independently either way.
    return False


def highlight_pdf(pdf_path: str, highlights: list, page_map: dict, out_path: str) -> None:
    """
    Produce the searchable, highlighted PDF (PRD Section 10).

    highlights: ranked scoring.py output (post diversity-filter). Only
    `.sentence` is used here - ranking/score fields belong to the report.
    page_map: unused - see module docstring.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ReportGenerationError() from e

    try:
        routing = [
            page_router.route_page(i + 1, doc[i].get_text())
            for i in range(doc.page_count)
        ]

        # Build the invisible text layer for every scanned page up front
        # (PRD 10.2 intends the whole document to end up searchable, not
        # only the pages that happen to contain a highlight).
        scanned_ocr = {}
        for r in routing:
            if r.page_type.value != "scanned":
                continue
            try:
                result = ocr_module.run_ocr_on_page(pdf_path, r.page_number)
            except Exception:
                # PRD 14.4: one page's OCR failure shouldn't kill the
                # whole highlighted-PDF output; it just won't get a text
                # layer or be eligible for highlighting.
                continue
            scanned_ocr[r.page_number] = result
            _embed_invisible_text_layer(doc[r.page_number - 1], result)

        for item in highlights:
            sentence = getattr(item, "sentence", None)
            if sentence:
                _place_highlight(doc, routing, scanned_ocr, sentence)

        doc.save(out_path, garbage=4, deflate=True)
    finally:
        doc.close()