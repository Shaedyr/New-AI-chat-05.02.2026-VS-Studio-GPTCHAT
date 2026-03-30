"""
Frende-specific mapping for sheet: Prosjekt,entreprenor.

Agreed mapping:
- A3/B3: Prosjektforsikring / total premium
- A4/B4: Bygg, anlegg og montasje / premium
- A5/B5: Maskiner og utstyr / premium
- A6/B6: Skade i reklamasjonstiden pga. mangel i entreprisen / premium
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "\u00a0": " ",
        "\r\n": "\n",
        "\r": "\n",
        "Ã¥": "a",
        "Ã¸": "o",
        "Ã¦": "ae",
        "Ã…": "A",
        "Ã˜": "O",
        "Ã†": "AE",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _extract_last_amount(line: str) -> str:
    """
    Extract the right-most amount from a line.
    For Frende project detail rows this corresponds to row premium.
    """
    if not line:
        return ""

    hits = re.findall(r"([0-9]{1,3}(?:[ .]\d{3})+|[0-9]{4,7})", line)
    if not hits:
        return ""
    return hits[-1]


def _find_line(lines: list[str], needle: str) -> str:
    needle_norm = _normalize_text(needle).lower()
    for line in lines:
        if needle_norm in _normalize_text(line).lower():
            return line
    return ""


def _extract_total_project_premium(text: str) -> str:
    """
    Prefer overview row:
    'Prosjektforsikring ... 112096 kr'
    """
    match = re.search(
        r"Prosjektforsikring[^\n\r]{0,160}?([0-9]{1,3}(?:[ .]\d{3})+|[0-9]{5,7})\s*kr",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return ""


def transform_data(extracted: dict) -> dict:
    out: dict[str, object] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    normalized = _normalize_text(pdf_text)
    if "frende" not in normalized.lower() or "prosjektforsikring" not in normalized.lower():
        return out

    lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]

    total_premium = _extract_total_project_premium(normalized)
    bygg_line = _find_line(lines, "Bygg, anlegg og montasje")
    maskiner_line = _find_line(lines, "Maskiner og utstyr")
    rekl_line = _find_line(lines, "Skade i reklamasjonstiden")

    bygg_premium = _extract_last_amount(bygg_line)
    maskiner_premium = _extract_last_amount(maskiner_line)
    rekl_premium = _extract_last_amount(rekl_line)

    if _digits(total_premium):
        out["A3"] = "Prosjektforsikring"
        out["B3"] = int(_digits(total_premium))

    if _digits(bygg_premium):
        out["A4"] = "Bygg, anlegg og montasje"
        out["B4"] = int(_digits(bygg_premium))

    if _digits(maskiner_premium):
        out["A5"] = "Maskiner og utstyr"
        out["B5"] = int(_digits(maskiner_premium))

    if _digits(rekl_premium):
        out["A6"] = "Skade i reklamasjonstiden pga. mangel i entreprisen"
        out["B6"] = int(_digits(rekl_premium))

    return out
