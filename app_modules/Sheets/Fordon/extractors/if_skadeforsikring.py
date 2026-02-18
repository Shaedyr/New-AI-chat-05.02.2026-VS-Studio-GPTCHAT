# app_modules/Sheets/Fordon/extractors/if_skadeforsikring.py
"""
IF SKADEFORSIKRING FORMAT EXTRACTOR.

Strategy:
- Anchor each vehicle block on "Registreringsnummer: XX12345"
- Parse details inside that bounded block (up to next anchor)
- Return fields used by Fordon mapping, including premium/sum_insured when present
"""

from __future__ import annotations

import re
import streamlit as st


VEHICLE_TYPE_PATTERN = r"(Varebil|Personbil|Lastebil|Moped|Traktor|BÃ¥t|Båt|Tilhenger)"
ANCHOR_RE = re.compile(r"Registreringsnummer:\s*([A-Z]{2}\d{5})")
DEDUCTIBLE_RE = re.compile(
    r"Egenandel\s*-\s*Skader p\S* eget kj\S*ret\S*y:\s*([\d\s]+?)\s*kr",
    flags=re.IGNORECASE,
)
SUM_INSURED_RE = re.compile(
    r"Forsikringssum[^0-9]{0,40}([\d\s]{4,})\s*kr",
    flags=re.IGNORECASE,
)
LEASING_MARK_RE = re.compile(r"Tredjemannsinteresse/leasing", re.IGNORECASE)
KNOWN_LEASING_COMPANIES = (
    "Sparebank 1",
    "Nordea Finans",
    "Santander",
    "DNB Finans",
    "BRAGE FINANS",
    "Handelsbanken",
    "BN Bank",
)


def extract_if_vehicles(pdf_text: str) -> list:
    """Extract vehicles from IF PDFs."""

    vehicles = []
    seen = set()

    st.write("    ðŸ” **DEBUG: If pattern matching...**")

    anchors = list(ANCHOR_RE.finditer(pdf_text))
    st.write(f"    - Registreringsnummer anchors found: {len(anchors)}")

    for idx, anchor in enumerate(anchors):
        reg = anchor.group(1)
        if reg in seen:
            continue
        seen.add(reg)

        next_anchor_start = anchors[idx + 1].start() if idx + 1 < len(anchors) else min(len(pdf_text), anchor.end() + 2200)
        block_start = max(0, anchor.start() - 350)
        section = pdf_text[block_start:next_anchor_start]
        after_anchor = pdf_text[anchor.end():next_anchor_start]

        make_m = re.search(
            rf"{reg}\s*,\s*{VEHICLE_TYPE_PATTERN}\s*,\s*([A-Za-zÃ†Ã˜Ã…Ã¦Ã¸Ã¥\-\.\s]+?)(?:\s+Pris|\s+\d|\s*\n)",
            section,
        )
        if not make_m:
            continue

        raw_type = make_m.group(1).strip().lower()
        make = make_m.group(2).strip()

        year = _extract_year(after_anchor)
        mileage = _extract_mileage(after_anchor)
        deductible = _extract_deductible(after_anchor)
        leasing = _extract_leasing(after_anchor)
        if not leasing:
            # Some IF layouts place leasing line immediately before the
            # "Registreringsnummer" line for the same vehicle.
            pre_anchor = pdf_text[max(0, anchor.start() - 240):anchor.start()]
            leasing = _extract_leasing(pre_anchor)
        premium = _extract_premium(section, reg)
        sum_insured = _extract_sum_insured(after_anchor)

        type_map = {
            "varebil": "bil",
            "personbil": "bil",
            "lastebil": "bil",
            "tilhenger": "trailer",
            "moped": "moped",
            "traktor": "traktor",
            "bÃ¥t": "boat",
            "båt": "boat",
        }

        model_with_year = f"{make} {year}".strip()
        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": type_map.get(raw_type, "bil"),
                "make_model_year": model_with_year,
                "coverage": "kasko",
                "leasing": leasing,
                "annual_mileage": mileage,
                "bonus": "",
                "deductible": deductible,
                "premium": premium,
                "sum_insured": sum_insured,
            }
        )

        st.write(
            f"      âœ“ {reg} - {model_with_year} | {mileage} km | "
            f"egenandel: {deductible} | premium: {premium} | {leasing}"
        )

    st.write(f"    - **Total: {len(vehicles)} vehicles**")
    return vehicles


def _extract_year(text: str) -> str:
    m = re.search(r"(?:Årsmodell|Ã…rsmodell):\s*(\d{4})", text)
    return m.group(1) if m else ""


def _extract_mileage(text: str) -> str:
    m = re.search(r"(?:Kjørelengde|KjÃ¸relengde):\s*([\d\s]+?)\s*km", text)
    return m.group(1).strip() if m else ""


def _extract_deductible(text: str) -> str:
    m = DEDUCTIBLE_RE.search(text)
    return m.group(1).strip() if m else ""


def _extract_premium(text: str, reg: str) -> str:
    m = re.search(
        rf"{reg}\s*,\s*{VEHICLE_TYPE_PATTERN}\s*,\s*.+?\s+Pris per \S*r\s+NOK\s*([\d\s]+)",
        text,
        flags=re.IGNORECASE,
    )
    return m.group(2).strip() if m else ""


def _extract_sum_insured(text: str) -> str:
    m = SUM_INSURED_RE.search(text)
    return m.group(1).strip() if m else ""


def _extract_leasing(text: str) -> str:
    for company in KNOWN_LEASING_COMPANIES:
        if company in text:
            return company
    if LEASING_MARK_RE.search(text):
        return "Leasing (ukjent selskap/tredjepartsleasing)"
    return ""
