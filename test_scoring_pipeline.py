from backend.pipeline.scoring import score_sentences
from backend.pipeline.diversity_filter import apply_diversity_filter
from backend.profiles import get_profile


def main():

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
        "Total Amount payable is 50000.",
        "Payment terms are 30 days.",
        "This is unrelated text.",
    ]

    scored = score_sentences(
        sentences,
        metadata,
        profile
    )

    print("\nScored sentences:")
    for s in scored:
        print(s)

    print("\nApplying diversity filter:")

    result = apply_diversity_filter(
        scored,
        3
    )

    for r in result:
        print(r)


if __name__ == "__main__":
    main()