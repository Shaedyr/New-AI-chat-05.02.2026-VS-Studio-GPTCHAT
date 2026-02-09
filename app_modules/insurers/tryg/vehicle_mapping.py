from app_modules.insurers.shared import vehicle_mapping as base_mapping


def transform_data(extracted: dict) -> dict:
    """Tryg-specific vehicle mapping wrapper."""
    data = dict(extracted or {})
    data["vehicle_provider"] = "tryg"
    return base_mapping.transform_data(data)


__all__ = ["transform_data"]
