from backend.profiles import PROFILE_REGISTRY


required_keys = [
    "fields",
    "field_patterns",
    "metadata_fields",
]


for profile_name, profile in PROFILE_REGISTRY.items():
    print(f"\nChecking {profile_name}")

    for key in required_keys:
        if key in profile:
            print(f"✅ {key}")
        else:
            print(f"❌ Missing {key}")

print("\nDone!")