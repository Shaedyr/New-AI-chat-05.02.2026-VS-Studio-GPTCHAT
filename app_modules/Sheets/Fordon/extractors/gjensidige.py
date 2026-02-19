# app_modules/Sheets/Fordon/extractors/gjensidige.py
"""
Gjensidige extractor for Fordon sheet.

Design goals:
- Keep vehicle detection stable for existing PDFs.
- Avoid leaking shared values to every row.
- Populate sum insured / annual mileage only when explicitly found.
"""

from __future__ import annotations

import re


MACHINE_BRANDS = [
    "Doosan",
    "Hitachi",
    "Caterpillar",
    "Liebherr",
    "Sennebogen",
    "Komatsu",
    "Volvo",
    "JCB",
    "Bobcat",
    "Case",
    "John Deere",
    "New Holland",
    "Kubota",
]
REG_TOKEN = r"[A-Z]{2}\s*\d(?:\s?\d){3,4}"
REG_WITH_SPACES_RE = re.compile(rf"\b({REG_TOKEN})\b", re.IGNORECASE)
LABEL_RE = re.compile(r"\b(kjennemerke|reg\.?\s*nr|regnr|registreringsnummer)\b", re.IGNORECASE)
YEAR_20XX_RE = re.compile(r"\b(20\d{2})\b")
NUMBER_TOKEN_RE = re.compile(r"\b([0-9]{1,3}(?:[\s\.,][0-9]{3})+|[0-9]{5,6})\b")
MASKINLOSORE_RE = re.compile(
    r"maskinl(?:\u00f8|o|0|@|\?|\u00c3\u00b8)s(?:\u00f8|o|0|@|\?|\u00c3\u00b8)re",
    re.IGNORECASE,
)
OCR_TEXT_REPLACEMENTS = {
    "\u00c3\u00b8": "o",
    "\u00c3\u0098": "o",
    "\u00c3\u00a5": "a",
    "\u00c3\u0085": "a",
    "\u00c3\u00a6": "ae",
    "\u00c3\u0086": "ae",
    "\u00f8": "o",
    "\u00d8": "o",
    "\u00e5": "a",
    "\u00c5": "a",
    "\u00e6": "ae",
    "\u00c6": "ae",
}


def _looks_like_gjensidige_pdf(pdf_text: str) -> bool:
    """
    Guard against cross-format false positives.
    Gjensidige extractor should only run on Gjensidige documents.
    """
    text = (pdf_text or "").lower()
    if "gjensidige" not in text:
        return False

    strong_markers = (
        "gjensidige forsikring asa",
        "forsikringsnummer",
        "forsikringsoversikt",
        "næringsbil minigruppe",
        "ureg. arbeidsmaskin",
    )
    return any(marker in text for marker in strong_markers)


def extract_gjensidige_vehicles(pdf_text: str) -> list:
    """Extract vehicles from a Gjensidige PDF text dump."""
    if not _looks_like_gjensidige_pdf(pdf_text):
        return []

    vehicles: list[dict] = []
    seen_registrations: set[str] = set()

    vehicles.extend(_extract_registered_cars(pdf_text, seen_registrations))
    vehicles.extend(_extract_unregistered_tractors(pdf_text))

    return vehicles


