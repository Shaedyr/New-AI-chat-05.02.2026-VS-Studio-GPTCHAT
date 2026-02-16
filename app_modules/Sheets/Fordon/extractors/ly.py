# app_modules/Sheets/Fordon/extractors/ly.py
"""
Ly Forsikring extractor for Fordon sheet.

Supports two observed Ly formats:
1) Group tables:
   - "Kjoretoy som inngar i gruppen" (cars)
   - "Tilhengere som inngar i gruppen" (trailers)
2) Unregistered machinery blocks:
   - "Registreringsnummer UREG"
"""

from __future__ import annotations

import re


TABLE_ROW_RE = re.compile(
    r"^([A-Z]{2}\s?\d{4,5})\s+(.+?)\s+(19\d{2}|20\d{2})\s+"
    r"\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}\.\d{2}\.\d{4})?\s+"
    r"([0-9][0-9\s\.,]{0,15})\s+([0-9][0-9\s\.,]{0,15})$"
)


def extract_ly_vehicles(pdf_text: str) -> list:
    """Extract vehicles from Ly Forsikring PDF text."""
    import streamlit as st

    if not pdf_text:
        return []

    normalized_all = _normalize_text(pdf_text)
    ly_markers = (
        "ly forsikring",
        "firmabil flate",
        "tilhenger flate",
        "registreringsnummer ureg",
    )
    if not any(marker in normalized_all for marker in ly_markers):
        return []

    st.write("    DEBUG: Ly pattern matching...")

    vehicles: list[dict] = []
    seen_keys: set[str] = set()

    defaults = _extract_group_defaults(pdf_text)
    vehicles.extend(_extract_group_table_vehicles(pdf_text, defaults, seen_keys))
    vehicles.extend(_extract_unregistered_machines(pdf_text, seen_keys))

    st.write(f"    - Ly total: {len(vehicles)} vehicles")
    return vehicles


def _extract_group_defaults(text: str) -> dict:
    car_section = _section_between(
        text,
        r"Gruppenavn\s+Firmabiler",
        r"Kj[øo]ret[øo]y\s+som\s+inng[åa]r\s+i\s+gruppen",
    )
    trailer_section = _section_between(
        text,
        r"Gruppenavn\s+Tilhengere",
        r"Tilhengere\s+som\s+inng[åa]r\s+i\s+gruppen",
    )

    return {
        "car": {
            "coverage": "kasko" if _extract_amount(car_section, r"\bKasko\s+([0-9][0-9\s\.,]*)") else "",
            "deductible": _extract_amount(car_section, r"\bKasko\s+([0-9][0-9\s\.,]*)"),
            "annual_mileage": _extract_amount(car_section, r"Avtalt\s+kj[øo]relengde\s+([0-9][0-9\s\.,]*)"),
            "leasing": _extract_selected_leasing(car_section),
        },
        "trailer": {
            "coverage": "kasko" if _extract_amount(trailer_section, r"\bKasko\s+([0-9][0-9\s\.,]*)") else "",
            "deductible": _extract_amount(trailer_section, r"\bKasko\s+([0-9][0-9\s\.,]*)"),
            "annual_mileage": "",
            "leasing": _extract_selected_leasing(trailer_section),
        },
    }


def _extract_group_table_vehicles(pdf_text: str, defaults: dict, seen_keys: set[str]) -> list:
    vehicles: list[dict] = []
    current_section = ""

    for raw_line in pdf_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        normalized = _normalize_text(line)
        if "kjoretoy som inngar i gruppen" in normalized:
            current_section = "car"
            continue
        if "tilhengere som inngar i gruppen" in normalized:
            current_section = "trailer"
            continue

        if current_section not in ("car", "trailer"):
            continue

        match = TABLE_ROW_RE.match(line)
        if not match:
            continue

        reg = _normalize_registration(match.group(1))
        model = _compact_spaces(match.group(2))
        year = match.group(3)
        premium = _normalize_amount(match.group(4))

        key = reg
        if key in seen_keys:
            continue
        seen_keys.add(key)

        section_defaults = defaults.get(current_section, {})
        vehicle_type = "car" if current_section == "car" else "trailer"

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": vehicle_type,
                "make_model_year": f"{model} {year}".strip(),
                "coverage": section_defaults.get("coverage", "kasko") or "kasko",
                "leasing": section_defaults.get("leasing", ""),
                "annual_mileage": section_defaults.get("annual_mileage", ""),
                "bonus": "",
                "deductible": section_defaults.get("deductible", ""),
                "sum_insured": "",
                "premium": premium,
            }
        )

    return vehicles


