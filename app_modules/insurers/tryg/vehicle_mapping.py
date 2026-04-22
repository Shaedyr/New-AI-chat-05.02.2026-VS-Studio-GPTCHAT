# app_modules/insurers/tryg/vehicle_mapping.py
"""
FORDON mapping (tryg).
Hard-isolated: this module only runs tryg extractor logic.
"""

import re
import streamlit as st
from app_modules.Sheets.Fordon.extractors.tryg import extract_tryg_vehicles


VEHICLE_ROWS = {
    "car": {"start": 3, "end": 5, "name": "Cars"},
    "trailer": {"start": 9, "end": 11, "name": "Trailers"},
    "moped": {"start": 15, "end": 17, "name": "Mopeds"},
    "tractor": {"start": 21, "end": 23, "name": "Tractors"},
    "boat": {"start": 27, "end": 29, "name": "Boats"},
    "other": {"start": 33, "end": 35, "name": "?vrig (Other)"},
}


VEHICLE_COLUMNS = {
    "registration": "B",
    "make_model_year": "C",
    "sum_insured": "D",
    "coverage": "E",
    "leasing": "F",
    "annual_mileage": "G",
    "bonus": "H",
    "deductible": "I",
}

PREMIUM_FONT_COLOR = "0129F6"

NUMERIC_CELL_STYLE = {
    "number_format": "0",
    "align_horizontal": "right",
    "font_bold": False,
}


def _to_excel_number(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return value

    raw = value.strip().replace(" ", " ")
    if not raw:
        return ""

    if "/" in raw or "%" in raw:
        return value
    if re.search(r"[^0-9\s.,]", raw):
        return value
    if not re.fullmatch(r"[0-9][0-9\s.,]*", raw):
        return value

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return value

    return int(digits)


def _categorize_vehicles(vehicles: list) -> dict:
    categorized = {
        "car": [],
        "trailer": [],
        "moped": [],
        "tractor": [],
        "boat": [],
        "other": [],
    }

    for vehicle in vehicles:
        vtype = (vehicle.get("vehicle_type") or "").lower()
        reg = (vehicle.get("registration") or "").lower()

        if vtype == "other":
            category = "other"
        elif vtype == "trailer":
            category = "trailer"
        elif vtype == "tractor":
            category = "tractor"
        elif vtype == "boat":
            category = "boat"
        elif vtype == "car":
            category = "car"
        elif "tilhenger" in vtype or "henger" in vtype:
            category = "trailer"
        elif "moped" in vtype:
            category = "moped"
        elif "traktor" in vtype:
            category = "tractor"
        elif "b?t" in vtype:
            category = "boat"
        elif "bil" in vtype or "varebil" in vtype or "personbil" in vtype:
            category = "car"
        elif "uregistrert" in reg:
            category = "tractor"
        else:
            category = "other"

        categorized[category].append(vehicle)

    return categorized


def transform_data(extracted: dict) -> dict:
    out = {}
    cell_styles = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""

    if not pdf_text:
        return out

    st.write("?? FORDON: tryg isolated mapping")

    try:
        vehicles = extract_tryg_vehicles(pdf_text) or []
    except Exception as exc:
        st.error(f"tryg extractor failed: {exc}")
        return out

    if not vehicles:
        st.warning("No vehicles extracted")
        return out

    categorized = _categorize_vehicles(vehicles)
    category_order = ["car", "trailer", "moped", "tractor", "boat", "other"]
    fordon_expansions = {}
    cumulative_row_shift = 0

    for category in category_order:
        vehicles_in_category = categorized.get(category, [])

        config = VEHICLE_ROWS[category]
        start, end = config["start"], config["end"]
        capacity = max(0, end - start + 1)
        extra_rows = max(0, len(vehicles_in_category) - capacity)
        fordon_expansions[category] = extra_rows

        if extra_rows > 0:
            st.warning(f"Expanding {config['name']} section by {extra_rows} row(s)")

        shifted_start = start + cumulative_row_shift

        for idx, vehicle in enumerate(vehicles_in_category):
            row = shifted_start + idx

            for field, column in VEHICLE_COLUMNS.items():
                cell_ref = f"{column}{row}"

                if field == "sum_insured":
                    sum_insured = vehicle.get("sum_insured", "")
                    premium = vehicle.get("premium", "")
                    if sum_insured:
                        out[cell_ref] = _to_excel_number(sum_insured)
                        if out[cell_ref] != "":
                            cell_styles[cell_ref] = dict(NUMERIC_CELL_STYLE)
                    elif premium:
                        out[cell_ref] = _to_excel_number(premium)
                        style = dict(NUMERIC_CELL_STYLE)
                        style["font_color"] = PREMIUM_FONT_COLOR
                        cell_styles[cell_ref] = style
                    else:
                        out[cell_ref] = ""
                    continue

                value = vehicle.get(field, "")
                if field in {"annual_mileage", "deductible"}:
                    value = _to_excel_number(value)
                    if value != "":
                        cell_styles[cell_ref] = dict(NUMERIC_CELL_STYLE)
                out[cell_ref] = value

        cumulative_row_shift += extra_rows

    if any(v > 0 for v in fordon_expansions.values()):
        out["_fordon_expansions"] = fordon_expansions

    if cell_styles:
        out["_cell_styles"] = cell_styles

    return out


CELL_MAP = {}
