"""
Pipeline Stage 5: Classify the document type (PRD Section 6) and
determine Classification Strength (PRD Section 6.1).

Rule-assisted, not machine-learning: matches extracted text against
keyword sets and structural patterns per document type. Reports
Classification Strength (High/Medium/Low) rather than a percentage,
because a rule-based score is not a true statistical probability.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from .. import config
from ..profiles import PROFILE_REGISTRY, GENERIC_PROFILE


class ClassificationStrength(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TypeScore:
    doc_type: str
    keyword_score: float
    structural_score: float
    combined_score: float


@dataclass
class ClassificationResult:
    predicted_type: str
    strength: ClassificationStrength
    top_score: float
    margin: float
    all_scores: list[TypeScore] = field(default_factory=list)
    use_generic_fallback: bool = False

    @property
    def is_ambiguous(self) -> bool:
        return self.strength == ClassificationStrength.LOW


def _keyword_score(text_lower: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text_lower)
    return hits / len(keywords)


def _structural_score(text_lower: str, patterns: list[str]) -> float:
    if not patterns:
        return 0.0
    hits = sum(1 for pat in patterns if re.search(pat, text_lower, re.IGNORECASE))
    return hits / len(patterns)


def _score_all_types(text: str) -> list[TypeScore]:
    text_lower = text.lower()
    scores = []
    for doc_type, profile in PROFILE_REGISTRY.items():
        kw_score = _keyword_score(text_lower, profile["keywords"])
        struct_score = _structural_score(text_lower, profile["structural_patterns"])
        # Classification-time combination: keyword and structural evidence only.
        # (Full metadata/keyword/semantic weighting from PRD 8.1 applies later,
        # during Business Highlights scoring on the already-classified document.)
        combined = 0.5 * kw_score + 0.5 * struct_score
        scores.append(TypeScore(doc_type, kw_score, struct_score, combined))
    return sorted(scores, key=lambda s: s.combined_score, reverse=True)


def classify_document(text: str) -> ClassificationResult:
    """
    Classify a document's cleaned text and determine Classification
    Strength using the hybrid approach from PRD 6.1:
      - weighted score (keywords + structural patterns)
      - absolute minimum-evidence floor
      - margin check between top two types (ambiguous/mixed-document signal)
    """
    scores = _score_all_types(text)

    if not scores:
        return ClassificationResult(
            predicted_type=GENERIC_PROFILE["type"],
            strength=ClassificationStrength.LOW,
            top_score=0.0,
            margin=0.0,
            all_scores=[],
            use_generic_fallback=True,
        )

    top = scores[0]
    runner_up = scores[1] if len(scores) > 1 else None
    margin = top.combined_score - (runner_up.combined_score if runner_up else 0.0)

    if top.combined_score < config.CLASSIFICATION_MIN_EVIDENCE:
        strength = ClassificationStrength.LOW
    elif (
        top.combined_score >= config.CLASSIFICATION_HIGH_SCORE
        and margin >= config.CLASSIFICATION_MARGIN_HIGH
    ):
        strength = ClassificationStrength.HIGH
    elif margin >= config.CLASSIFICATION_MARGIN_MEDIUM:
        strength = ClassificationStrength.MEDIUM
    else:
        strength = ClassificationStrength.LOW

    return ClassificationResult(
        predicted_type=top.doc_type,
        strength=strength,
        top_score=top.combined_score,
        margin=margin,
        all_scores=scores,
        use_generic_fallback=(strength == ClassificationStrength.LOW),
    )