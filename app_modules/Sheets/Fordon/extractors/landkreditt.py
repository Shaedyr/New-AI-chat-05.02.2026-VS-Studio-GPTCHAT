# app_modules/Sheets/Fordon/extractors/landkreditt.py
"""
Landkreditt extractor for Fordon sheet.

Parses overview rows such as:
- Firmabil: RL34020 12 183
- Lastebil: KU11789 33 331
- Tilhenger: LP5655 5 441
- Lastebilhenger: JN2692 5 950
- Arbeidsmaskin: New Holland, TL90A, KC2068 3 258
- Arbeidsmaskin: Cat, AP 300, UREG 32 649
"""

from __future__ import annotations

import re
import streamlit as st


REG_RE = r"[A-Z]{2}\d{4,5}"
PREMIUM_RE = r"([0-9]{1,3}(?:\s[0-9]{3})*)"
DETAIL_SECTION_CHARS = 2800

SIMPLE_RE = re.compile(
    rf"(Firmabil|Lastebil|Tilhenger|Lastebilhenger)\s*:\s*({REG_RE})\s+{PREMIUM_RE}",
    flags=re.IGNORECASE,
)

MACHINE_RE = re.compile(
    rf"Arbeidsmaskin\s*:\s*(.+?),\s*({REG_RE}|UREG)\s+{PREMIUM_RE}",
    flags=re.IGNORECASE,
)
DETAIL_REG_RE = re.compile(rf"Registreringsnummer\s*:\s*({REG_RE}|UREG)", flags=re.IGNORECASE)


