# app_modules/insurers/shared/sheet_config.py
"""
Centralized configuration for all Excel sheets.
This file imports and aggregates all sheet mappings.
"""

# Import Sammendrag mapping
from app_modules.Sheets.Sammendrag.mapping import (
    CELL_MAP as SAMMENDRAG_MAP,
    transform_data as transform_sammendrag
)

# Import Fordon mapping (shared)
from app_modules.insurers.shared.vehicle_mapping import (
    CELL_MAP as FORDON_MAP,
    transform_data as transform_fordon
)

# Import Yrkesskade mapping (shared dispatcher)
from app_modules.insurers.shared.workers_comp_mapping import (
    CELL_MAP as YRKESSKADE_MAP,
    transform_data as transform_yrkesskade,
)

# Import Alminnelig ansvar mapping (shared dispatcher)
from app_modules.insurers.shared.general_liability_mapping import (
    CELL_MAP as ALMINNELIG_ANSVAR_MAP,
    transform_data as transform_alminnelig_ansvar,
)


# Master mapping: Excel sheet name -> field mappings
SHEET_MAPPINGS = {
    "Sammendrag": SAMMENDRAG_MAP,
    "Fordon": FORDON_MAP,  # Note: Fordon uses dynamic mapping, CELL_MAP is empty
    "Yrkesskade": YRKESSKADE_MAP,  # Dynamic mapping per insurer
    "Alminnelig ansvar": ALMINNELIG_ANSVAR_MAP,  # Dynamic mapping per insurer
    # Add other sheets here when you create their mapping files
}


# Master transform functions: sheet name -> transform function
SHEET_TRANSFORMS = {
    "Sammendrag": transform_sammendrag,
    "Fordon": transform_fordon,
    "Yrkesskade": transform_yrkesskade,
    "Alminnelig ansvar": transform_alminnelig_ansvar,
    # Add other sheets here when you create their mapping files
}


def get_sheet_mapping(sheet_name: str) -> dict:
    """
    Get the cell mapping for a specific sheet.

    Args:
        sheet_name: Name of the Excel sheet

    Returns:
        Dictionary mapping field names to cell references
    """
    return SHEET_MAPPINGS.get(sheet_name, {})


def get_transform_function(sheet_name: str):
    """
    Get the transform function for a specific sheet.

    Args:
        sheet_name: Name of the Excel sheet

    Returns:
        Transform function or None if not found
    """
    return SHEET_TRANSFORMS.get(sheet_name)


def transform_for_sheet(sheet_name: str, data: dict) -> dict:
    """
    Transform data for a specific sheet using its transform function.

    Args:
        sheet_name: Name of the Excel sheet
        data: Raw data dictionary

    Returns:
        Transformed data dictionary
    """
    transform_func = get_transform_function(sheet_name)
    if transform_func:
        return transform_func(data)
    return data
