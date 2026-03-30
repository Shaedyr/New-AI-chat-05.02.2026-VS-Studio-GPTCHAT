"""
IF-specific mapping for the Yrkesskade sheet.

Target rows (template):
- Row 3: Yrkesskade premium -> D3
- Row 4: Kontor years/person count -> B4/C4
- Row 5: Tømrer/bygningsarbeider-type years/person count -> B5/C5
- Row 6: Frivillig yrkesinvaliditet amount -> D6

Missing values are left blank.
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


ROW_CONFIG = {
    3: {
        "labels": [r"\byrkesskade\b"],
        "mode": "amount",
    },
    4: {
        "labels": [r"\bkontor\b"],
        "mode": "count",
    },
    5: {
        "labels": [
            r"tomrer",
            r"tømrer",
            r"bygningsarbeider",
            r"takarbeider",
            r"tilkomsttekniker",
        ],
        "mode": "count",
    },
    6: {
        "labels": [
            r"frivillig\s+yrkesinvaliditet",
            r"yrkesinvaliditet\s*1\s*%?\s*til\s*14\s*%?",
        ],
        "mode": "amount",
    },
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.lower()
    replacements = {
        "Ã¸": "o",
        "Ã¥": "a",
        "Ã¦": "ae",
        "Ã¶": "o",
        "Ã¼": "u",
        "\u00c3\u00b8": "o",
        "\u00c3\u00a5": "a",
        "\u00c3\u00a6": "ae",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


def _extract_amount(line: str) -> str:
    # Match either "65 009" style or plain "65009".
    candidates = re.findall(r"\b([0-9]{1,3}(?:[\s\.,][0-9]{3})+|[0-9]{4,7})\b", line or "")
    if not candidates:
        return ""

    # Use the right-most valid amount; PDFs often contain old/new side-by-side values.
    for candidate in reversed(candidates):
        value = _digits(candidate)
        if not value:
            continue
        number = int(value)
        if 1900 <= number <= 2100:
            continue
        return value
    return ""


def _extract_count(line: str) -> str:
    candidates = re.findall(r"\b([0-9]{1,3}(?:[\s\.,][0-9]{3})?|[0-9]{1,2})\b", line or "")
    if not candidates:
        return ""

    for candidate in reversed(candidates):
        value = _digits(candidate)
        if not value:
            continue
        number = int(value)
        # Years and large prices are not counts.
        if 1900 <= number <= 2100:
            continue
        if number > 500:
            continue
        return value
    return ""


def _extract_antall_personer(pdf_text: str) -> str:
    normalized = _normalize_text(pdf_text or "")
    # Example in Malco IF: "Antall personer: 9"
    match = re.search(r"antall\s+personer\s*:\s*([0-9]{1,4})", normalized, re.IGNORECASE)
    if not match:
        return ""
    return _digits(match.group(1))


def _matching_lines(pdf_text: str, label_patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for raw_line in (pdf_text or "").splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue
        normalized_line = _normalize_text(line)
        if any(re.search(pattern, normalized_line, re.IGNORECASE) for pattern in label_patterns):
            matches.append(line)
    return matches


def transform_data(extracted: dict) -> dict:
    out: dict[str, str] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    # Row 3, column C: total people count for the group when explicitly present.
    antall_personer = _extract_antall_personer(pdf_text)
    if antall_personer:
        out["C3"] = antall_personer

    for row, cfg in ROW_CONFIG.items():
        lines = _matching_lines(pdf_text, cfg["labels"])
        if not lines:
            continue

        mode = cfg.get("mode", "")
        if mode == "amount":
            for line in lines:
                amount = _extract_amount(line)
                if amount:
                    out[f"D{row}"] = amount
                    break
            continue

        if mode == "count":
            for line in lines:
                count = _extract_count(line)
                if count:
                    out[f"B{row}"] = count
                    break
            continue

    return out


__all__ = ["CELL_MAP", "transform_data"]
