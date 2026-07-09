from backend.pipeline.scoring import score_sentences
from backend.profiles import get_profile
from backend.pipeline.metadata_extraction import extract_metadata


def main():

    print("Testing sentence scoring\n")

    profile = get_profile("invoice")

    metadata = {
        "Invoice Number": {
            "value": "INV-1001",
            "confidence": 0.95
        },
        "Vendor": {
            "value": "ABC Pvt Ltd",
            "confidence": 0.85
        },
        "Total Amount": {
            "value": "50000",
            "confidence": 0.90
        }
    }

    sentences = [
        "Invoice Number: INV-1001 issued by ABC Pvt Ltd.",
        "The payment terms are 30 days.",
        "This document contains general information."
    ]

    results = score_sentences(
        sentences,
        metadata,
        profile
    )

    for r in results:
        print("\nSentence:")
        print(r.sentence)

        print("Score:", r.score)
        print("Metadata:", r.metadata_score)
        print("Keyword:", r.keyword_score)
        print("Semantic:", r.semantic_score)


if __name__ == "__main__":
    main()