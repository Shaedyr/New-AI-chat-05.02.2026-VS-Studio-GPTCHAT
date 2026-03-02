from app_modules.insurers.shared.project_entrepreneur_mapping import (
    CELL_MAP,
    transform_data as base_transform_data,
)


def transform_data(extracted: dict) -> dict:
    data = dict(extracted or {})
    data["vehicle_provider"] = "if"
    return base_transform_data(data)


__all__ = ["CELL_MAP", "transform_data"]

