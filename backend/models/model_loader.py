"""
backend/models/model_loader.py

Implements PRD Section 11: load BART / MiniLM / NER / KeyBERT exactly
once, at Flask startup (app.py's create_app() / __main__ both call
load_all_models() before app.run()), rather than lazily inside request
handling -- so the first document processed doesn't pay a multi-second
model-load penalty, and so a broken model environment fails loudly at
startup instead of surfacing as a mysterious mid-pipeline error.

Public interface (matches backend/app.py's expectation):

    load_all_models() -> None
        Raises ModelLoadingError if a model fails to load.

Accessors for other pipeline modules (new, not yet consumed by any
implemented module as of this commit -- clause_detection.py is pure
regex/token-overlap and has no model dependency; summarization.py is
the first real consumer, via get_summarizer()):

    get_summarizer()       -> the loaded BART summarization pipeline
    get_semantic_model()   -> the loaded MiniLM sentence-embedding model
    get_ner_model()        -> the loaded NER model
    get_keyword_model()    -> the loaded KeyBERT model

    Each accessor raises ModelLoadingError if called before
    load_all_models() has run, or if that specific model failed to
    load (see partial-failure behavior below).

Partial-failure behavior:
    All four models are attempted independently -- one failing (e.g.
    missing optional dependency, no network access to fetch weights)
    doesn't stop the others from loading. If any failed, load_all_models()
    raises a single ModelLoadingError listing every failure, rather than
    stopping at the first one, so whoever's debugging deployment sees
    every broken piece at once instead of fixing one and re-running to
    discover the next.

    A model that failed to load is left as None in the module-level
    slot; its accessor still raises ModelLoadingError (rather than
    returning None for a caller to mishandle) if load_all_models()
    completed with that model missing. This means a deployment with,
    say, only BART broken can still be brought up (load_all_models()
    itself will raise once at startup, per its documented contract --
    see note below) but if a caller ever bypasses that startup check,
    get_summarizer() won't silently hand back None.

Note on "fail loud at startup" vs. "partial startup": PRD 11 / app.py's
create_app() calls load_all_models() and expects it to either succeed
or raise -- there's no documented "start up with 3 of 4 models" mode.
So a single failed model still fails the whole startup call, per the
existing app.py contract; the per-model try/except here exists to
*collect a complete failure report*, not to enable partial startup.
"""

import threading

from ..utils.errors import ModelLoadingError

# --- Model identifiers (PRD 11 doesn't pin exact checkpoints; these are
# the standard, commonly-available choices for each role and are the
# only thing that should need to change if a different checkpoint is
# preferred later). ---
_SUMMARIZATION_MODEL_NAME = "facebook/bart-large-cnn"
_SEMANTIC_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_NER_MODEL_NAME = "en_core_web_sm"  # spaCy model name, not a HF repo id

_lock = threading.Lock()
_loaded = False

_summarizer = None
_semantic_model = None
_ner_model = None
_keyword_model = None


def _load_summarizer():
    from transformers import pipeline
    return pipeline("summarization", model=_SUMMARIZATION_MODEL_NAME)


def _load_semantic_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_SEMANTIC_MODEL_NAME)


def _load_ner_model():
    import spacy
    return spacy.load(_NER_MODEL_NAME)


def _load_keyword_model(semantic_model):
    from keybert import KeyBERT
    # Reuse the already-loaded MiniLM embeddings for KeyBERT instead of
    # letting it pull its own default model -- one fewer model download,
    # and keeps "semantic similarity" consistent across the pipeline.
    if semantic_model is not None:
        return KeyBERT(model=semantic_model)
    return KeyBERT()


def load_all_models() -> None:
    """
    Load BART, MiniLM, NER, and KeyBERT once. Safe to call more than
    once (idempotent) -- a second call is a no-op rather than
    re-downloading/re-loading everything, since nothing about the
    already-loaded models changes between calls in this deployment
    (PRD 11: single-instance, single-primary-user).
    """
    global _loaded, _summarizer, _semantic_model, _ner_model, _keyword_model

    with _lock:
        if _loaded:
            return

        failures: list[str] = []

        try:
            _summarizer = _load_summarizer()
        except Exception as e:
            failures.append(f"summarization model ({_SUMMARIZATION_MODEL_NAME}): {e}")

        try:
            _semantic_model = _load_semantic_model()
        except Exception as e:
            failures.append(f"semantic model ({_SEMANTIC_MODEL_NAME}): {e}")

        try:
            _ner_model = _load_ner_model()
        except Exception as e:
            failures.append(f"NER model ({_NER_MODEL_NAME}): {e}")

        try:
            _keyword_model = _load_keyword_model(_semantic_model)
        except Exception as e:
            failures.append(f"KeyBERT model: {e}")

        if failures:
            detail = "; ".join(failures)
            raise ModelLoadingError(
                f"One or more models failed to load at startup: {detail}"
            )

        _loaded = True


def _require(model, name: str):
    if not _loaded or model is None:
        raise ModelLoadingError(
            f"{name} was requested before it finished loading. "
            f"Make sure load_all_models() has completed successfully."
        )
    return model


def get_summarizer():
    """Returns the loaded BART summarization pipeline (used by summarization.py)."""
    return _require(_summarizer, "Summarization model")


def get_semantic_model():
    """Returns the loaded MiniLM sentence-embedding model."""
    return _require(_semantic_model, "Semantic model")


def get_ner_model():
    """Returns the loaded NER model."""
    return _require(_ner_model, "NER model")


def get_keyword_model():
    """Returns the loaded KeyBERT model."""
    return _require(_keyword_model, "Keyword model")