# app_modules/Sheets/Fordon/extractors/gjensidige.py
"""
GJENSIDIGE FORMAT EXTRACTOR

ACTUAL OCR output formats:
--------------------------
CARS:
  VOLKSWAGEN TRANSPORTER 2020 BU 21895
  - Sparebank 1 Sør-Norge ASA

TRACTORS:
  Uregistrert traktor og arb.maskin - Doosan 300 DX 2023 - 24 741 Uregistrert
  Uregistrert traktor og arb.maskin - Hitachi 300 - 28 346 Uregistrert
  (OCR may insert © between entries)

MASKINLØSØRE:
  Maskinløsøre - MASKINLØSØRE 2024 - 62 324 Uregistrert
"""

import re


MACHINE_BRANDS = [
    "Doosan", "Hitachi", "Caterpillar", "Liebherr", "Sennebogen",
    "Komatsu", "Volvo", "JCB", "Bobcat", "Case", "John Deere",
    "New Holland", "Kubota"
]


def extract_gjensidige_vehicles(pdf_text: str) -> list:
    """Extract vehicles from Gjensidige PDF."""
    import streamlit as st

    vehicles = []
    seen_registrations = set()

    # Extract registered cars (UNCHANGED)
    cars = _extract_registered_cars(pdf_text, seen_registrations)
    vehicles.extend(cars)

    # Extract tractors + maskinløsøre
    tractors_and_other = _extract_unregistered_tractors(pdf_text)
    vehicles.extend(tractors_and_other)

    return vehicles


# =============================================================
# REGISTERED CARS - UNCHANGED
# =============================================================
def _extract_registered_cars(pdf_text: str, seen: set) -> list:
    """
    Extract registered cars from TWO formats:
    1. "VOLKSWAGEN TRANSPORTER 2020 BU 21895"
    2. Table rows with registration numbers
    """
    vehicles = []

    brands = [
        "VOLKSWAGEN", "FORD", "TOYOTA", "MERCEDES-BENZ", "MERCEDES", "LAND ROVER",
        "CITROEN", "PEUGEOT", "VOLVO", "BMW", "AUDI", "NISSAN", "RENAULT",
        "OPEL", "FIAT", "IVECO", "MAN", "SCANIA", "SKODA", "HYUNDAI", "KIA",
        "MAZDA", "MITSUBISHI", "SUZUKI", "ISUZU", "TESLA", "POLESTAR", "BYD",
        "MG", "SEAT", "MINI"
    ]

    # FORMAT 1: BRAND + text + YEAR + REG (allow spaced digits)
    brands_pattern = '|'.join(brands)
    reg_token = r'[A-Z]{2}\s*\d(?:\s?\d){3,4}'
    pattern1 = rf'({brands_pattern})\s+([A-Za-z0-9\s\-().]+?)\s+(20\d{{2}})\s+({reg_token})'

    for match in re.finditer(pattern1, pdf_text, re.IGNORECASE):
        make = match.group(1).strip()
        model = match.group(2).strip()
        year = match.group(3).strip()
        reg_with_space = match.group(4).strip()
        reg = re.sub(r"\s+", "", reg_with_space)

        if reg in seen:
            continue
        seen.add(reg)

        pos = match.start()
        section = pdf_text[max(0, pos-200):min(len(pdf_text), pos+500)]

        leasing = _extract_leasing(section, pdf_text, reg)
        bonus = _extract_bonus(pdf_text, reg)

        vehicles.append({
            "registration": reg,
            "vehicle_type": "bil",
            "make_model_year": f"{make} {model} {year}",
            "coverage": "kasko",
            "leasing": leasing,
            "annual_mileage": "",
            "bonus": bonus,
            "deductible": "",
        })

    # FORMAT 2: All registration numbers (table format, allow spaced digits)
    all_regs = re.findall(r'\b([A-Z]{2}\s*\d(?:\s?\d){3,4})\b', pdf_text, re.IGNORECASE)
    label_re = re.compile(
        r'\b(kjennemerke|reg\.?\s*nr|regnr|registreringsnummer)\b',
        re.IGNORECASE,
    )

    for reg_raw in all_regs:
        reg = reg_raw.replace(" ", "")

        # Skip year-like tokens (e.g., KW 2022, SE 2018) from OCR
        digits = re.sub(r"\D", "", reg)
        if len(digits) == 4 and digits.startswith(("19", "20")):
            continue

        if reg in seen:
            continue

        reg_pattern = re.sub(r"\s+", r"\\s?", reg_raw)
        match = re.search(rf'{reg_pattern}', pdf_text, re.IGNORECASE)
        if not match:
            continue

        pos = match.start()
        window = pdf_text[max(0, pos-500):min(len(pdf_text), pos+500)]
        context_window = pdf_text[max(0, pos-120):min(len(pdf_text), pos+120)]

        found_brand = None
        found_model = None
        found_year = None

        window_lower = window.lower()
        for brand in brands:
            brand_re = re.compile(rf'\b{re.escape(brand)}\b', re.IGNORECASE)
            if brand_re.search(window):
                found_brand = brand
                brand_match = re.search(
                    rf'\b{re.escape(brand)}\b\s+([A-Za-z0-9\s\-().]+?)(?:\s+20\d{{2}}|\s*\n|$)',
                    window,
                    re.IGNORECASE,
                )
                if brand_match:
                    found_model = brand_match.group(1).strip()
                    found_model = re.sub(r'\s+(Reg\.år|TFA|Årspremie).*$', '', found_model).strip()
                break

        year_match = re.search(r'\b(20\d{2})\b', window)
        if year_match:
            found_year = year_match.group(1)

        label_hit = bool(label_re.search(context_window))

        if found_brand or label_hit:
            if not found_model:
                found_model = ""
            make_model = f"{found_brand or ''} {found_model}".strip()

            seen.add(reg)
            leasing = _extract_leasing(window, pdf_text, reg)
            bonus = _extract_bonus(pdf_text, reg)

            make_model_year = f"{make_model} {found_year}".strip()
            vehicles.append({
                "registration": reg,
                "vehicle_type": "bil",
                "make_model_year": make_model_year,
                "coverage": "kasko",
                "leasing": leasing,
                "annual_mileage": "",
                "bonus": bonus,
                "deductible": "",
            })

    return vehicles