def _extract_registered_cars(pdf_text: str, seen: set[str]) -> list:
    """
    Extract registered cars from two common OCR formats:
    1) "VOLKSWAGEN TRANSPORTER 2020 BU 21895"
    2) Table rows where reg numbers appear with spaces.
    """
    vehicles: list[dict] = []

    brands = [
        "VOLKSWAGEN",
        "FORD",
        "TOYOTA",
        "MERCEDES-BENZ",
        "MERCEDES",
        "LAND ROVER",
        "CITROEN",
        "PEUGEOT",
        "VOLVO",
        "BMW",
        "AUDI",
        "NISSAN",
        "RENAULT",
        "OPEL",
        "FIAT",
        "IVECO",
        "MAN",
        "SCANIA",
        "SKODA",
        "HYUNDAI",
        "KIA",
        "MAZDA",
        "MITSUBISHI",
        "SUZUKI",
        "ISUZU",
        "TESLA",
        "POLESTAR",
        "BYD",
        "MG",
        "SEAT",
        "MINI",
    ]

    brands_pattern = "|".join(brands)
    pattern1 = rf"({brands_pattern})\s+([A-Za-z0-9\s\-().]+?)\s+(20\d{{2}})\s+({REG_TOKEN})"

    for match in re.finditer(pattern1, pdf_text, re.IGNORECASE):
        make = match.group(1).strip()
        model = match.group(2).strip()
        year = match.group(3).strip()
        reg = re.sub(r"\s+", "", match.group(4).strip())

        if reg in seen:
            continue
        seen.add(reg)

        pos = match.start()
        section = _slice_context(pdf_text, pos, before=200, after=500)
        premium = _extract_premium_after_position(pdf_text, match.end())

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": "bil",
                "make_model_year": f"{make} {model} {year}",
                "coverage": "kasko",
                "leasing": _extract_leasing(section, pdf_text, reg),
                "annual_mileage": _extract_annual_mileage(section),
                "bonus": _extract_bonus(pdf_text, reg),
                "deductible": "",
                "sum_insured": _extract_sum_insured(section),
                "premium": premium,
            }
        )

    for reg_match in REG_WITH_SPACES_RE.finditer(pdf_text):
        reg_raw = reg_match.group(1)
        reg = reg_raw.replace(" ", "")

        digits = re.sub(r"\D", "", reg)
        if len(digits) == 4 and digits.startswith(("19", "20")):
            continue
        if reg in seen:
            continue

        pos = reg_match.start()
        window = _slice_context(pdf_text, pos, before=500, after=500)
        context_window = _slice_context(pdf_text, pos, before=120, after=120)
        premium = _extract_premium_after_position(pdf_text, reg_match.end())

        found_brand = ""
        found_model = ""
        found_year = ""

        for brand in brands:
            if not re.search(rf"\b{re.escape(brand)}\b", window, re.IGNORECASE):
                continue
            found_brand = brand
            brand_match = re.search(
                rf"\b{re.escape(brand)}\b\s+([A-Za-z0-9\s\-().]+?)(?:\s+20\d{{2}}|\s*\n|$)",
                window,
                re.IGNORECASE,
            )
            if brand_match:
                found_model = brand_match.group(1).strip()
                found_model = re.sub(r"\s+(Reg\.\w+|TFA|\w*rspremie).*$", "", found_model).strip()
            break

        year_match = YEAR_20XX_RE.search(window)
        if year_match:
            found_year = year_match.group(1)

        label_hit = bool(LABEL_RE.search(context_window))
        if not (found_brand or label_hit):
            continue

        make_model = f"{found_brand} {found_model}".strip()
        make_model_year = f"{make_model} {found_year}".strip()

        seen.add(reg)
        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": "bil",
                "make_model_year": make_model_year,
                "coverage": "kasko",
                "leasing": _extract_leasing(window, pdf_text, reg),
                "annual_mileage": _extract_annual_mileage(window),
                "bonus": _extract_bonus(pdf_text, reg),
                "deductible": "",
                "sum_insured": _extract_sum_insured(window),
                "premium": premium,
            }
        )

    return vehicles


