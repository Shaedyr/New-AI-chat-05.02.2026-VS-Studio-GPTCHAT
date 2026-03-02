"""
Gjensidige sheet configuration.
"""

from app_modules.insurers.gjensidige.sheets.sammendrag import (
    CELL_MAP as SAMMENDRAG_MAP,
    transform_data as transform_sammendrag,
)
from app_modules.insurers.gjensidige.sheets.fordon import (
    CELL_MAP as FORDON_MAP,
    transform_data as transform_fordon,
)
from app_modules.insurers.gjensidige.sheets.yrkesskade import (
    CELL_MAP as YRKESSKADE_MAP,
    transform_data as transform_yrkesskade,
)
from app_modules.insurers.gjensidige.sheets.alminnelig_ansvar import (
    CELL_MAP as ALMINNELIG_ANSVAR_MAP,
    transform_data as transform_alminnelig_ansvar,
)
from app_modules.insurers.gjensidige.sheets.prosjekt_entreprenor import (
    CELL_MAP as PROSJEKT_ENTREPRENOR_MAP,
    transform_data as transform_prosjekt_entreprenor,
)
from app_modules.insurers.gjensidige.sheets.helse import (
    CELL_MAP as HELSE_MAP,
    transform_data as transform_helse,
)

SHEET_MAPPINGS = {
    "Sammendrag": SAMMENDRAG_MAP,
    "Fordon": FORDON_MAP,
    "Yrkesskade": YRKESSKADE_MAP,
    "Alminnelig ansvar": ALMINNELIG_ANSVAR_MAP,
    "Prosjekt,entreprenør": PROSJEKT_ENTREPRENOR_MAP,
    "Helse": HELSE_MAP,
}

SHEET_TRANSFORMS = {
    "Sammendrag": transform_sammendrag,
    "Fordon": transform_fordon,
    "Yrkesskade": transform_yrkesskade,
    "Alminnelig ansvar": transform_alminnelig_ansvar,
    "Prosjekt,entreprenør": transform_prosjekt_entreprenor,
    "Helse": transform_helse,
}


def transform_for_sheet(sheet_name: str, data: dict) -> dict:
    transform_func = SHEET_TRANSFORMS.get(sheet_name)
    if transform_func:
        return transform_func(data)
    return data

