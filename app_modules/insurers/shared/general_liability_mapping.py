"""
Alminnelig ansvar mapping orchestrator (shared).

Insurer-specific extraction stays isolated in this file.
Only fields found in the PDF are mapped; missing fields stay blank.
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
    "tilbud_pris": "G",
    "tilbud_kommentar": "H",
}

DEFAULT_ENTRY = {
    "virksomhet": "",
    "annual_turnover_2024": "",
    "bedriftsansvar": "",
    "egenandel_ansvar": "",
    "produktansvar": "",
    "rettshjelp_sum": "",
    "tilbud_pris": "",
    "tilbud_kommentar": "",
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.replace("\u00a0", " ")
    replacements = {
        "\u00f8": "o",
        "\u00e5": "a",
        "\u00e6": "ae",
        "\u00d8": "o",
        "\u00c5": "a",
        "\u00c6": "ae",
        "\u00c3\u00b8": "o",
        "\u00c3\u00a5": "a",
        "\u00c3\u00a6": "ae",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)

    cleaned = cleaned.lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _to_int_or_blank(value: str):
    digits = _digits(value)
    return int(digits) if digits else ""


def _normalize_sum_value(value: str):
    text = (value or "").strip()
    if not text:
        return ""

    if re.search(r"\bg\b", text, re.IGNORECASE):
        digits = _digits(text)
        return f"{digits} G" if digits else text

    digits = _digits(text)
    return int(digits) if digits else ""


def _first_match(patterns: list[str], text: str) -> re.Match | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match
    return None


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip(" .,:;|-"))


def _clean_virksomhet(label: str) -> str:
    value = _clean_label(label)
    if not value:
        return ""

    # IF/scan text often appends right-column labels on same line.
    stop_markers = (
        r"\bbrannalarm\b",
        r"\bkrigsomr",
        r"\btyverisikring\b",
        r"\bforsikrede\b",
        r"\bdekning\b",
        r"\berstatningsgrunnlag\b",
        r"\bforsikringssum\b",
        r"\begenandel\b",
    )
    for marker in stop_markers:
        value = re.split(marker, value, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    return value.strip(" .,:;|-")


def _extract_if_entry(pdf_text: str, normalized: str) -> dict:
    entry = dict(DEFAULT_ENTRY)

    virksomhet_match = _first_match(
        [
            r"virksomhet\s*[:\-]?\s*([^\r\n]+)",
            r"omsetning\s+forsikret\s+virksomhet\s*[:\-]?\s*virksomhet\s+([^\r\n]+)",
        ],
        pdf_text,
    )
    if virksomhet_match:
        entry["virksomhet"] = _clean_virksomhet(virksomhet_match.group(1))
    if not entry["virksomhet"]:
        virksomhet_table = _first_match(
            [r"virksomhet\s+omsetning\s+(.+?)\s+[0-9][0-9\s.,]{3,}\s*kr"],
            normalized,
        )
        if virksomhet_table:
            entry["virksomhet"] = _clean_virksomhet(virksomhet_table.group(1))

    omsetning_match = _first_match(
        [
            r"arsomsetning[^0-9]{0,40}([0-9][0-9\s.,]{3,})",
            r"omsetning\s+forsikret\s+virksomhet[^0-9]{0,60}([0-9][0-9\s.,]{3,})",
        ],
        normalized,
    )
    if omsetning_match:
        entry["annual_turnover_2024"] = omsetning_match.group(1)

    ansvar_start = normalized.find("ansvarsforsikring")
    ansvar_section = normalized[ansvar_start : ansvar_start + 7000] if ansvar_start >= 0 else normalized

    bedrift_sum = _first_match(
        [
            r"bedriftsansvar(?:.{0,220}?forsikringssum\s*:?\s*)([0-9]+\s*g|[0-9][0-9\s.,]{3,})",
            r"bedriftsansvar\s+([0-9]+\s*g)",
        ],
        ansvar_section,
    )
    if bedrift_sum:
        entry["bedriftsansvar"] = bedrift_sum.group(1)

    produkt_sum = _first_match(
        [
            r"produktansvar(?:.{0,220}?forsikringssum\s*:?\s*)([0-9]+\s*g|[0-9][0-9\s.,]{3,})",
            r"produktansvar\s+([0-9]+\s*g)",
        ],
        ansvar_section,
    )
    if produkt_sum:
        entry["produktansvar"] = produkt_sum.group(1)

    egenandel_match = _first_match(
        [r"egenandel\s+per\s+skade\s*[:\-]?\s*([0-9][0-9\s.,]{3,})"],
        ansvar_section,
    )
    if egenandel_match and not entry["egenandel_ansvar"]:
        entry["egenandel_ansvar"] = egenandel_match.group(1)

    rettshjelp_match = _first_match(
        [r"rettshjelp[^0-9]{0,30}([0-9][0-9\s.,]{3,})"],
        normalized,
    )
    if rettshjelp_match:
        entry["rettshjelp_sum"] = rettshjelp_match.group(1)

    price_match = _first_match(
        [
            r"ansvarsforsikring\s+pris\s+per\s+ar\s+nok\s*([0-9][0-9\s.,]{3,})",
            r"ansvarsforsikring\s+([0-9][0-9\s.,]{3,})",
        ],
        normalized,
    )
    if price_match:
        entry["tilbud_pris"] = price_match.group(1)

    return entry


def _extract_gjensidige_entry(pdf_text: str, normalized: str) -> dict:
    entry = dict(DEFAULT_ENTRY)

    split_index = normalized.find("forsikringsbevis")
    head = normalized[:split_index] if split_index > 0 else normalized[:9000]

    price_match = _first_match([r"ansvarsforsikring\s+([0-9][0-9\s.,]{3,})"], head)
    if price_match:
        entry["tilbud_pris"] = price_match.group(1)

    omsetning_match = _first_match([r"sist\s+kjente\s+omsetning\s+([0-9][0-9\s.,]{3,})"], head)
    if omsetning_match:
        entry["annual_turnover_2024"] = omsetning_match.group(1)

    return entry


def _extract_tryg_entry(pdf_text: str, normalized: str) -> dict:
    entry = dict(DEFAULT_ENTRY)

    start = normalized.find("alminnelig ansvarsforsikring")
    section = pdf_text[start : start + 8000] if start >= 0 else pdf_text[:12000]

    virksomhet_match = _first_match([r"virksomhet\s*[:\-]?\s*([^\r\n]+)"], section)
    if virksomhet_match:
        raw_value = _clean_label(virksomhet_match.group(1))
        if raw_value.lower() not in {"virksomhet", "dekning", "vilkar", "vilkar"}:
            entry["virksomhet"] = raw_value

    omsetning_match = _first_match([r"driftsinntekter\s*kr\s*([0-9][0-9\s.,]{3,})"], normalized)
    if omsetning_match:
        entry["annual_turnover_2024"] = omsetning_match.group(1)

    bedrift_row = _first_match(
        [
            r"ansvar\s+for\s+virksomheten\s*\*?\s+([0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})",
        ],
        section,
    )
    if bedrift_row:
        entry["bedriftsansvar"] = bedrift_row.group(1)
        entry["egenandel_ansvar"] = bedrift_row.group(2)
        entry["tilbud_pris"] = bedrift_row.group(3)

    rettshjelp_row = _first_match([r"rettshjelp(?:\s+[a-z0-9]{4,})?\s+([0-9][0-9\s.,]{3,})"], section)
    if rettshjelp_row:
        entry["rettshjelp_sum"] = rettshjelp_row.group(1)

    if not entry["tilbud_pris"]:
        prices = re.findall(r"\bpris\s+([0-9][0-9\s.,]{3,})\b", section, re.IGNORECASE)
        if prices:
            entry["tilbud_pris"] = prices[-1]

    return entry


def _extract_ly_entry(pdf_text: str, normalized: str) -> dict:
    entry = dict(DEFAULT_ENTRY)

    virksomhet_match = _first_match([r"naeringskode\s+(.+?)\s+sist\s+kjente\s+omsetning"], normalized)
    if virksomhet_match:
        entry["virksomhet"] = _clean_label(virksomhet_match.group(1))

    omsetning_match = _first_match([r"sist\s+kjente\s+omsetning\s+([0-9][0-9\s.,]{3,})"], normalized)
    if omsetning_match:
        entry["annual_turnover_2024"] = omsetning_match.group(1)

    bedrift_row = _first_match(
        [r"bedriftsansvar\s+([0-9]+\s*g|[0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})"],
        normalized,
    )
    bedrift_price = ""
    if bedrift_row:
        entry["bedriftsansvar"] = bedrift_row.group(1)
        entry["egenandel_ansvar"] = bedrift_row.group(2)
        bedrift_price = bedrift_row.group(3)

    produkt_row = _first_match(
        [r"produktansvar\s+([0-9]+\s*g|[0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})\s+([0-9][0-9\s.,]{3,})"],
        normalized,
    )
    produkt_price = ""
    if produkt_row:
        entry["produktansvar"] = produkt_row.group(1)
        produkt_price = produkt_row.group(3)

    rettshjelp_selected = _first_match(
        [r"kundevalgte\s+tilleggsdekninger\s+som\s+er\s+valgt.{0,400}?rettshjelp\s+([0-9][0-9\s.,]{3,})"],
        normalized,
    )
    if rettshjelp_selected:
        entry["rettshjelp_sum"] = rettshjelp_selected.group(1)

    price_match = _first_match([r"ansvarsforsikring\s+([0-9][0-9\s.,]{3,})"], normalized)
    if price_match:
        entry["tilbud_pris"] = price_match.group(1)
    elif bedrift_price and produkt_price:
        entry["tilbud_pris"] = str(_to_int_or_blank(bedrift_price) + _to_int_or_blank(produkt_price))
    elif bedrift_price:
        entry["tilbud_pris"] = bedrift_price

    return entry


def _detect_provider(pdf_text: str) -> str:
    normalized = _normalize_text(pdf_text)
    if "ly forsikring" in normalized:
        return "ly"
    if "gjensidige" in normalized:
        return "gjensidige"
    if "tryg" in normalized:
        return "tryg"
    if "if skadeforsikring" in normalized or re.search(r"\bif\b", normalized):
        return "if"
    return ""


def _extract_entry_by_provider(pdf_text: str, provider: str) -> dict:
    normalized = _normalize_text(pdf_text)
    selected = (provider or "").strip().lower()

    if selected in {"", "auto-detect"}:
        selected = _detect_provider(pdf_text)

    if selected in {"if", "if skadeforsikring"}:
        return _extract_if_entry(pdf_text, normalized)
    if selected == "gjensidige":
        return _extract_gjensidige_entry(pdf_text, normalized)
    if selected == "tryg":
        return _extract_tryg_entry(pdf_text, normalized)
    if selected in {"ly", "ly forsikring"}:
        return _extract_ly_entry(pdf_text, normalized)

    return dict(DEFAULT_ENTRY)


def transform_data(extracted: dict) -> dict:
    """
    Dynamic mapping entry point for the 'Alminnelig ansvar' sheet.
    Returns cell_ref -> value for row 3.
    """
    data = dict(extracted or {})
    pdf_text = data.get("pdf_text", "") or ""
    if not pdf_text:
        return {}

    provider = (data.get("vehicle_provider") or "").strip().lower()
    entry = _extract_entry_by_provider(pdf_text, provider)

    if not any(entry.values()):
        return {}

    out: dict[str, object] = {}

    for field, column in FIELD_COLUMNS.items():
        value = entry.get(field, "")

        if field in {"annual_turnover_2024", "egenandel_ansvar", "tilbud_pris"}:
            value = _to_int_or_blank(value)
        elif field in {"bedriftsansvar", "produktansvar", "rettshjelp_sum"}:
            value = _normalize_sum_value(value)
        else:
            value = (value or "").strip()

        out[f"{column}{ROW_START}"] = value

    return out