def _extract_unregistered_tractors(pdf_text: str) -> list:
    """
    Extract unregistered tractors + MASKINLOSORE.

    Typical overview format:
    "Uregistrert traktor og arb.maskin - Hitachi 300 - 28 346 Uregistrert"
    """
    import streamlit as st

    vehicles: list[dict] = []
    seen_machines: set[str] = set()

    st.write("    DEBUG: Tractors...")

    text_lower = pdf_text.lower()
    found_brands = [b for b in MACHINE_BRANDS if b.lower() in text_lower]
    has_maskinlosore = bool(MASKINLOSORE_RE.search(pdf_text))
    st.write(
        f"    - Brands: {', '.join(found_brands) if found_brands else 'NONE'}"
        f" | maskinlosore: {has_maskinlosore}"
    )

    brands_alt = "|".join(found_brands) if found_brands else "|".join(MACHINE_BRANDS)
    tractor_re = (
        rf"[Uu]registrert\s+traktor\s+og\s+arb\.?maskin\s*-\s*"
        rf"({brands_alt})\s+([\w\s]+?)\s*(?:(20\d{{2}})\s*)?-\s*([0-9][0-9\s\.,]{{2,}})"
    )

    matches = list(re.finditer(tractor_re, pdf_text, re.IGNORECASE))
    st.write(f"    - Tractor regex matches: {len(matches)}")

    for match in matches:
        brand = match.group(1).strip()
        model = match.group(2).strip().rstrip("-").strip()
        year = match.group(3) or ""
        premium = _normalize_digits(match.group(4))

        key = f"{brand}_{model}".lower()
        if key in seen_machines:
            continue
        seen_machines.add(key)

        label = f"{brand} {model} {year}".strip()
        context = _find_best_vehicle_context(pdf_text, f"{brand} {model}", match.start())

        vehicles.append(
            {
                "registration": "Uregistrert",
                "vehicle_type": "traktor",
                "make_model_year": label,
                "coverage": "kasko",
                "leasing": "",
                "annual_mileage": _extract_annual_mileage(context),
                "bonus": "",
                "deductible": "",
                "sum_insured": _extract_sum_insured(context),
                "premium": premium,
            }
        )
        st.write(f"      - Traktor: {label}")

    maskin_matches = list(MASKINLOSORE_RE.finditer(pdf_text))
    st.write(f"    - MASKINLOSORE regex matches: {len(maskin_matches)}")

    for match in maskin_matches:
        if "maskinlosore" in seen_machines:
            continue
        seen_machines.add("maskinlosore")

        window = _slice_context(pdf_text, match.start(), before=150, after=150)
        year_match = re.search(r"\b(20\d{2})\b", window)
        year = year_match.group(1) if year_match else ""
        line_start = pdf_text.rfind("\n", 0, match.start()) + 1
        line_end = pdf_text.find("\n", match.start())
        if line_end == -1:
            line_end = len(pdf_text)
        line_text = pdf_text[line_start:line_end]
        premium = _extract_premium_from_window(line_text) or _extract_premium_from_window(window)

        context = _slice_context(pdf_text, match.start(), before=800, after=1200)
        label = f"MASKINLOSORE {year}".strip()

        vehicles.append(
            {
                "registration": "Uregistrert",
                "vehicle_type": "other",
                "make_model_year": label,
                "coverage": "kasko",
                "leasing": "",
                # Do not infer driving length for maskinlosore from nearby tractor sections.
                "annual_mileage": "",
                "bonus": "",
                "deductible": "",
                "sum_insured": _extract_sum_insured(context),
                "premium": premium,
            }
        )
        st.write(f"      - Ovrig: {label}")

    tractors = len([v for v in vehicles if v["vehicle_type"] == "traktor"])
    other = len([v for v in vehicles if v["vehicle_type"] == "other"])
    st.write(f"    - Result: {tractors} tractors, {other} ovrig")
    return vehicles


def _slice_context(text: str, center: int, before: int, after: int) -> str:
    """Return bounded text context around a position."""
    return text[max(0, center - before) : min(len(text), center + after)]


def _find_best_vehicle_context(full_text: str, vehicle_hint: str, fallback_pos: int) -> str:
    """
    Prefer the detailed vehicle block when it exists.
    This avoids using only the overview line for mileage/sum extraction.
    """
    default_context = _slice_context(full_text, fallback_pos, before=800, after=1200)
    if not vehicle_hint:
        return default_context

    hint_re = re.compile(re.escape(vehicle_hint), re.IGNORECASE)
    candidates: list[tuple[int, str]] = []
    for match in hint_re.finditer(full_text):
        window = _slice_context(full_text, match.start(), before=400, after=2200)
        before_hint = full_text[max(0, match.start() - 500) : match.start()]
        after_hint = full_text[match.end() : min(len(full_text), match.end() + 1400)]
        score = 0
        if re.search(r"Hva\s+er\s+forsikret", before_hint, re.IGNORECASE):
            score += 3
        if re.search(r"F(?:\u00f8|o)rste\s+gang\s+registrert|Ferste\s+gang\s+registrert", after_hint, re.IGNORECASE):
            score += 3
        if re.search(r"Forsikringen\s+dekker", after_hint, re.IGNORECASE):
            score += 2
        if re.search(r"kj[a-z]{0,3}re(?:lengde|tid)\s*(?:inntil|opp\s*til)?\s*[0-9]", after_hint, re.IGNORECASE):
            score += 2
        candidates.append((score, window))

    if not candidates:
        return default_context

    best_score, best_window = max(candidates, key=lambda item: item[0])
    return best_window if best_score > 0 else default_context