# =============================================================
# TRACTORS + MASKINLØSØRE - REWRITTEN with correct patterns
# =============================================================
def _extract_unregistered_tractors(pdf_text: str) -> list:
    """
    Actual OCR formats:
      "Uregistrert traktor og arb.maskin - Doosan 300 DX 2023 - 24 741 Uregistrert"
      "Uregistrert traktor og arb.maskin - Hitachi 300 - 28 346 Uregistrert"
      "Maskinløsøre - MASKINLØSØRE 2024 - 62 324 Uregistrert"

    Key: price (24 741) sits between dash and final "Uregistrert".
    We capture brand + model + optional year, then stop at " - ".
    """
    import streamlit as st

    vehicles = []
    seen_machines = set()

    st.write("    🔍 **DEBUG: Tractors...**")

    found_brands = [b for b in MACHINE_BRANDS if b.lower() in pdf_text.lower()]
    has_maskinlosore = 'maskinløsøre' in pdf_text.lower()
    st.write(f"    - Brands: {', '.join(found_brands) if found_brands else 'NONE'} | maskinløsøre: {has_maskinlosore}")

    # ---------------------------------------------------------
    # TRACTORS
    # "Uregistrert traktor og arb.maskin - BRAND MODEL [YEAR] - PRICE Uregistrert"
    # Capture brand, then everything up to next " - "
    # ---------------------------------------------------------
    brands_alt = '|'.join(found_brands) if found_brands else '|'.join(MACHINE_BRANDS)

    tractor_re = rf'[Uu]registrert\s+traktor\s+og\s+arb\.?maskin\s*-\s*({brands_alt})\s+([\w\s]+?)\s*(?:(20\d{{2}})\s*)?-'

    matches = list(re.finditer(tractor_re, pdf_text, re.IGNORECASE))
    st.write(f"    - Tractor regex matches: {len(matches)}")

    for m in matches:
        brand = m.group(1).strip()
        model = m.group(2).strip().rstrip('-').strip()
        year  = m.group(3) or ""

        key = f"{brand}_{model}".lower()
        if key in seen_machines:
            continue
        seen_machines.add(key)

        label = f"{brand} {model} {year}".strip()
        vehicles.append({
            "registration": "Uregistrert",
            "vehicle_type": "traktor",
            "make_model_year": label,
            "coverage": "kasko",
            "leasing": "",
            "annual_mileage": "",
            "bonus": "",
            "deductible": "",
        })
        st.write(f"      ✓ Traktor: {label}")

    # ---------------------------------------------------------
    # MASKINLØSØRE → Øvrig (B76-B84)
    # OCR variants include: Maskinløsøre, Maskinlosore, MASKINL@S@RE
    # ---------------------------------------------------------
    maskin_re = r'maskinl(?:ø|o|0|@)s(?:ø|o|0|@)re'

    matches = list(re.finditer(maskin_re, pdf_text, re.IGNORECASE))
    st.write(f"    - MASKINLØSØRE regex matches: {len(matches)}")

    for m in matches:
        start = max(0, m.start() - 150)
        end = min(len(pdf_text), m.end() + 150)
        window = pdf_text[start:end]
        year_match = re.search(r"\b(20\d{2})\b", window)
        year = year_match.group(1) if year_match else ""

        if "maskinlosore" in seen_machines:
            continue
        seen_machines.add("maskinlosore")

        label = f"MASKINLØSØRE {year}".strip()
        vehicles.append({
            "registration": "Uregistrert",
            "vehicle_type": "other",
            "make_model_year": label,
            "coverage": "kasko",
            "leasing": "",
            "annual_mileage": "",
            "bonus": "",
            "deductible": "",
        })
        st.write(f"      ✓ Øvrig: {label}")

    tractors = len([v for v in vehicles if v["vehicle_type"] == "traktor"])
    other   = len([v for v in vehicles if v["vehicle_type"] == "other"])
    st.write(f"    - **Result: {tractors} tractors, {other} øvrig**")
    return vehicles


