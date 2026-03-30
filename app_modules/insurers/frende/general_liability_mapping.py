"""
Frende-specific mapping for sheet: Alminnelig ansvar.

Rules:
- Map only values that can be found in the PDF text.
- Keep missing values blank.
- Prefer `150 G` for bedriftsansvar when both G and MNOK are present.
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
    match = re.search(r"N[æa]ringsvirksomhet\s+([^\r\n]+)", pdf_text, re.IGNORECASE)
    if match:
        return _normalize_whitespace(match.group(1))

    match = re.search(
        r"Ansvar\s+omfatter\s+ogs[aå]\s+f[øo]lgende\s+n[æa]ringsvirksomhet\s+Omsetning\s+([^\r\n]+?)\s+[0-9]",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return _normalize_whitespace(match.group(1))

    return ""


def _extract_turnover(pdf_text: str) -> str:
    patterns = [
        r"Driftsinntekter\s+regnskaps[åa]ret\s+2024\s*:\s*([0-9][0-9\s.,]{3,})",
        r"Ansvar\s+omfatter\s+ogs[aå]\s+f[øo]lgende\s+n[æa]ringsvirksomhet\s+Omsetning\s+[^\r\n]*?\s+([0-9][0-9\s.,]{3,})",
        r"Omsetning[^\r\n]{0,40}?([0-9][0-9\s.,]{3,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
    return ""


def _extract_bedriftsansvar(pdf_text: str) -> str:
    # Priority rule: 150 G first (if present)
    g_match = re.search(
        r"Ansvar\s+iht\.?\s+norsk\s+standard\s*-\s*([0-9]{1,3})\s*G",
        pdf_text,
        re.IGNORECASE,
    )
    if g_match:
        return f"{g_match.group(1)} G"

    mnok_match = re.search(
        r"Bedriftsansvar\s+innen\s+Norden\s*:\s*([0-9]{1,3})\s*MNOK",
        pdf_text,
        re.IGNORECASE,
    )
    if mnok_match:
        return f"{mnok_match.group(1)} MNOK"

    return ""


def _extract_egenandel(pdf_text: str) -> str:
    match = re.search(
        r"Bedriftsansvar\s*-\s*Norden[^\r\n]{0,80}?Se\s+vilk[åa]r\s+([0-9][0-9\s.,]{2,})\s*kr",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


def _extract_produktansvar(pdf_text: str) -> str:
    match = re.search(
        r"Produktsansvar\s+inntil\s+([0-9]{1,3})\s*MNOK",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} MNOK"

    # Fallback: Product liability expressed with G.
    match = re.search(
        r"Produktansvar[^\r\n]{0,80}?([0-9]{1,3})\s*G",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} G"

    return ""


def _extract_rettshjelp(pdf_text: str) -> str:
    match = re.search(
        r"Rettshjelp[^\r\n]{0,30}([0-9][0-9\s.,]{3,})",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


def transform_data(extracted: dict) -> dict:
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return {}

    # Keep this mapper isolated to Frende documents only.
    if "frende" not in pdf_text.lower():
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
