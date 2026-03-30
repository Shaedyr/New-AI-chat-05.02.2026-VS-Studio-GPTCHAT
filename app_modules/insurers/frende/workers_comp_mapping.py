"""
Frende-specific mapping for sheet: Yrkesskade.

Current scope:
- Fill row 3 total premium when explicitly found.
- Fill row 3 årsverk/personer if explicitly found.
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


def _extract_total_premium(pdf_text: str) -> str:
    patterns = [
        r"Yrkesskadeforsikring\s+Yrkesskade\s+([0-9][0-9\s.,]{2,})\s*kr",
        r"Yrkesskade\s+([0-9][0-9\s.,]{2,})\s*kr",
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _extract_row3_counts(pdf_text: str) -> tuple[str, str]:
    # Generic fallback if counts are present in the document.
    # B = årsverk, C = personer
    match = re.search(
        r"Antall\s+ansatte\s*[: ]\s*([0-9]{1,4}).{0,40}?[åa]rsverk\s*[: ]\s*([0-9]{1,4})",
        pdf_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return "", ""
    personer = _digits(match.group(1))
    arsverk = _digits(match.group(2))
    return arsverk, personer


def transform_data(extracted: dict) -> dict:
    out: dict[str, object] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    if "frende" not in pdf_text.lower():
        return out

    premium = _digits(_extract_total_premium(pdf_text))
    arsverk, personer = _extract_row3_counts(pdf_text)

    if premium:
        out["D3"] = int(premium)
    if arsverk:
        out["B3"] = int(arsverk)
    if personer:
        out["C3"] = int(personer)

    return out
