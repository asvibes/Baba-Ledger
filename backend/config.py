"""
Baba's Ledger - Configuration Module
PRD Section 14.5: every tunable value lives here, not scattered through
business logic. Change a number here after testing on real documents;
never hardcode a threshold inside a pipeline module.
"""

# --- Upload limits (PRD 14.1) ---
MAX_FILE_SIZE_MB = 50
MAX_PAGE_COUNT = 200
ACCEPTED_EXTENSIONS = {".pdf"}

# --- Business Highlights (PRD 8.6) ---
# (min_sentences_inclusive, max_sentences_inclusive_or_None, top_n)
TOP_N_BRACKETS = [
    (1, 20, 5),
    (21, 100, 10),
    (101, 300, 15),
    (301, None, 20),
]

# --- Scoring weights (PRD 8.1) ---
METADATA_SCORE_WEIGHT = 0.50
KEYWORD_SCORE_WEIGHT = 0.25
SEMANTIC_SCORE_WEIGHT = 0.25

# --- Metadata field priority multipliers (PRD 8.2) ---
FIELD_PRIORITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}

# --- Diversity filter / MMR (PRD 8.5) ---
DIVERSITY_SIMILARITY_THRESHOLD = 0.85

# --- Summarization chunking (PRD 8.8) ---
SUMMARY_CHUNK_SIZE_TOKENS = 1024
SUMMARY_CHUNK_OVERLAP_TOKENS = 128

# --- OCR ---
OCR_CONFIDENCE_THRESHOLD = 0.60          # per-word confidence floor before flagging (PRD 9.1)
MIN_TEXT_CHARS_PER_PAGE = 40              # below this, a page routes to OCR (PRD 5.1)

# --- Classification Strength (PRD 6.1) ---
CLASSIFICATION_MIN_EVIDENCE = 0.30        # absolute floor: min weighted score for a type to be considered at all
CLASSIFICATION_HIGH_SCORE = 0.75          # min weighted score for "High" (also needs margin below)
CLASSIFICATION_MARGIN_HIGH = 0.20         # min gap vs. runner-up for "High"
CLASSIFICATION_MARGIN_MEDIUM = 0.08       # min gap vs. runner-up for "Medium"
# Below CLASSIFICATION_MIN_EVIDENCE, or margin below CLASSIFICATION_MARGIN_MEDIUM -> "Low"

# --- Text cleaning ---
STRIP_INVISIBLE_CHARS = True
NORMALIZE_LINE_BREAKS = True

# --- Deployment / language ---
SUPPORTED_LANGUAGE = "en"