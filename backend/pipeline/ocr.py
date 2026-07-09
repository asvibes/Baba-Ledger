"""
Pipeline Stage 3: Perform OCR on scanned pages only (PRD Section 5.2).

Workflow (PRD 5.2): rasterize the scanned page -> run EasyOCR -> collect
text and bounding boxes -> return them so the caller can merge into the
document's text stream (app.py, Stage 3) and/or build the invisible
text layer + highlight annotations for the searchable PDF (highlighting.py,
Stage 10.2). Both callers share this one function so OCR logic and the
EasyOCR reader are never duplicated.

Bounding boxes are returned in PDF point space (the same coordinate
system PyMuPDF uses for the page), not raw image pixel space, so callers
never need to know the rasterization DPI used internally.
"""
import threading
from dataclasses import dataclass

from ..utils.errors import OCRFailureError

# Rasterization resolution for OCR. 300 DPI is a standard sweet spot for
# accuracy on real-world scans without exploding memory/runtime; PDF
# points are 72 per inch, so this is the zoom factor passed to PyMuPDF.
_OCR_DPI = 300
_ZOOM = _OCR_DPI / 72.0

_LANGUAGES = ["en"]  # PRD 14.1: Version 1 supports English documents only


@dataclass
class OcrBoundingBox:
    """One recognized text fragment (EasyOCR groups characters into
    words/short phrases) and its location in PDF point space."""
    text: str
    bbox: list  # [(x0, y0), (x1, y1), (x2, y2), (x3, y3)] quad corners, PDF points
    confidence: float


@dataclass
class OcrPageResult:
    text: str
    bounding_boxes: list  # list[OcrBoundingBox], in reading order
    confidence: float  # page-level average of fragment confidences


# --- EasyOCR reader: loaded lazily, once, on first use ---
#
# model_loader.load_all_models() (PRD 11) is documented as loading the
# Hugging Face models (BART/MiniLM/NER/KeyBERT) at Flask startup; EasyOCR
# is a separate, non-Hugging-Face dependency, so this module manages its
# own singleton rather than assuming model_loader covers it. A lock
# guards initialization since app.py runs one background thread per job,
# and two jobs could reach first-use concurrently.
_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:  # re-check inside the lock
                import easyocr
                _reader = easyocr.Reader(_LANGUAGES, gpu=False)
    return _reader


def _rasterize_page(pdf_path: str, page_number: int) -> bytes:
    """Render one page (1-indexed) to a PNG image for OCR."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM), colorspace=fitz.csRGB)
        return pix.tobytes("png")
    finally:
        doc.close()


def _image_quad_to_pdf_points(quad_px) -> list:
    """Undo the rasterization zoom to map an EasyOCR pixel quad back to
    PDF point space."""
    return [(x / _ZOOM, y / _ZOOM) for x, y in quad_px]


def run_ocr_on_page(pdf_path: str, page_number: int) -> OcrPageResult:
    """
    Run OCR on a single page (1-indexed) of pdf_path.

    Raises OCRFailureError(page_number) if the page cannot be rasterized
    or OCR'd. Per PRD 14.4 this is caught by the caller and treated as a
    per-page failure - the rest of the document keeps processing - not a
    fatal error for the whole job.
    """
    try:
        image_bytes = _rasterize_page(pdf_path, page_number)
        reader = _get_reader()
        raw_results = reader.readtext(image_bytes)
    except Exception as e:
        raise OCRFailureError(page_number) from e

    if not raw_results:
        return OcrPageResult(text="", bounding_boxes=[], confidence=0.0)

    # EasyOCR doesn't guarantee strict reading order for multi-column or
    # skewed pages; sort by vertical position first (bucketed to tolerate
    # slight skew), then horizontal - a reasonable approximation for the
    # single-column business documents this platform targets.
    def _sort_key(item):
        quad_px, _text, _conf = item
        y_center = sum(pt[1] for pt in quad_px) / 4
        x_left = min(pt[0] for pt in quad_px)
        return (round(y_center / 5), x_left)

    raw_results = sorted(raw_results, key=_sort_key)

    fragments = []
    confidences = []
    for quad_px, text, conf in raw_results:
        text = text.strip()
        if not text:
            continue
        fragments.append(
            OcrBoundingBox(
                text=text,
                bbox=_image_quad_to_pdf_points(quad_px),
                confidence=float(conf),
            )
        )
        confidences.append(float(conf))

    full_text = " ".join(f.text for f in fragments)
    page_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return OcrPageResult(text=full_text, bounding_boxes=fragments, confidence=page_confidence)