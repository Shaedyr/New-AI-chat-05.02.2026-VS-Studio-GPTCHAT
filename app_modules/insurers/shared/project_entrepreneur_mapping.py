"""
Prosjekt,entreprenor mapping (shared dispatcher).

Current scope:
- IF: A3/B3 from explicit Allrisk value.
- Tryg: A3-A9 / B3-B9 from Bygg/Anlegg/Montasjefors specification rows.
- Other insurers: leave sheet unchanged.
"""

from __future__ import annotations

import re


CELL_MAP: dict = {}

NUMBER_TOKEN_RE = re.compile(r"\d{1,3}(?:[ .]\d{3})+|\d{2,7}")

NORMALIZE_REPLACEMENTS = {
    "\u00a0": " ",
    "\r\n": "\n",
    "\r": "\n",
    "å": "a",
    "ø": "o",
    "æ": "ae",
    "Å": "A",
    "Ø": "O",
    "Æ": "AE",
    "Ã¥": "a",
    "Ã¸": "o",
    "Ã¦": "ae",
    "Ã…": "A",
    "Ã˜": "O",
    "Ã†": "AE",
    "ÃƒÂ¥": "a",
    "ÃƒÂ¸": "o",
    "ÃƒÂ¦": "ae",
    "ÃƒÆ’Ã‚Â¥": "a",
    "ÃƒÆ’Ã‚Â¸": "o",
    "ÃƒÆ’Ã‚Â¦": "ae",
}

TRYG_DETAIL_ROWS = [
    ("bygge-/montasjearbeid", "Bygge-/montasjearbeid, 1.risiko"),
    ("brakker, containere", "Brakker, containere, 1. risiko"),
    ("varer under transport", "Varer under transport, 1.risiko"),
    ("inventar og losore", "Inventar og losore, 1. risiko"),
    ("varer pa fast sted", "Varer pa fast sted, 1. risiko"),
    ("maskiner og utstyr", "Maskiner og utstyr 1. risiko"),
]


def _normalize_text(text: str) -> str:
    out = text or ""
    for src, dst in NORMALIZE_REPLACEMENTS.items():
        out = out.replace(src, dst)
    return out


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _extract_last_amount_from_line(line: str) -> str:
    text = (line or "").strip()
    # Use the final numeric token on the line as "Pris".
    tail = re.search(r"(\d{1,3}(?:[ .]\d{3})*|\d{2,7})\s*$", text)
    if tail:
        token = tail.group(1)
        digits = _digits(token)
        if " " in token or "." in token:
            groups = [g for g in re.split(r"[ .]+", token) if g]
            if len(groups) > 2:
                return groups[-1]
        # OCR can collapse chained columns into one long number.
        # In those rows, the price is still represented by the trailing 3-5 digits.
        if " " not in token and "." not in token and len(digits) > 7:
            return str(int(digits[-5:]))
        return token

    nums = NUMBER_TOKEN_RE.findall(text)
    if nums:
        return nums[-1]
    return ""


def _is_if_document(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    return any(marker in lowered for marker in ("if skadeforsikring", "if.no", "if forsikrer", "if forsikring"))


def _is_tryg_document(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    if "tryg" not in lowered:
        return False
    markers = (
        "bygg/anlegg/montasjefors",
        "vilkar bslmt100",
        "forsikringsbevis | spesifikasjon",
    )
    return any(marker in lowered for marker in markers)


def _extract_allrisk_amount(pdf_text: str) -> str:
    norm = _normalize_text(pdf_text)
    patterns = [
        r"Prosjekt[\-/ ]*entrepren(?:or)\s*-\s*Allrisk\s*([0-9][0-9\s.,]{2,})",
        r"Prosjekt[\-/ ]*entrepren(?:or)forsikring.*?Allrisk\s*([0-9][0-9\s.,]{2,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, norm, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
    return ""


def _extract_tryg_project_section(pdf_text: str) -> str:
    norm = _normalize_text(pdf_text).lower()
    header = re.search(r"bygg/anlegg/montasjefors\s*-\s*vilkar\s*bslmt100", norm, re.IGNORECASE)
    if not header:
        return ""

    section = norm[header.start() : min(len(norm), header.start() + 8000)]
    end_markers = (
        "reise ekstra bedrift - vilkar",
        "behandlingsforsikring",
        "forsikringsbevis | sikkerhetsforskrift",
    )
    cut = len(section)
    for marker in end_markers:
        idx = section.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return section[:cut]


def _transform_if(pdf_text: str) -> dict:
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


def _transform_tryg(pdf_text: str) -> dict:
    if not _is_tryg_document(pdf_text):
        return {}

    section = _extract_tryg_project_section(pdf_text)
    if not section:
        return {}

    out: dict = {}

    total_price_match = re.search(r"\bpris\s+([0-9][0-9\s.,]{2,})\b", section, re.IGNORECASE)
    if total_price_match:
        total_digits = _digits(total_price_match.group(1))
        if total_digits:
            out["A3"] = "Bygg/Anlegg/Montasjefors"
            out["B3"] = int(total_digits)

    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    for idx, (needle, label) in enumerate(TRYG_DETAIL_ROWS, start=4):
        matched_line = ""
        for line in lines:
            if needle in line:
                matched_line = line
                break
        if not matched_line:
            continue

        amount_raw = _extract_last_amount_from_line(matched_line)
        amount_digits = _digits(amount_raw)
        if not amount_digits:
            continue

        out[f"A{idx}"] = label
        out[f"B{idx}"] = int(amount_digits)

    return out


def transform_data(extracted: dict) -> dict:
    """
    Dynamic mapping for the sheet "Prosjekt,entreprenor".
    """
    data = dict(extracted or {})
    pdf_text = data.get("pdf_text", "") or ""
    if not pdf_text:
        return {}

    provider = (data.get("vehicle_provider") or "").strip().lower()

    if provider in ("if", "if skadeforsikring"):
        return _transform_if(pdf_text)
    if provider == "tryg":
        return _transform_tryg(pdf_text)

    if provider not in ("", "auto-detect"):
        return {}

    out_if = _transform_if(pdf_text)
    if out_if:
        return out_if

    out_tryg = _transform_tryg(pdf_text)
    if out_tryg:
        return out_tryg

    return {}
