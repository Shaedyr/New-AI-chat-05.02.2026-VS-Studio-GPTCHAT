# app_modules/insurers/ly/vehicle_mapping.py
"""
FORDON mapping (ly).
Hard-isolated: this module only runs ly extractor logic.
"""

import re
import streamlit as st
from app_modules.Sheets.Fordon.extractors.ly import extract_ly_vehicles


VEHICLE_ROWS = {
    "car": {"start": 3, "end": 27, "name": "Cars"},
    "trailer": {"start": 31, "end": 45, "name": "Trailers"},
    "moped": {"start": 49, "end": 63, "name": "Mopeds"},
    "tractor": {"start": 67, "end": 81, "name": "Tractors"},
    "boat": {"start": 85, "end": 99, "name": "Boats"},
    "other": {"start": 103, "end": 117, "name": "?vrig (Other)"},
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

    st.write("?? FORDON: ly isolated mapping")

    try:
        vehicles = extract_ly_vehicles(pdf_text) or []
    except Exception as exc:
        st.error(f"ly extractor failed: {exc}")
        return out

    if not vehicles:
        st.warning("No vehicles extracted")
        return out

    categorized = _categorize_vehicles(vehicles)

    for category, vehicles_in_category in categorized.items():
        if not vehicles_in_category:
            continue

        config = VEHICLE_ROWS[category]
        start, end = config["start"], config["end"]

        for idx, vehicle in enumerate(vehicles_in_category):
            row = start + idx
            if row > end:
                st.warning(f"Too many {config['name']} for template range")
                break

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

    if cell_styles:
        out["_cell_styles"] = cell_styles

    return out


CELL_MAP = {}
