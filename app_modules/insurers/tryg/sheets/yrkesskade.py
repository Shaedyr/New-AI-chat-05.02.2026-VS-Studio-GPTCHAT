"""
Tryg-specific mapping for sheet: Yrkesskade.

Mapping policy:
- Fill only values that are explicitly found in PDF text.
- Leave cells blank when values are not clear.
- Keep this logic isolated to Tryg format only.

Template row intent:
- Row 3: total Yrkesskade (people + premium)
- Row 4: Kontor-like group (office/sales-with-office)
- Row 5: Main trade group (e.g., rørlegger)
- Row 6: Frivillig yrkesinvaliditet premium (sum)
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


def _to_int_or_blank(value: str):
    d = _digits(value)
    return int(d) if d else ""


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = value.lower()
    replacements = {
        "ø": "o",
        "å": "a",
        "æ": "ae",
        "ã¸": "o",
        "ã¥": "a",
        "ã¦": "ae",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _extract_overview_total(pdf_text: str) -> dict[str, int]:
    """
    Example:
    'Yrkesskade 22 personer 51 199'
    -> C3=22, D3=51199
    """
    out: dict[str, int] = {}
    match = re.search(
        r"Yrkesskade\s+([0-9]{1,4})\s+personer\s+([0-9][0-9\s.,]{1,})",
        pdf_text,
        re.IGNORECASE,
    )
    if not match:
        return out

    people = _to_int_or_blank(match.group(1))
    premium = _to_int_or_blank(match.group(2))
    if people != "":
        out["C3"] = people
    if premium != "":
        out["D3"] = premium
    return out


def _extract_group_blocks(pdf_text: str) -> list[dict[str, object]]:
    """
    Parse tariff blocks in Yrkesskade specification section.
    Each returned block may contain:
    - people
    - years
    - tariff_text
    - yrk_premium
    - friv_premium
    """
    lines = [ln.strip() for ln in (pdf_text or "").splitlines() if ln.strip()]
    blocks: list[dict[str, object]] = []

    start_indexes: list[int] = []
    for i, raw in enumerate(lines):
        raw_norm = _normalize_text(raw)
        if "prisen er basert pa" in raw_norm:
            start_indexes.append(i)

    for idx, start in enumerate(start_indexes):
        end = start_indexes[idx + 1] if idx + 1 < len(start_indexes) else min(len(lines), start + 30)
        block_lines = lines[start:end]
        block_text = "\n".join(block_lines)

        people_match = re.search(
            r"Prisen\s+er\s+basert\s+p[åa]\s+([0-9]{1,4})\s+personer",
            block_text,
            re.IGNORECASE,
        )
        years_match = re.search(
            r"Antall\s+[åa]rsverk\s*:\s*([0-9]{1,4})(?:[.,][0-9]+)?",
            block_text,
            re.IGNORECASE,
        )
        tariff_match = re.search(
            r"Tariff\s+gr\.\s*:\s*([^\r\n]+)",
            block_text,
            re.IGNORECASE,
        )
        yrk_match = re.search(
            r"Yrkesskade\s+for\s+ansatte\s*\*\)\s*Se\s+vilk[åa]r\s+([0-9]{1,3}(?:\s[0-9]{3})+|[0-9]{4,6})",
            block_text,
            re.IGNORECASE,
        )
        friv_match = re.search(
            r"Frivillig\s+yrkesinvaliditet[^\r\n]{0,80}?Se\s+vilk[åa]r\s+([0-9]{1,3}(?:\s[0-9]{3})+|[0-9]{3,6})",
            block_text,
            re.IGNORECASE,
        )

        people = _to_int_or_blank(people_match.group(1)) if people_match else ""
        years = _to_int_or_blank(years_match.group(1)) if years_match else ""
        tariff = tariff_match.group(1).strip() if tariff_match else ""
        yrk_premium = _to_int_or_blank(yrk_match.group(1)) if yrk_match else ""
        friv_premium = _to_int_or_blank(friv_match.group(1)) if friv_match else ""

        # Keep block only if it looks like real Yrkesskade block.
        if yrk_premium != "" and (people != "" or years != "" or tariff):
            blocks.append(
                {
                    "people": people,
                    "years": years,
                    "tariff_text": tariff,
                    "yrk_premium": yrk_premium,
                    "friv_premium": friv_premium,
                }
            )

    return blocks


def _assign_row_for_block(block: dict[str, object]) -> int:
    """
    Row 4 is office-like groups, row 5 is main trade group.
    """
    tariff = _normalize_text(str(block.get("tariff_text", "")))
    if any(token in tariff for token in ("kontor", "administrasjon", "selger")):
        return 4
    return 5


def transform_data(extracted: dict) -> dict:
    out: dict[str, object] = {}
    pdf_text = (extracted or {}).get("pdf_text", "") or ""
    if not pdf_text:
        return out

    normalized_all = _normalize_text(pdf_text)
    if "tryg" not in normalized_all or "yrkesskade" not in normalized_all:
        return out

    # Row 3 from overview totals.
    out.update(_extract_overview_total(pdf_text))

    # Rows 4-5 and row 6 from tariff blocks.
    blocks = _extract_group_blocks(pdf_text)
    friv_sum = 0

    for block in blocks:
        row = _assign_row_for_block(block)
        years = block.get("years", "")
        people = block.get("people", "")
        yrk_premium = block.get("yrk_premium", "")
        friv_premium = block.get("friv_premium", "")

        if years != "":
            out[f"B{row}"] = years
        if people != "":
            out[f"C{row}"] = people
        if yrk_premium != "":
            out[f"D{row}"] = yrk_premium

        if friv_premium != "":
            friv_sum += int(friv_premium)

    if friv_sum > 0:
        out["D6"] = friv_sum

    return out


__all__ = ["CELL_MAP", "transform_data"]
