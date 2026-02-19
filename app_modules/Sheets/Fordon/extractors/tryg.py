# app_modules/Sheets/Fordon/extractors/tryg.py
"""
Tryg Forsikring extractor for Fordon sheet.

Principles:
- Keep parsing isolated to Tryg format only.
- Prefer section-level extraction from "Forsikringsbevis | Spesifikasjon".
- Use registration-anchored fallback to avoid empty rows.
- Leave fields blank when no reliable value exists.
"""

from __future__ import annotations

import re
import streamlit as st


COVERAGE_WORDS = ("kasko", "delkasko", "ansvar", "brann", "tyveri", "glass", "redning")
COVERAGE_RE = re.compile(r"\b(kasko|delkasko|ansvar|brann|tyveri|glass|redning)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d{1,3}(?:[ .]\d{3})+|\d{3,6}")
REG_RE = re.compile(r"\b([A-Z]{2}\s?\d{4,5})\b")
REG_BLOCK_RE = re.compile(r"(?:Kjennemerke|Registreringsnummer)\s*[:\-]?\s*([A-Z]{2}\s?\d{4,5})", re.IGNORECASE)

SPEC_HEADER_RE = re.compile(
    r"(?P<header>(?:Motorvogn|Personbil|Varebil|Lastebil|Campingvogn og tilhenger|Tilhenger|Traktor|Moped|Motorsykkel|Snoscooter|Bat)[^\n]*?)\s*[-–—]\s*Vilkar\s+[A-Z]{2,5}\d+",
    re.IGNORECASE,
)

PRODUCT_HINT_RE = re.compile(
    r"([A-Za-z0-9 ,/()\-]{2,120}?)\s*[-–—]\s*Vilkar\s+[A-Z]{2,5}\d+",
    re.IGNORECASE,
)

OVERVIEW_ROW_RE = re.compile(
    r"(Motorvogn|Personbil|Varebil|Lastebil|Campingvogn og tilhenger|Tilhenger|Traktor|Moped|Motorsykkel|Snoscooter|Bat)\s+([A-Z]{2}\d{4,5})\s+(\d{2,7})",
    re.IGNORECASE,
)

TEXT_REPLACEMENTS = {
    "\u00a0": " ",
    "\r\n": "\n",
    "\r": "\n",
    "Vilkår": "Vilkar",
    "Snøscooter": "Snoscooter",
    "Båt": "Bat",
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


def _normalize_tryg_text(text: str) -> str:
    out = text or ""
    for src, dst in TEXT_REPLACEMENTS.items():
        out = out.replace(src, dst)
    return out


def _clean_text_value(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "")).strip()
    value = re.sub(r"\s+(?:Type|Forsikringssum|Dekning|Vilkar|Egenandel|Pris).*$", "", value, flags=re.IGNORECASE)
    return value.strip()