def _extract_unregistered_machines(pdf_text: str, seen_keys: set[str]) -> list:
    vehicles: list[dict] = []

    for anchor in re.finditer(r"Registreringsnummer\s+UREG", pdf_text, re.IGNORECASE):
        section = _slice_context(pdf_text, anchor.start(), before=120, after=2200)

        model = _extract_line_value(section, r"Merke\s*/\s*modell\s*([^\n\r]*)")
        year = _extract_line_value(section, r"(?:Å|A)rsmodell\s+(19\d{2}|20\d{2})")
        machine_type = _extract_line_value(section, r"Maskintype\s+([^\n\r]+)")

        if not model and not machine_type:
            continue

        reg = "Uregistrert"
        display_base = _compact_spaces(model) or _compact_spaces(machine_type)
        display_name = f"{display_base} {year}".strip()
        key = f"{reg}_{display_name}".lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)

        type_norm = _normalize_text(machine_type)
        vehicle_type = "tractor" if "traktor" in type_norm else "other"

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": vehicle_type,
                "make_model_year": display_name,
                "coverage": "kasko" if _extract_amount(section, r"\bKasko\s+([0-9][0-9\s\.,]*)") else "",
                "leasing": _extract_selected_leasing(section),
                "annual_mileage": "",
                "bonus": "",
                "deductible": _extract_amount(section, r"\bKasko\s+([0-9][0-9\s\.,]*)"),
                "sum_insured": _extract_amount(section, r"Markedsverdi\s+([0-9][0-9\s\.,]*)"),
                "premium": _extract_amount(section, r"Pris\s+for\s+forsikringsperioden\s+([0-9][0-9\s\.,]*)"),
            }
        )

    return vehicles


def _section_between(text: str, start_pattern: str, end_pattern: str) -> str:
    start = re.search(start_pattern, text, re.IGNORECASE)
    if not start:
        return ""

    end = re.search(end_pattern, text[start.end() :], re.IGNORECASE)
    if not end:
        return text[start.start() : start.start() + 2500]
    return text[start.start() : start.end() + end.start()]


def _extract_selected_leasing(section: str) -> str:
    if not section:
        return ""
    selected = re.search(
        r"Kundevalgte\s+tilleggsdekninger\s+som\s+er\s+valgt(.{0,700})",
        section,
        re.IGNORECASE | re.DOTALL,
    )
    if not selected:
        return ""
    return "Leasingavtale" if re.search(r"M01\s+Leasingavtale", selected.group(1), re.IGNORECASE) else ""


def _extract_amount(text: str, pattern: str) -> str:
    if not text:
        return ""
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    return _normalize_amount(match.group(1))


def _extract_line_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    return _compact_spaces(match.group(1))


def _normalize_registration(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def _compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _normalize_text(value: str) -> str:
    text = (value or "").lower()
    replacements = {
        "ø": "o",
        "å": "a",
        "æ": "ae",
        "ö": "o",
        "ü": "u",
        "\u00c3\u00b8": "o",
        "\u00c3\u00a5": "a",
        "\u00c3\u00a6": "ae",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_amount(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    # Keep "0" unchanged.
    if digits == "0":
        return "0"
    parts = []
    while digits:
        parts.append(digits[-3:])
        digits = digits[:-3]
    return " ".join(reversed(parts))


def _slice_context(text: str, center: int, before: int, after: int) -> str:
    return text[max(0, center - before) : min(len(text), center + after)]

