# DocIntel

[![Live Demo](https://img.shields.io/badge/Live%20Demo-baba--ledger--2.onrender.com-brightgreen)](https://baba-ledger-2.onrender.com/)

**A calm place to read the paperwork.**

DocIntel is a document analysis tool for business paperwork — invoices, tenders, contracts, work orders, purchase orders, BOQs, delivery challans, and technical specs. Upload a PDF and it reads every page (OCR included), figures out what kind of document it is, pulls out the dates/amounts/parties that matter, flags clauses worth a second look, and hands back a summary plus a highlighted copy. Nothing is kept, nothing is shared.

---

## Table of contents

- [Features](#features)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Security](#security)
- [Testing](#testing)
- [Tech stack](#tech-stack)

---

## Features

- **Drag-and-drop PDF upload**, text-based or scanned (OCR runs only on pages that need it).
- **Automatic document classification** across nine business document types, each with its own extraction profile.
- **Metadata extraction** — dates, amounts, parties, and other type-specific fields, each with a confidence score.
- **Business clause detection**, flagged and linked back to the page they appear on.
- **Chunked executive summary** generation for long documents.
- **Business-critical sentence highlighting**, ranked and de-duplicated (MMR diversity filtering), rendered into a searchable, highlighted PDF.
- **Live progress**, not a spinner — the UI polls real pipeline stages (reading, OCR page-by-page, extraction, summarization, report building).
- **Nothing persists.** Uploaded files and all intermediate artifacts are deleted after the user downloads their results (or immediately, if a job fails).

## How it works

Each upload runs through an eleven-stage pipeline in a background thread, so the frontend can poll for specific, real progress instead of showing a generic loading spinner:

1. Upload PDF
2. Detect text-based vs. scanned, per page
3. OCR scanned pages only
4. Clean extracted text
5. Classify document type + classification strength
6. Extract document-specific metadata
7. Detect business clauses
8. Generate an executive summary (chunked for long documents)
9. Rank and highlight business-critical sentences (with diversity filtering)
10. Generate a searchable, highlighted PDF and a separate analysis report
11. Deliver both downloads, then delete all uploaded and intermediate files

**Supported document types:** Invoice, Tender, Contract, Purchase Order, Work Order, BOQ (Bill of Quantities), Delivery Challan, Technical Spec, and a Generic fallback profile.

## Project structure

```
docintel/
├── backend/
│   ├── app.py                    # Flask entrypoint: routes, job orchestration, rate limiting
│   ├── config.py                 # Every tunable value (limits, weights, thresholds)
│   ├── demo_pipeline.py
│   ├── demo_report_generator.py
│   ├── requirements.txt
│   ├── models/
│   │   └── model_loader.py       # Loads BART / MiniLM / NER / KeyBERT once at startup
│   ├── pipeline/
│   │   ├── ingestion.py          # Upload validation, page extraction
│   │   ├── page_router.py        # Text-based vs. scanned routing per page
│   │   ├── ocr.py                # Per-page OCR
│   │   ├── text_cleaning.py
│   │   ├── classification.py     # Document type + classification strength
│   │   ├── metadata_extraction.py
│   │   ├── clause_detection.py
│   │   ├── sentence_pipeline.py
│   │   ├── scoring.py             # Metadata / keyword / semantic scoring
│   │   ├── diversity_filter.py    # MMR near-duplicate suppression
│   │   ├── summarization.py       # Chunked summarization
│   │   ├── highlighting.py        # Renders the highlighted PDF
│   │   └── report_generator.py    # Renders the analysis report PDF
│   ├── profiles/                  # One extraction profile per document type
│   │   ├── invoice.py
│   │   ├── tender.py
│   │   ├── contract.py
│   │   ├── purchase_order.py
│   │   ├── work_order.py
│   │   ├── boq.py
│   │   ├── delivery_challan.py
│   │   ├── technical_spec.py
│   │   └── generic.py
│   ├── storage/
│   │   └── temp_manager.py        # Per-job temp workspace + cleanup
│   └── utils/
│       ├── errors.py              # PipelineError and friends
│       └── validators.py
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js                 # Theme toggle
│       ├── upload.js              # Drag/drop + upload submission
│       ├── progress.js            # Status polling + results rendering
│       └── theme.js
│
├── prototypes/
│   └── prototype.py
│
├── tests/
│   ├── fixtures/
│   ├── test_classification.py
│   ├── test_highlighting.py
│   └── test_scoring.py
│
├── check_metadata_fields.py
├── test_profiles.py
├── test_scoring_pipeline.py
├── test_scoring.py
├── test_sentence_scoring.py
├── test_summary.py
├── requirements.txt
├── runtime.txt
├── .python-version
├── .gitignore
├── .env                            # Not committed — see Getting started
└── README.md
```

> `__pycache__/` directories and `venv/` are omitted above — both are gitignored and generated automatically.

## Getting started

### Prerequisites

- Python (version pinned in `.python-version`)
- `pip`

### Backend

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

Create a `.env` file in the project root for any local secrets/overrides your deployment needs, then run:

```bash
python -m backend.app
```

The Flask app also serves the frontend directly (`static_folder="../frontend"`), so once it's running, the whole app is available at `http://localhost:5000`.

### Frontend

No build step — the frontend is plain HTML/CSS/JS served by Flask. Editing anything under `frontend/` takes effect on refresh.

## Configuration

Every tunable value lives in `backend/config.py` rather than scattered through the pipeline — change a number there after testing on real documents, don't hardcode thresholds inside pipeline modules. Notable ones:

| Setting | Default | Purpose |
|---|---|---|
| `MAX_FILE_SIZE_MB` | `50` | Max upload size, enforced both client-side and server-side |
| `MAX_PAGE_COUNT` | `200` | Max pages per document |
| `ACCEPTED_EXTENSIONS` | `{".pdf"}` | Allowed upload file types |
| `TOP_N_BRACKETS` | — | How many sentences get highlighted, scaled by document length |
| `METADATA_SCORE_WEIGHT` / `KEYWORD_SCORE_WEIGHT` / `SEMANTIC_SCORE_WEIGHT` | `0.50 / 0.25 / 0.25` | Sentence scoring weights |
| `DIVERSITY_SIMILARITY_THRESHOLD` | `0.85` | MMR near-duplicate suppression cutoff |
| `SUMMARY_CHUNK_SIZE_TOKENS` / `SUMMARY_CHUNK_OVERLAP_TOKENS` | `1024 / 128` | Summarization chunking |
| `OCR_CONFIDENCE_THRESHOLD` | `0.60` | Below this, an OCR'd field gets flagged in the UI |
| `MIN_TEXT_CHARS_PER_PAGE` | `40` | Below this, a page routes to OCR instead of direct text extraction |
| `CLASSIFICATION_MIN_EVIDENCE` / `_HIGH_SCORE` / `_MARGIN_HIGH` / `_MARGIN_MEDIUM` | — | Thresholds behind the High/Medium/Low classification strength badge |

## API reference

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/analyze` | Upload a PDF, kicks off analysis. Returns `202` with a `job_id`. **Rate-limited to 5 requests/minute per IP.** |
| `GET` | `/api/analyze/<job_id>/status` | Current pipeline stage, OCR page progress, done/error state |
| `GET` | `/api/analyze/<job_id>/result` | Final result: document type, classification strength, metadata, clauses, summary, highlight count |
| `GET` | `/api/analyze/<job_id>/download/<report\|highlighted>` | Download the analysis report or the highlighted PDF |
| `DELETE` | `/api/analyze/<job_id>` | Explicit cleanup — deletes the job's temp workspace |

All error responses are JSON: `{"error": "<message>"}`, with an appropriate HTTP status code.

## Security

- **Rate limiting** — uploads are capped at 5 per minute per IP (`/api/analyze` only; polling, results, and downloads are unaffected). Exceeding it returns `429` with a clear JSON error.
- **Max upload size** enforced at the Flask/Werkzeug layer via `MAX_CONTENT_LENGTH`, in addition to the pipeline's own validation — oversized bodies are rejected (`413`) before any file bytes are read.
- **File type validation** against `ACCEPTED_EXTENSIONS`, both as a fast pre-check and inside the ingestion pipeline's deeper, content-based validation.
- **Secure filenames** via Werkzeug's `secure_filename`.
- **No persistence** — job state lives in memory only (no database in v1), and every job's temp files are deleted after download or immediately on failure.

> The in-memory rate limiter and job store are both single-instance by design (see comments in `app.py`). Move both to a shared store (e.g. Redis) before running more than one worker process.

## Testing

```bash
pytest
```

Test files live both under `tests/` (classification, highlighting, scoring) and at the project root (`test_profiles.py`, `test_scoring_pipeline.py`, `test_scoring.py`, `test_sentence_scoring.py`, `test_summary.py`).

## Tech stack

- **Backend:** Flask, Flask-Limiter
- **NLP/ML:** BART (summarization), MiniLM, NER, KeyBERT
- **Frontend:** Vanilla HTML/CSS/JS — no framework, no build step