def _normalize_reg(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def _normalize_number(value: str) -> str:
    if not value:
        return ""
    raw = value.strip().lower().replace("kr", "")
    if re.search(r"[^0-9\s.,]", raw):
        return ""
    m = NUMBER_RE.search(raw)
    if not m:
        return ""
    normalized = m.group(0).replace(".", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""
    if set(normalized.replace(" ", "")) == {"0"}:
        return ""
    return normalized


def _coverage_from_text(text: str) -> str:
    m = COVERAGE_RE.search(text or "")
    return m.group(1).capitalize() if m else ""


def _infer_vehicle_type(type_text: str) -> str:
    vt = (type_text or "").lower()
    if any(word in vt for word in ("tilhenger", "henger", "campingvogn")):
        return "trailer"
    if any(word in vt for word in ("personbil", "varebil", "lastebil", "motorvogn", "bil")):
        return "car"
    if any(word in vt for word in ("traktor", "arbeid", "maskin", "redskap")):
        return "tractor"
    if any(word in vt for word in ("moped", "motorsykkel", "snoscooter")):
        return "moped"
    if "bat" in vt:
        return "boat"
    return "other"


def _extract_table_fields(section: str) -> dict:
    if not section:
        return {}

    # Join split thousands first (e.g. "6\n000" -> "6 000")
    flat = re.sub(r"(\d)\s*[\r\n]+\s*(\d{3})", r"\1 \2", section)
    flat = re.sub(r"\s+", " ", flat)

    num_re = r"\d{1,3}(?:[ .]\d{3})+|\d{3,6}"
    cov_re = r"kasko|delkasko|ansvar|brann|tyveri|glass|redning"

    row = re.search(
        rf"({cov_re})\s+(?:[A-Z]{{2,5}}\d+\s+)?({num_re})\s+({num_re})\s+({num_re})",
        flat,
        re.IGNORECASE,
    )
    if row:
        return {
            "coverage": row.group(1).capitalize(),
            "sum_insured": _normalize_number(row.group(2)),
            "deductible": _normalize_number(row.group(3)),
            "premium": _normalize_number(row.group(4)),
        }

    # Fallback: first coverage word + first 3 numbers after it.
    cov = re.search(rf"({cov_re})", flat, re.IGNORECASE)
    if cov:
        tail = flat[cov.end() : cov.end() + 220]
        nums = re.findall(num_re, tail)
        if len(nums) >= 2:
            return {
                "coverage": cov.group(1).capitalize(),
                "sum_insured": _normalize_number(nums[0]),
                "deductible": _normalize_number(nums[1]),
                "premium": _normalize_number(nums[2]) if len(nums) >= 3 else "",
            }

    return {}


def _extract_vehicle_fields(section: str, header_hint: str = "") -> dict:
    kv = {
        "registration": "",
        "make_model_year": "",
        "type": "",
        "sum_insured": "",
        "coverage": "",
        "leasing": "",
        "annual_mileage": "",
        "bonus": "",
        "deductible": "",
        "premium": "",
    }

    reg_match = REG_BLOCK_RE.search(section)
    if reg_match:
        kv["registration"] = _normalize_reg(reg_match.group(1))

    make_match = re.search(
        r"Fabrikat/(?:arsmodell)(?:/Type)?\s*[:\-]?\s*([^\n\r]{3,120})",
        section,
        re.IGNORECASE,
    )
    if make_match:
        kv["make_model_year"] = _clean_text_value(make_match.group(1))

    if not kv["make_model_year"] and kv["registration"]:
        inline = re.search(
            rf"{re.escape(kv['registration'])}\s+([A-Za-z0-9 .,/()\-]{{3,120}}?(?:19|20)\d{{2}})",
            section,
            re.IGNORECASE,
        )
        if inline:
            kv["make_model_year"] = _clean_text_value(inline.group(1))

    type_match = re.search(r"Type\s*[:\-]?\s*([^\n\r]{2,80})", section, re.IGNORECASE)
    if type_match:
        candidate = _clean_text_value(type_match.group(1))
        if candidate and not re.search(r"vilkar|forsikringssum|egenandel|pris", candidate, re.IGNORECASE):
            kv["type"] = candidate

    if not kv["type"] and header_hint:
        kv["type"] = _clean_text_value(header_hint)

    sum_match = re.search(r"Forsikringssum\s*(?:kr)?\s*[:\-]?\s*([0-9][0-9 .]{2,})", section, re.IGNORECASE)
    if sum_match:
        kv["sum_insured"] = _normalize_number(sum_match.group(1))

    table = _extract_table_fields(section)
    if table.get("coverage"):
        kv["coverage"] = table["coverage"]
    if table.get("sum_insured"):
        kv["sum_insured"] = table["sum_insured"]
    if table.get("deductible"):
        kv["deductible"] = table["deductible"]
    if table.get("premium"):
        kv["premium"] = table["premium"]

    if not kv["coverage"]:
        kv["coverage"] = _coverage_from_text(section)

    return kv


def _extract_specification_sections(pdf_text: str, seen: set[str]) -> list[dict]:
    vehicles: list[dict] = []
    headers = list(SPEC_HEADER_RE.finditer(pdf_text))

    for idx, header in enumerate(headers):
        start = header.start()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else min(len(pdf_text), start + 8000)
        section = pdf_text[start:end]

        fields = _extract_vehicle_fields(section, header.group("header"))
        reg = fields.get("registration", "")
        if not reg or reg in seen:
            continue

        seen.add(reg)
        fields["source"] = "specification"
        vehicles.append(fields)

    return vehicles


def _extract_registration_blocks(pdf_text: str, seen: set[str]) -> list[dict]:
    vehicles: list[dict] = []
    matches = list(REG_BLOCK_RE.finditer(pdf_text))

    for idx, match in enumerate(matches):
        reg = _normalize_reg(match.group(1))
        if not reg or reg in seen:
            continue

        start = max(0, match.start() - 350)
        end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(pdf_text), match.start() + 2200)
        section = pdf_text[start:end]

        pre = pdf_text[max(0, match.start() - 450) : match.start()]
        header_hint_match = PRODUCT_HINT_RE.search(pre)
        header_hint = header_hint_match.group(1) if header_hint_match else ""

        fields = _extract_vehicle_fields(section, header_hint)
        if not fields.get("registration"):
            fields["registration"] = reg

        if fields["registration"] in seen:
            continue

        seen.add(fields["registration"])
        fields["source"] = "registration_block"
        vehicles.append(fields)

    return vehicles


def _extract_overview_rows(pdf_text: str, seen: set[str]) -> list[dict]:
    vehicles: list[dict] = []

    for match in OVERVIEW_ROW_RE.finditer(pdf_text):
        product = _clean_text_value(match.group(1))
        reg = _normalize_reg(match.group(2))
        premium = _normalize_number(match.group(3))

        if not reg or reg in seen:
            continue

        seen.add(reg)
        vehicles.append(
            {
                "registration": reg,
                "make_model_year": "",
                "type": product,
                "sum_insured": "",
                "coverage": "",
                "leasing": "",
                "annual_mileage": "",
                "bonus": "",
                "deductible": "",
                "premium": premium,
                "source": "overview",
            }
        )

    return vehicles


def _extract_header_only(pdf_text: str, seen: set[str]) -> list[dict]:
    vehicles: list[dict] = []

    for header in SPEC_HEADER_RE.finditer(pdf_text):
        product = _clean_text_value(header.group("header"))
        tail = pdf_text[header.end() : min(len(pdf_text), header.end() + 1200)]

        reg_match = REG_RE.search(tail)
        if not reg_match:
            continue

        reg = _normalize_reg(reg_match.group(1))
        if not reg or reg in seen:
            continue

        seen.add(reg)
        vehicles.append(
            {
                "registration": reg,
                "make_model_year": "",
                "type": product,
                "sum_insured": "",
                "coverage": "",
                "leasing": "",
                "annual_mileage": "",
                "bonus": "",
                "deductible": "",
                "premium": "",
                "source": "header",
            }
        )

    return vehicles


def _standardize_vehicle(vehicle: dict) -> dict:
    type_text = vehicle.get("type", "")
    vehicle_type = _infer_vehicle_type(type_text)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", vehicle.get("make_model_year", ""))
    year = year_match.group(1) if year_match else ""

    return {
        "registration": vehicle.get("registration", ""),
        "make_model_year": vehicle.get("make_model_year", ""),
        "year": year,
        "vehicle_type": vehicle_type,
        "type": (type_text or "").lower(),
        "coverage": vehicle.get("coverage", ""),
        "leasing": vehicle.get("leasing", ""),
        "annual_mileage": vehicle.get("annual_mileage", ""),
        "bonus": vehicle.get("bonus", ""),
        "deductible": vehicle.get("deductible", ""),
        "sum_insured": vehicle.get("sum_insured", ""),
        "premium": vehicle.get("premium", ""),
        "source": vehicle.get("source", ""),
    }


def extract_tryg_vehicles(pdf_text: str) -> list:
    """Extract vehicles from Tryg Forsikring PDF text."""
    st.write("    DEBUG: Tryg pattern matching...")

    normalized = _normalize_tryg_text(pdf_text)
    vehicles: list[dict] = []
    seen: set[str] = set()

    spec = _extract_specification_sections(normalized, seen)
    vehicles.extend(spec)
    st.write(f"    - Pattern 0 (Specification): {len(spec)} vehicles")

    reg_blocks = _extract_registration_blocks(normalized, seen)
    vehicles.extend(reg_blocks)
    st.write(f"    - Pattern 1 (Registration blocks): {len(reg_blocks)} vehicles")

    overview = _extract_overview_rows(normalized, seen)
    vehicles.extend(overview)
    st.write(f"    - Pattern 2 (Overview): {len(overview)} vehicles")

    headers = _extract_header_only(normalized, seen)
    vehicles.extend(headers)
    st.write(f"    - Pattern 3 (Headers): {len(headers)} vehicles")

    st.write(f"    Total Tryg vehicles extracted: {len(vehicles)}")
    return [_standardize_vehicle(v) for v in vehicles]


def categorize_tryg_vehicle(vehicle: dict) -> str:
    """Compatibility helper used by other modules."""
    return vehicle.get("vehicle_type", "other")
