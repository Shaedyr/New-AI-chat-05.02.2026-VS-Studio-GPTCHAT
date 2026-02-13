# app_modules/Sheets/Fordon/extractors/if_skadeforsikring.py
"""
IF SKADEFORSIKRING FORMAT EXTRACTOR

PDF has each vehicle 3x. Only the detail section has:
  Registreringsnummer: PR59518
  Årsmodell: 2020
  Kjørelengde: 16 000 km

Strategy: find "Registreringsnummer: REG" anchors, then extract
fields from the text that follows. This avoids overview/trafikkavgift noise.
"""

import re


def extract_if_vehicles(pdf_text: str) -> list:
    """Extract vehicles from If Skadeforsikring PDF."""
    import streamlit as st

    vehicles = []
    seen = set()

    st.write("    🔍 **DEBUG: If pattern matching...**")

    # ANCHOR on "Registreringsnummer: PR59518" — only exists in detail section
    anchor_re = r'Registreringsnummer:\s*([A-Z]{2}\d{5})'
    anchors = list(re.finditer(anchor_re, pdf_text))
    st.write(f"    - Registreringsnummer anchors found: {len(anchors)}")

    for a in anchors:
        reg = a.group(1)
        if reg in seen:
            continue
        seen.add(reg)

        # Section: 200 chars BEFORE anchor (has "REG, Varebil, MAKE") + 600 after (has fields)
        start   = max(0, a.start() - 200)
        section = pdf_text[start : a.end() + 600]

        # Extract make/model from "REG, Varebil, MAKE" line in section
        make_m = re.search(
            rf'{reg}\s*,\s*(Varebil|Personbil|Lastebil|Moped|Traktor|Båt|Tilhenger)\s*,\s*([A-Za-zÆØÅæøå\s\-\.]+?)(?:\s+Pris|\s+\d|\s*\n)',
            section
        )
        if not make_m:
            continue

        vtype = make_m.group(1).strip().lower()
        make  = make_m.group(2).strip()

        # Fields - search AFTER the anchor only
        after = pdf_text[a.end() : a.end() + 600]

        year       = _extract_year(after)
        mileage    = _extract_mileage(after)
        deductible = _extract_deductible(after)
        leasing    = _extract_leasing(after)

        type_map = {
            "varebil": "bil", "personbil": "bil", "lastebil": "bil",
            "tilhenger": "trailer", "moped": "moped",
            "traktor": "traktor", "båt": "boat",
        }

        vehicles.append({
            "registration":    reg,
            "vehicle_type":    type_map.get(vtype, "bil"),
            "make_model_year": f"{make} {year}",
            "coverage":        "kasko",
            "leasing":         leasing,
            "annual_mileage":  mileage,
            "bonus":           "",
            "deductible":      deductible,
        })
        st.write(f"      ✓ {reg} - {make} {year} | {mileage} km | egenandel: {deductible} | {leasing}")

    st.write(f"    - **Total: {len(vehicles)} vehicles**")
    return vehicles


# =============================================================
# FIELD EXTRACTORS - search in text AFTER the anchor
# =============================================================
def _extract_year(text: str) -> str:
    """Årsmodell: 2020"""
    m = re.search(r'Årsmodell:\s*(\d{4})', text)
    return m.group(1) if m else ""


def _extract_mileage(text: str) -> str:
    """Kjørelengde: 16 000 km"""
    m = re.search(r'Kjørelengde:\s*([\d\s]+?)\s*km', text)
    return m.group(1).strip() if m else ""


def _extract_deductible(text: str) -> str:
    """Egenandel - Skader på eget kjøretøy: 12 000 kr"""
    m = re.search(r'Egenandel\s*-\s*Skader på eget kjøretøy:\s*([\d\s]+?)\s*kr', text)
    return m.group(1).strip() if m else ""


def _extract_leasing(text: str) -> str:
    """Tredjemannsinteresse/leasing 437"""
    known = ["Sparebank 1", "Nordea Finans", "Santander", "DNB Finans",
             "BRAGE FINANS", "Handelsbanken", "BN Bank"]
    for company in known:
        if company in text:
            return company
    if re.search(r'Tredjemannsinteresse/leasing', text, re.I):
        return "Leasing"
    return ""
