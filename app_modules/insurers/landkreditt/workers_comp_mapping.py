"""
Landkreditt-specific mapping for sheet: Yrkesskade.

Current scope:
- Row 3: total (all groups).
- Row 4: Kontor/administrasjon.
- Row 5: Grunnarbeider.

Mapped columns:
- B = Årsverk
- C = Personer (antall ansatte)
- D = Premium
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


def _to_int(value: str):
    d = _digits(value)
    return int(d) if d else ""


def _extract_total_row(pdf_text: str) -> dict[str, int]:
    out: dict[str, int] = {}

    # Example: "Yrkesskade: Antall ansatte 20, årsverk: 16 83 071"
    match = re.search(
        r"Yrkesskade\s*:\s*Antall\s+ansatte\s*([0-9]{1,4})\s*,?\s*[åa]rsverk\s*[: ]\s*([0-9]{1,4})\s+([0-9][0-9\s.,]{2,})",
        pdf_text,
        re.IGNORECASE,
    )
    if match:
        out["C3"] = _to_int(match.group(1))
        out["B3"] = _to_int(match.group(2))
        out["D3"] = _to_int(match.group(3))
        return out

    # Fallback: totals from "Forsikring Pris pr år ... Yrkesskade 83 071"
    price_match = re.search(
        r"Forsikring\s+Pris\s+pr\s+[åa]r.*?Yrkesskade\s+([0-9][0-9\s.,]{2,})",
        pdf_text,
        re.IGNORECASE | re.DOTALL,
    )
    if price_match:
        out["D3"] = _to_int(price_match.group(1))

    counts_match = re.search(
        r"Antall\s+ansatte\s*([0-9]{1,4})\s*,?\s*[åa]rsverk\s*[: ]\s*([0-9]{1,4})",
        pdf_text,
        re.IGNORECASE,
    )
    if counts_match:
        out["C3"] = _to_int(counts_match.group(1))
        out["B3"] = _to_int(counts_match.group(2))

    return out


def _extract_group_row(pdf_text: str, label: str, row: int) -> dict[str, int]:
    out: dict[str, int] = {}

    # Capture a short block starting at the group label.
    block_match = re.search(
        rf"{label}\s+Antall\s+ansatte\s*:\s*([0-9]{{1,4}})\s*,?\s*[åa]rsverk\s*:\s*([0-9]{{1,4}})(.*?)(?:NEW\s*LINE|G\s*=|Side\s+\d+|$)",
        pdf_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return out

    ansatte = _to_int(block_match.group(1))
    arsverk = _to_int(block_match.group(2))
    block_tail = block_match.group(3) or ""

    lovbestemt_match = re.search(
        r"Lovbestemt\s+dekning\s*:\s*kr\s*([0-9][0-9\s.,]{1,})",
        block_tail,
        re.IGNORECASE,
    )
    utvidet_match = re.search(
        r"Utvidet\s+dekning\s*:\s*kr\s*([0-9][0-9\s.,]{1,})",
        block_tail,
        re.IGNORECASE,
    )

    premium = 0
    if lovbestemt_match:
        premium += _to_int(lovbestemt_match.group(1)) or 0
    if utvidet_match:
        premium += _to_int(utvidet_match.group(1)) or 0

    if arsverk:
        out[f"B{row}"] = arsverk
    if ansatte:
        out[f"C{row}"] = ansatte
    if premium:
        out[f"D{row}"] = premium

    return out


def transform_data(extracted: dict) -> dict:
    out: dict[str, object] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    if "landkreditt" not in pdf_text.lower() or "yrkesskade" not in pdf_text.lower():
        return out

    out.update(_extract_total_row(pdf_text))
    out.update(_extract_group_row(pdf_text, "Kontor/administrasjon", 4))
    out.update(_extract_group_row(pdf_text, "Grunnarbeider", 5))
    return out