def _extract_leasing(section: str, full_text: str, reg: str) -> str:
    """Extract leasing company."""
    if re.search(r"sparebank\s*1", section, re.I):
        return "Sparebank 1"
    if re.search(r"nordea\s*finans", section, re.I):
        return "Nordea Finans"
    if re.search(r"santander", section, re.I):
        return "Santander"
    if re.search(r"dnb\s*finans", section, re.I):
        return "DNB Finans"
    if re.search(r"brage\s*finans", section, re.I):
        return "BRAGE FINANS"

    reg_pattern = rf"{reg}.*?(?:Sparebank 1|Nordea Finans|Santander|DNB Finans|BRAGE FINANS)"
    match = re.search(reg_pattern, full_text, re.I | re.DOTALL)
    if not match:
        return ""

    matched_text = match.group(0)
    if re.search(r"sparebank\s*1", matched_text, re.I):
        return "Sparebank 1"
    if re.search(r"nordea\s*finans", matched_text, re.I):
        return "Nordea Finans"
    if re.search(r"santander", matched_text, re.I):
        return "Santander"
    if re.search(r"dnb\s*finans", matched_text, re.I):
        return "DNB Finans"
    if re.search(r"brage\s*finans", matched_text, re.I):
        return "BRAGE FINANS"
    return ""


def _extract_bonus(full_text: str, reg: str) -> str:
    """Extract bonus percentage."""
    bonus_match = re.search(rf"{reg}:\s*(\d+)%\s*bonus", full_text, re.I)
    if bonus_match:
        return bonus_match.group(1) + "%"
    return ""


def _normalize_digits(value: str) -> str:
    """Return digits only."""
    return re.sub(r"\D", "", value or "").strip()


def _extract_premium_after_position(text: str, start_pos: int) -> str:
    """
    Extract first numeric amount after a known vehicle token (typically row premium).
    """
    if not text:
        return ""
    tail = text[start_pos : min(len(text), start_pos + 100)]
    match = NUMBER_TOKEN_RE.search(tail)
    if not match:
        return ""
    value = _normalize_digits(match.group(1))
    if not value:
        return ""
    # avoid accidental year capture
    if 1900 <= int(value) <= 2100:
        return ""
    return value


def _extract_premium_from_window(text: str) -> str:
    """
    Extract likely premium from a short overview window.
    Chooses the last numeric amount in the window (usually the price in overview rows).
    """
    if not text:
        return ""
    candidates = []
    for hit in NUMBER_TOKEN_RE.findall(text):
        value = _normalize_digits(hit)
        if not value:
            continue
        if 1900 <= int(value) <= 2100:
            continue
        candidates.append(value)
    return candidates[-1] if candidates else ""


def _normalize_ocr_text(text: str) -> str:
    """Normalize common OCR and mojibake artifacts for pattern matching."""
    if not text:
        return ""

    normalized = text
    for src, dst in OCR_TEXT_REPLACEMENTS.items():
        normalized = normalized.replace(src, dst)

    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _extract_sum_insured(text: str) -> str:
    """
    Extract Forsikringssum when explicitly labeled.
    We intentionally do not use generic coverage lines as fallback.
    """
    if not text:
        return ""

    normalized = _normalize_ocr_text(text)
    match = re.search(
        r"forsikringssum(?:\s*\(kr\))?\s*(?:kr)?\s*[:\-]?\s*([0-9]{1,3}(?:[\s\.,]?[0-9]{3})+)",
        normalized,
        re.IGNORECASE,
    )
    if match:
        return _normalize_digits(match.group(1))

    # Table-style fallback:
    # "Hva er forsikret  Forsikringssum  Egenandel" + row values before "Forsikringen dekker".
    header_block = re.search(
        r"hva\s+er\s+forsikret\s+forsikringssum\s+egenandel(.{0,700}?)(?:forsikringen\s+dekker|$)",
        normalized,
        re.IGNORECASE | re.DOTALL,
    )
    if header_block:
        row_text = header_block.group(1)
        for candidate in re.findall(r"\b[0-9]{1,3}(?:[\s\.,][0-9]{3})+\b", row_text):
            value = _normalize_digits(candidate)
            if not value:
                continue
            # Guard against accidental years.
            if 1900 <= int(value) <= 2100:
                continue
            return value
    return ""


def _extract_annual_mileage(text: str) -> str:
    """Extract annual mileage or annual driving time when present."""
    if not text:
        return ""

    normalized = _normalize_ocr_text(text).lower()
    patterns = [
        r"(?:arlig\s+)?(?:kjorelengde|kjoretid)\s*(?:inntil|opp\s*til)?\s*([0-9][0-9\s\.,]{2,})\s*(?:km|kilometer|timer)?",
        r"(?:arlig\s+)?kj[a-z]{0,3}re(?:lengde|tid)\s*(?:inntil|opp\s*til)?\s*([0-9][0-9\s\.,]{2,})\s*(?:km|kilometer|timer)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return _normalize_digits(match.group(1))
    return ""
