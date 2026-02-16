"""
Gjensidige-specific mapping for the Yrkesskade sheet.

Current scope:
- Fill Yrkesskade row data only when values are explicitly found in PDF text.
- Keep missing fields blank.
- Do not affect other insurer formats.
"""

from __future__ import annotations

import re


ROW_CONFIG = {
    3: {
        "labels": [
            r"lovbestemt\s+yrkesskade",
        ]
    },
    4: {
        "labels": [
            r"\bkontor\b",
        ]
    },
    5: {
        "labels": [
            r"tomrer\s*/\s*bygningsarbeider",
            r"\bbygningsarbeider\b",
            r"\btomrer\b",
        ]
    },
    6: {
        "labels": [
            r"frivillig\s+yrkesinvaliditet",
            r"yrkesinvaliditet\s*1\s*%?\s*til\s*14\s*%?",
        ]
    },
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.lower()
    replacements = {
        "ø": "o",
        "å": "a",
        "æ": "ae",
        "ö": "o",
        "ü": "u",
        "\u00c3\u00b8": "o",
        "\u00c3\u00a5": "a",
        "\u00c3\u00a6": "ae",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


def _extract_amount(line: str) -> str:
    candidates = re.findall(r"\b([0-9]{1,3}(?:[\s\.,][0-9]{3})+|[0-9]{4,6})\b", line)
    if not candidates:
        return ""

    for candidate in reversed(candidates):
        value = _normalize_digits(candidate)
        if not value:
            continue
        number = int(value)
        # Guard against years.
        if 1900 <= number <= 2100:
            continue
        return value
    return ""


def _extract_count(normalized_line: str, kind: str) -> str:
    if not normalized_line:
        return ""

    if kind == "arsverk":
        match = re.search(r"\b([0-9][0-9\s\.,]{0,10})\s*arsverk\b", normalized_line, re.IGNORECASE)
    elif kind == "personer":
        match = re.search(r"\b([0-9][0-9\s\.,]{0,10})\s*person(?:er)?\b", normalized_line, re.IGNORECASE)
    else:
        return ""

    if not match:
        return ""
    return _normalize_digits(match.group(1))


def _extract_row_values(pdf_text: str, label_patterns: list[str]) -> dict[str, str]:
    for raw_line in pdf_text.splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue

        normalized_line = _normalize_text(line)
        if not any(re.search(pattern, normalized_line, re.IGNORECASE) for pattern in label_patterns):
            continue

        amount = _extract_amount(line)
        arsverk = _extract_count(normalized_line, "arsverk")
        personer = _extract_count(normalized_line, "personer")

        if amount or arsverk or personer:
            return {
                "B": arsverk,
                "C": personer,
                "D": amount,
            }
    return {}


def transform_data(extracted: dict) -> dict:
    """
    Return dynamic Excel mapping (cell_ref -> value) for Yrkesskade sheet.
    """
    out: dict[str, str] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    for row, config in ROW_CONFIG.items():
        row_values = _extract_row_values(pdf_text, config["labels"])
        for column in ("B", "C", "D"):
            value = row_values.get(column, "")
            if value:
                out[f"{column}{row}"] = value

    return out

