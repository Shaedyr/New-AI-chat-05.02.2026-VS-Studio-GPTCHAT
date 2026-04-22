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
ANCHOR_RE = re.compile(r"Registreringsnummer:\s*([A-Z]{2}\d{4,5})")
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

BILAG_REG_LINE_RE = re.compile(r"^\s*([A-Z]{2}\d{4,5})\s+(\d{4})\s+(.+?)\s*$")
BILAG_COMMA_ROW_RE = re.compile(r"^\s*([A-Z]{2}\d{4,5})\s*,\s*([^,]+?)(?:\s*,\s*|\s+)(.+?)\s*$")
BILAG_PREMIUM_RE = re.compile(r"(\d{1,3}(?:\s\d{3})*)\s*kr\b", re.IGNORECASE)


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
        seen.add(reg)
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

    if _has_bilag_vehicle_lists(pdf_text):
        fallback = _extract_if_bilag_table_vehicles(pdf_text, seen)
        if fallback:
            st.write(f"    - Bilag fallback vehicles: {len(fallback)}")
            vehicles.extend(fallback)
    elif not vehicles:
        # Safety net for IF layouts that omit "Registreringsnummer:" blocks.
        fallback = _extract_if_bilag_table_vehicles(pdf_text, seen)
        if fallback:
            st.write(f"    - Fallback vehicles: {len(fallback)}")
            vehicles.extend(fallback)

    st.write(f"    - **Total: {len(vehicles)} vehicles**")
    return vehicles


def _has_bilag_vehicle_lists(pdf_text: str) -> bool:
    text = (pdf_text or "").lower()
    return (
        ("bilag 1" in text and "kjennetegn" in text)
        or "næringsbiler" in text
        or "neringsbiler" in text
        or "storbiler" in text
    )


def _extract_if_bilag_table_vehicles(pdf_text: str, seen: set[str]) -> list:
    """
    Fallback parser for IF Bilag tables:
    Example rows:
      EB47847 2020 VOLKSWAGEN ID.3 ... 2 939 kr 11 933 kr
      JH8240 2013 IVECO ... 18 674 kr
    """
    vehicles: list[dict] = []
    current_type = "bil"

    for raw_line in (pdf_text or "").splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue

        lower = line.lower()
        if "tilhengere" in lower:
            current_type = "trailer"
        elif "traktorer/atv" in lower or "traktorer" in lower:
            current_type = "traktor"
        elif "arbeidsmaskiner" in lower:
            current_type = "traktor"
        elif "næringsbiler" in lower or "neringsbiler" in lower or "storbiler" in lower:
            current_type = "bil"
        elif "snøscooter" in lower:
            current_type = "traktor"
        elif "båt" in lower or "bat" in lower:
            current_type = "boat"

        comma_row = BILAG_COMMA_ROW_RE.match(line)
        if comma_row:
            reg = comma_row.group(1).strip().upper()
            type_token = comma_row.group(2).strip().lower()
            model_segment = comma_row.group(3).strip()
            if reg in seen:
                continue

            row_type = _type_from_token(type_token) or _infer_type_from_line(current_type, model_segment)

            model_segment = re.split(r"\s+Aktiv fra:\s*\d{2}\.\d{2}\.\d{4}\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
            model_segment = re.split(r"\s+Avsluttet:\s*\d{2}\.\d{2}\.\d{4}\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
            model_segment = re.split(r"\s+\d{1,3}(?:\s\d{3}){1,2}\s*$", model_segment, maxsplit=1)[0]
            model_segment = re.split(r"\s+(?:ja|nei)\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
            model_segment = re.sub(r"\s{2,}", " ", model_segment).strip(" ,")
            if not model_segment:
                model_segment = "Ukjent modell"

            premium_tokens = BILAG_PREMIUM_RE.findall(line)
            premium = _normalize_digits(premium_tokens[-1]) if premium_tokens else ""

            seen.add(reg)
            vehicles.append(
                {
                    "registration": reg,
                    "vehicle_type": row_type,
                    "make_model_year": model_segment,
                    "coverage": "kasko",
                    "leasing": "",
                    "annual_mileage": "",
                    "bonus": "",
                    "deductible": "",
                    "premium": premium,
                    "sum_insured": "",
                }
            )
            continue

        row_match = BILAG_REG_LINE_RE.match(line)
        if not row_match:
            continue

        reg = row_match.group(1).strip().upper()
        year = row_match.group(2).strip()
        model_segment = row_match.group(3).strip()

        if reg in seen:
            continue

        model_segment = re.split(r"\s+\d{2}\.\d{2}\.\d{4}\b", model_segment, maxsplit=1)[0]
        model_segment = re.split(r"\s+Avsluttet:\s*\d{2}\.\d{2}\.\d{4}\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
        model_segment = re.split(r"\s+(?:ja|nei)\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
        model_segment = re.split(r"\s+\d{1,3}(?:\s\d{3})?\s*kr\b", model_segment, maxsplit=1, flags=re.IGNORECASE)[0]
        model_segment = re.sub(r"\s+\d{9}$", "", model_segment)
        model_segment = re.sub(r"\s{2,}", " ", model_segment).strip(" ,")

        if not model_segment:
            model_segment = "Ukjent modell"

        premium_tokens = BILAG_PREMIUM_RE.findall(line)
        premium = _normalize_digits(premium_tokens[-1]) if premium_tokens else ""

        row_type = _infer_type_from_line(current_type, model_segment)
        model_with_year = f"{model_segment} {year}".strip()

        seen.add(reg)
        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": row_type,
                "make_model_year": model_with_year,
                "coverage": "kasko",
                "leasing": "",
                "annual_mileage": "",
                "bonus": "",
                "deductible": "",
                "premium": premium,
                "sum_insured": "",
            }
        )

    return vehicles


def _infer_type_from_line(default_type: str, model_text: str) -> str:
    txt = (model_text or "").lower()
    if "tilhenger" in txt:
        return "trailer"
    if "traktor" in txt or "atv" in txt or "snøscooter" in txt:
        return "traktor"
    if "båt" in txt or "bat" in txt:
        return "boat"
    return default_type or "bil"


def _type_from_token(type_token: str) -> str:
    token = (type_token or "").strip().lower()
    if "tilhenger" in token:
        return "trailer"
    if "traktor" in token or "atv" in token or "snøscooter" in token or "snoscooter" in token:
        return "traktor"
    if "terrengkjøretøy" in token or "terrengkjoretoy" in token:
        return "traktor"
    if "båt" in token or "bat" in token:
        return "boat"
    if "moped" in token:
        return "moped"
    if "lastebil" in token or "varebil" in token or "personbil" in token:
        return "bil"
    return ""


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


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()
