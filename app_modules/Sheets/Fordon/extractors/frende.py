# app_modules/Sheets/Fordon/extractors/frende.py
"""
Frende extractor for Fordon sheet.

Parses overview rows such as:
- Firmabilforsikring OPEL, VIVARO, RL69728 10720 kr

Conservative mapping:
- only values found in the PDF are mapped
- missing values stay blank
"""

from __future__ import annotations

import re
import streamlit as st


LINE_RE = re.compile(
    r"Firmabilforsikring\s+(.+?)\s*,\s*([A-Z]{2}\d{4,5})\s+([0-9][0-9\s]{1,})\s*kr",
    flags=re.IGNORECASE,
)
REG_BLOCK_RE = re.compile(r"Registreringsnummer\s+([A-Z]{2}\d{4,5})", flags=re.IGNORECASE)


def _normalize_amount(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _normalize_model(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace(" ,", ",").strip(" ,"))


def _extract_vehicle_details(pdf_text: str, reg: str) -> dict:
    """
    Extract per-vehicle details from the registration section.
    Only map values explicitly found for this vehicle.
    """
    details = {
        "coverage": "",
        "bonus": "",
        "deductible": "",
    }

    anchor = re.search(rf"Registreringsnummer\s+{re.escape(reg)}\b", pdf_text, flags=re.IGNORECASE)
    if not anchor:
        return details

    next_anchor = REG_BLOCK_RE.search(pdf_text, anchor.end())
    section_end = next_anchor.start() if next_anchor else min(len(pdf_text), anchor.start() + 2600)
    section = pdf_text[anchor.start():section_end]

    if re.search(r"Kasko\s+Du har valgt bort dekningen", section, flags=re.IGNORECASE):
        details["coverage"] = "Du har valgt bort dekningen"
    elif re.search(r"\bKasko\b", section, flags=re.IGNORECASE):
        details["coverage"] = "Kasko"

    bonus_match = re.search(r"Bonus\s*:?\s*([^\n\r]+)", section, flags=re.IGNORECASE)
    if bonus_match:
        details["bonus"] = bonus_match.group(1).strip()

    deductible_match = re.search(r"Valgt egenandel\s*:\s*([0-9][0-9\s]*)\s*kr", section, flags=re.IGNORECASE)
    if deductible_match:
        details["deductible"] = _normalize_amount(deductible_match.group(1))

    return details


def extract_frende_vehicles(pdf_text: str) -> list:
    """Extract vehicles from Frende PDF text."""
    if not pdf_text:
        return []

    if "firmabilforsikring" not in pdf_text.lower():
        return []

    st.write("    DEBUG: Frende pattern matching...")

    vehicles: list[dict] = []
    seen_regs: set[str] = set()

    for match in LINE_RE.finditer(pdf_text):
        model = _normalize_model(match.group(1))
        reg = match.group(2).upper()
        premium = _normalize_amount(match.group(3))
        details = _extract_vehicle_details(pdf_text, reg)

        if reg in seen_regs:
            continue
        seen_regs.add(reg)

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": "car",
                "type": "firmabil",
                "make_model_year": model,
                "coverage": details["coverage"],
                "leasing": "",
                "annual_mileage": "",
                "bonus": details["bonus"],
                "deductible": details["deductible"],
                "sum_insured": "",
                "premium": premium,
                "source": "overview",
            }
        )

    st.write(f"    - Frende total: {len(vehicles)} vehicles")
    return vehicles
