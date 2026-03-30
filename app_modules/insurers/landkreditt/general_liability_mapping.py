"""
Landkreditt-specific mapping for sheet: Alminnelig ansvar.

Rules:
- Map only values that exist in the source PDF.
- Keep missing values blank.
- Prefer `150 G` when both `150 G` and other limits exist.
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}

ROW_START = 3

FIELD_COLUMNS = {
    "virksomhet": "A",
    "annual_turnover_2024": "B",
    "bedriftsansvar": "C",
    "egenandel_ansvar": "D",
    "produktansvar": "E",
    "rettshjelp_sum": "F",
    "tilbud_kommentar": "H",
}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _to_int_or_blank(value: str):
    num = _digits(value)
    return int(num) if num else ""


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _extract_virksomhet(pdf_text: str) -> str:
    # Example:
    # Forsikret virksomhet
    # 933768929
    # Grunnarbeid, 100 %
    match = re.search(
        r"Forsikret\s+virksomhet\s*(?:\r?\n)+\s*(?:[0-9]{9}\s*)?(?:\r?\n)?\s*([^\r\n]+)",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return _normalize_whitespace(match.group(1))
    return ""


def _extract_turnover(pdf_text: str) -> str:
    match = re.search(
        r"Driftsinntekter\s+regnskaps[åa]ret\s+2024\s*:\s*([0-9][0-9\s.,]{3,})",
        pdf_text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _extract_bedriftsansvar(pdf_text: str) -> str:
    match = re.search(
        r"Bedriftsansvar\s+([0-9]{1,3})\s*G",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} G"
    return ""


def _extract_egenandel(pdf_text: str) -> str:
    # Example: "Dekningsomfang: 15 000"
    match = re.search(
        r"Dekningsomfang\s*:\s*([0-9][0-9\s.,]{2,})",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


def _extract_produktansvar(pdf_text: str) -> str:
    match = re.search(
        r"Produktansvar\s+([0-9]{1,3})\s*G",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} G"
    return ""


def _extract_rettshjelp(pdf_text: str) -> str:
    # Guard against vehicle sections where "Rettshjelp 100 000 ... 12.2".
    # Only search inside the liability section, if present.
    section_match = re.search(
        r"Forsikringsbevis\s+del\s+1\s*-\s*Bedrifts-\s*og\s*produktansvar(.{0,3000})",
        pdf_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return ""
    section = section_match.group(1)

    match = re.search(
        r"Rettshjelp[^\r\n]{0,30}([0-9][0-9\s.,]{3,})",
        section,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


def transform_data(extracted: dict) -> dict:
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return {}

    # Keep this mapper isolated to Landkreditt documents only.
    if "landkreditt" not in pdf_text.lower():
        return {}

    values = {
        "virksomhet": _extract_virksomhet(pdf_text),
        "annual_turnover_2024": _extract_turnover(pdf_text),
        "bedriftsansvar": _extract_bedriftsansvar(pdf_text),
        "egenandel_ansvar": _extract_egenandel(pdf_text),
        "produktansvar": _extract_produktansvar(pdf_text),
        "rettshjelp_sum": _extract_rettshjelp(pdf_text),
        "tilbud_kommentar": "",
    }

    if not any(values.values()):
        return {}

    out: dict[str, object] = {}
    for field, col in FIELD_COLUMNS.items():
        value = values.get(field, "")
        if field in {"annual_turnover_2024", "egenandel_ansvar", "rettshjelp_sum"}:
            value = _to_int_or_blank(value)
        else:
            value = _normalize_whitespace(str(value)) if value else ""
        out[f"{col}{ROW_START}"] = value

    out["_cell_styles"] = {
        "A3": {"align_horizontal": "left", "align_vertical": "top", "wrap_text": True},
        "H3": {"align_horizontal": "left", "align_vertical": "top", "wrap_text": True},
    }

    return out
