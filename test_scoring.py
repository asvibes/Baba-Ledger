"""
Tests for backend.pipeline.scoring.calculate_metadata_score

Validates:
- Real metadata scoring for all profiles
- field_name -> metadata_fields key conversion
- confidence weighting
- normalization
- missing fields handling
- unknown fields handling
"""

from backend.pipeline.scoring import calculate_metadata_score
from backend.profiles import PROFILE_REGISTRY


# Realistic extracted metadata samples
SAMPLE_METADATA = {

    "invoice": {
        "Invoice Number": {
            "value": "INV-1001",
            "confidence": 0.95
        },
        "Vendor": {
            "value": "ABC Pvt Ltd",
            "confidence": 0.95
        },
        "Invoice Date": {
            "value": "09-07-2026",
            "confidence": 0.95
        },
        "Total Amount": {
            "value": "50000",
            "confidence": 0.95
        },
        "GST Tax": {
            "value": "9000",
            "confidence": 0.95
        },
    },


    "tender": {
        "Tender Number": {
            "value": "TN-101",
            "confidence": 0.9
        },
        "Project Name": {
            "value": "Highway Project",
            "confidence": 0.85
        },
        "Estimated Project Cost": {
            "value": "5000000",
            "confidence": 0.9
        },
        "Bid Submission Date": {
            "value": "20-08-2026",
            "confidence": 0.95
        },
    },


    "contract": {
        "Contract Number": {
            "value": "CON-2026",
            "confidence": 0.95
        },
        "Parties Involved": {
            "value": "Company A and Company B",
            "confidence": 0.9
        },
        "Effective Date": {
            "value": "01-01-2026",
            "confidence": 0.9
        },
    },


    "work_order": {
        "Work Order Number": {
            "value": "WO-500",
            "confidence": 0.95
        },
        "Project Name": {
            "value": "Building Construction",
            "confidence": 0.9
        },
        "Contractor": {
            "value": "XYZ Contractors",
            "confidence": 0.85
        },
        "Completion Timeline": {
            "value": "6 months",
            "confidence": 0.9
        },
    },


    "purchase_order": {
        "Po Number": {
            "value": "PO-900",
            "confidence": 0.95
        },
        "Vendor": {
            "value": "Supplier Ltd",
            "confidence": 0.9
        },
        "Material Details": {
            "value": "Steel and Cement",
            "confidence": 0.9
        },
        "Quantity": {
            "value": "1000",
            "confidence": 0.85
        },
    },


    "boq": {
        "Item Description": {
            "value": "Steel Rod",
            "confidence": 0.9
        },
        "Quantity": {
            "value": "500",
            "confidence": 0.95
        },
        "Unit": {
            "value": "Kg",
            "confidence": 0.9
        },
        "Estimated Cost": {
            "value": "200000",
            "confidence": 0.95
        },
    },


    "delivery_challan": {
        "Challan Number": {
            "value": "DC-100",
            "confidence": 0.95
        },
        "Vendor": {
            "value": "ABC Supplier",
            "confidence": 0.9
        },
        "Project Site": {
            "value": "Lucknow Site",
            "confidence": 0.85
        },
        "Material Delivered": {
            "value": "Cement Bags",
            "confidence": 0.9
        },
        "Quantity": {
            "value": "500",
            "confidence": 0.9
        },
        "Delivery Date": {
            "value": "09-07-2026",
            "confidence": 0.95
        },
        "Received By": {
            "value": "Manager",
            "confidence": 0.8
        },
    },


    "technical_spec": {
        "Applicable Standards": {
            "value": "IS 456",
            "confidence": 0.9
        },
        "Material Specifications": {
            "value": "Grade M30 Concrete",
            "confidence": 0.9
        },
        "Safety Requirements": {
            "value": "Helmet required",
            "confidence": 0.85
        },
    },


    "generic": {
        "Dates": {
            "value": "09-07-2026",
            "confidence": 0.9
        },
        "Money Amounts": {
            "value": "50000",
            "confidence": 0.95
        },
        "Organizations": {
            "value": "ABC Pvt Ltd",
            "confidence": 0.8
        },
    }

}


def test_all_profiles_real_metadata():

    print("\nTesting real metadata scoring\n")

    for profile_name, profile in PROFILE_REGISTRY.items():

        print(f"\nTesting {profile_name}")

        metadata = SAMPLE_METADATA.get(profile_name, {})

        score = calculate_metadata_score(
            metadata,
            profile
        )

        print("Score:", score)

        assert 0 <= score <= 1, (
            f"{profile_name} returned invalid score {score}"
        )

        assert score > 0, (
            f"{profile_name} returned zero score with valid metadata"
        )

        print("✅ passed")


def test_missing_fields():

    print("\nTesting missing fields")

    profile = PROFILE_REGISTRY["invoice"]

    metadata = {
        "Invoice Number": {
            "value": None,
            "confidence": 0.0
        }
    }

    score = calculate_metadata_score(
        metadata,
        profile
    )

    print("Score:", score)

    assert score == 0.0

    print("✅ missing field handled")


def test_unknown_field():

    print("\nTesting unknown field")

    profile = PROFILE_REGISTRY["invoice"]

    metadata = {
        "Random Field": {
            "value": "ABC",
            "confidence": 1.0
        }
    }

    score = calculate_metadata_score(
        metadata,
        profile
    )

    print("Score:", score)

    assert score == 0.0

    print("✅ unknown field handled")


if __name__ == "__main__":

    print("Starting scoring tests")

    test_all_profiles_real_metadata()
    test_missing_fields()
    test_unknown_field()

    print("\n🎉 All scoring tests passed!")