def _normalize_amount(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _extract_detail_model_and_sum(before_text: str) -> tuple[str, str]:
    """
    Read the line above "Registreringsnummer" and try to split:
    - model text
    - optional sum insured at the end
    """
    if not before_text:
        return "", ""

    cleaned = before_text.replace("NEW_LINE", "\n")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return "", ""

    ignore_tokens = (
        "forsikringssum",
        "egenandel",
        "vilkårspunkt",
        "forsikring pris",
        "forsikringsbevis",
        "hovedforfall",
        "utstedt",
        "adresse:",
        "landkreditt.no",
        "retur:",
    )

    candidate = ""
    for line in reversed(lines):
        low = line.lower()
        if any(token in low for token in ignore_tokens):
            continue
        candidate = line
        break

    if not candidate:
        return "", ""

    # Example: "VOLVO FH 540 6x2x4 1 500 000"
    m = re.search(r"^(.*?)(?:\s+([0-9]{1,3}(?:\s[0-9]{3})+))\s*$", candidate)
    if m:
        model = _normalize_text(m.group(1).strip(" -*"))
        sum_insured = _normalize_amount(m.group(2))
        return model, sum_insured

    return _normalize_text(candidate.strip(" -*")), ""


def _extract_deductible(section: str) -> str:
    """Extract deductible from coverage rows inside one registration section."""
    if not section:
        return ""

    patterns = [
        # Cars/trucks/machines:
        r"(?:Kollisjon[^\n\r]{0,90}?)([0-9]{1,3}(?:\s[0-9]{3})+)",
        # Trailers:
        r"(?:\b4\s*Kasko\s+)([0-9]{1,3}(?:\s[0-9]{3})+)",
        # Generic fallback:
        r"(?:Kasko[^\n\r]{0,90}?)([0-9]{1,3}(?:\s[0-9]{3})+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, section, flags=re.IGNORECASE)
        if m:
            return _normalize_amount(m.group(1))
    return ""


def _extract_details_by_registration(pdf_text: str) -> dict:
    """
    Build best per-registration detail map from detailed sections.
    We only map values explicitly present in each registration section.
    """
    details: dict[str, dict] = {}
    scores: dict[str, int] = {}

    if not pdf_text:
        return details

    for match in DETAIL_REG_RE.finditer(pdf_text):
        reg = (match.group(1) or "").upper()
        # UREG can appear multiple times and is not unique; do not force-mix those rows.
        if not reg or reg == "UREG":
            continue

        start = match.start()
        next_match = DETAIL_REG_RE.search(pdf_text, match.end())
        end = next_match.start() if next_match else min(len(pdf_text), start + DETAIL_SECTION_CHARS)
        end = min(end, start + DETAIL_SECTION_CHARS)

        section = pdf_text[start:end]
        before = pdf_text[max(0, start - 600):start]
        model, sum_insured = _extract_detail_model_and_sum(before)

        bonus_match = re.search(r"Bonus\s*:\s*([^\n\r]+)", section, flags=re.IGNORECASE)
        mileage_match = re.search(
            r"Årlig\s+kjørelengde\s*:\s*(?:inntil\s*)?([0-9][0-9\s]{2,})",
            section,
            flags=re.IGNORECASE,
        )
        owner_match = re.search(r"Eier\s*:\s*([^\n\r]+)", section, flags=re.IGNORECASE)

        bonus = _normalize_text((bonus_match.group(1) if bonus_match else "").replace("NEW_LINE", ""))
        annual_mileage = _normalize_amount(mileage_match.group(1)) if mileage_match else ""
        owner = _normalize_text((owner_match.group(1) if owner_match else "").replace("NEW_LINE", ""))
        coverage = "Kasko" if re.search(r"\bKasko\b", section, flags=re.IGNORECASE) else ""
        deductible = _extract_deductible(section)

        score = 0
        context = f"{before}\n{section}".lower()
        if "forsikringssum" in context and "egenandel" in context:
            score += 3
        if "dekningsomfang" in section.lower():
            score += 2
        if model:
            score += 1
        if sum_insured:
            score += 2
        if bonus:
            score += 1
        if annual_mileage:
            score += 1
        if owner:
            score += 1
        if deductible:
            score += 1
        if coverage:
            score += 1

        candidate = {
            "make_model_year": model,
            "sum_insured": sum_insured,
            "coverage": coverage,
            "leasing": owner,
            "annual_mileage": annual_mileage,
            "bonus": bonus,
            "deductible": deductible,
        }

        if reg not in details or score > scores.get(reg, -1):
            details[reg] = candidate
            scores[reg] = score

    return details


def extract_landkreditt_vehicles(pdf_text: str) -> list:
    """Extract vehicles from Landkreditt PDF text."""
    if not pdf_text:
        return []

    normalized = pdf_text.lower()
    if "landkreditt" not in normalized:
        return []
    if (
        "firmabil:" not in normalized
        and "arbeidsmaskin:" not in normalized
        and "lastebil:" not in normalized
        and "lastebilhenger:" not in normalized
    ):
        return []

    st.write("    DEBUG: Landkreditt pattern matching...")

    vehicles: list[dict] = []
    seen: set[str] = set()
    detail_map = _extract_details_by_registration(pdf_text)

    # Parse machine rows first (contains model in same row).
    for machine in MACHINE_RE.finditer(pdf_text):
        desc = _normalize_text(machine.group(1))
        reg_raw = machine.group(2).upper()
        premium = _normalize_amount(machine.group(3))

        reg = "Uregistrert" if reg_raw == "UREG" else reg_raw
        detail = detail_map.get(reg_raw, {})
        key = f"{reg}|{desc}".lower()
        if key in seen:
            continue
        seen.add(key)

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": "tractor",
                "type": "arbeidsmaskin",
                "make_model_year": detail.get("make_model_year") or desc,
                "coverage": detail.get("coverage", ""),
                "leasing": detail.get("leasing", ""),
                "annual_mileage": detail.get("annual_mileage", ""),
                "bonus": detail.get("bonus", ""),
                "deductible": detail.get("deductible", ""),
                "sum_insured": detail.get("sum_insured", ""),
                "premium": premium,
                "source": "overview",
            }
        )

    for simple in SIMPLE_RE.finditer(pdf_text):
        label = simple.group(1).lower()
        reg = simple.group(2).upper()
        premium = _normalize_amount(simple.group(3))

        if label in {"tilhenger", "lastebilhenger"}:
            vtype = "trailer"
        else:
            vtype = "car"

        detail = detail_map.get(reg, {})
        key = reg
        if key in seen:
            continue
        seen.add(key)

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": vtype,
                "type": label,
                "make_model_year": detail.get("make_model_year", ""),
                "coverage": detail.get("coverage", ""),
                "leasing": detail.get("leasing", ""),
                "annual_mileage": detail.get("annual_mileage", ""),
                "bonus": detail.get("bonus", ""),
                "deductible": detail.get("deductible", ""),
                "sum_insured": detail.get("sum_insured", ""),
                "premium": premium,
                "source": "overview",
            }
        )

    st.write(f"    - Landkreditt total: {len(vehicles)} vehicles")
    return vehicles