# =============================================================
# HELPERS - UNCHANGED
# =============================================================
def _extract_leasing(section: str, full_text: str, reg: str) -> str:
    """Extract leasing company."""
    if re.search(r'sparebank\s*1', section, re.I):
        return "Sparebank 1"
    if re.search(r'nordea\s*finans', section, re.I):
        return "Nordea Finans"
    if re.search(r'santander', section, re.I):
        return "Santander"
    if re.search(r'dnb\s*finans', section, re.I):
        return "DNB Finans"
    if re.search(r'brage\s*finans', section, re.I):
        return "BRAGE FINANS"

    reg_pattern = rf'{reg}.*?(?:Sparebank 1|Nordea Finans|Santander|DNB Finans|BRAGE FINANS)'
    match = re.search(reg_pattern, full_text, re.I | re.DOTALL)

    if match:
        matched_text = match.group(0)
        if re.search(r'sparebank\s*1', matched_text, re.I):
            return "Sparebank 1"
        if re.search(r'nordea\s*finans', matched_text, re.I):
            return "Nordea Finans"
        if re.search(r'santander', matched_text, re.I):
            return "Santander"
        if re.search(r'dnb\s*finans', matched_text, re.I):
            return "DNB Finans"
        if re.search(r'brage\s*finans', matched_text, re.I):
            return "BRAGE FINANS"

    return ""


def _extract_bonus(full_text: str, reg: str) -> str:
    """Extract bonus percentage."""
    bonus_match = re.search(rf'{reg}:\s*(\d+)%\s*bonus', full_text, re.I)
    if bonus_match:
        return bonus_match.group(1) + "%"
    return ""
