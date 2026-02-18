"""
Prosjekt,entreprenør mapping (shared).

Current scope:
- Malco / IF only
- Fill only A3 + B3 when explicit Allrisk amount is present in PDF text
- Leave everything else blank
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _is_if_document(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in ("if skadeforsikring", "if.no", "if forsikrer"))


def _extract_allrisk_amount(pdf_text: str) -> str:
    patterns = [
        r"Prosjekt[\-/ ]*entrepren(?:ør|or)\s*-\s*Allrisk\s*([0-9][0-9\s.,]{2,})",
        r"Prosjekt[\-/ ]*entrepren(?:ør|or)forsikring.*?Allrisk\s*([0-9][0-9\s.,]{2,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def transform_data(extracted: dict) -> dict:
    """
    Dynamic mapping for the sheet "Prosjekt,entreprenør".
    """
    data = dict(extracted or {})
    pdf_text = data.get("pdf_text", "") or ""
    if not pdf_text:
        return {}

    provider = (data.get("vehicle_provider") or "").strip().lower()
    if provider not in ("", "auto-detect", "if", "if skadeforsikring"):
        return {}

    if not _is_if_document(pdf_text):
        return {}

    amount_raw = _extract_allrisk_amount(pdf_text)
    amount_digits = _digits(amount_raw)
    if not amount_digits:
        return {}

    return {
        "A3": "Allrisk",
        "B3": int(amount_digits),
    }

