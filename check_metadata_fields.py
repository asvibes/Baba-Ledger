from backend.profiles import PROFILE_REGISTRY

for name, profile in PROFILE_REGISTRY.items():
    print("\n", name)

    for key, value in profile["metadata_fields"].items():
        print(key, "->", value, type(value))
        