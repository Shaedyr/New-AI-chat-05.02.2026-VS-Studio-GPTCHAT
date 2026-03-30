"""
Landkreditt-specific mapping for sheet: Prosjekt,entreprenor.

Current agreed scope:
- A3/B3: Prosjektforsikring / premium (from overview section).
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _extract_project_premium(pdf_text: str) -> str:
    """
    Example block:
    Prosjektforsikring:
    Omsetning 72 305 000 55 096
    -> premium is the right-most amount in this short block (55 096).
    """
    text = pdf_text or ""

    # Preferred pattern: "Omsetning <value> <premium>"
    omsetning_match = re.search(
        r"Prosjektforsikring\s*:\s*(?:\r?\n)?\s*Omsetning\s+([0-9]{1,3}(?:\s[0-9]{3})+)\s+([0-9]{1,3}(?:\s[0-9]{3})+)",
        text,
        flags=re.IGNORECASE,
    )
    if omsetning_match:
        return omsetning_match.group(2)

    # Fallback: short block after the heading, pick the right-most amount.
    match = re.search(
        r"Prosjektforsikring\s*:\s*(.{0,90})",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    block = match.group(1)
    numbers = re.findall(r"([0-9]{1,3}(?:\s[0-9]{3})+|[0-9]{5,7})", block)
    return numbers[-1] if numbers else ""


def transform_data(extracted: dict) -> dict:
    out: dict[str, object] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    lowered = pdf_text.lower()
    if "landkreditt" not in lowered or "prosjektforsikring" not in lowered:
        return out

    premium = _extract_project_premium(pdf_text)
    premium_digits = _digits(premium)
    if premium_digits:
        out["A3"] = "Prosjektforsikring"
        out["B3"] = int(premium_digits)

    return out
