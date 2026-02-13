import re


def extract_if_vehicles(pdf_text: str) -> list:
    """Extract vehicles from If Skadeforsikring PDF text."""
    import streamlit as st

    vehicles = []
    seen = set()

    st.write("    DEBUG: If pattern matching...")

    # Anchor that exists in detail sections
    anchor_re = r"Registreringsnummer:\s*([A-Z]{2}\d{5})"
    anchors = list(re.finditer(anchor_re, pdf_text))
    st.write(f"    - Registreringsnummer anchors found: {len(anchors)}")

    for anchor in anchors:
        reg = anchor.group(1)
        if reg in seen:
            continue
        seen.add(reg)

        start = max(0, anchor.start() - 200)
        section = pdf_text[start : anchor.end() + 600]
        after = pdf_text[anchor.end() : anchor.end() + 600]

        # Example: "PR59518, Varebil, FORD TRANSIT CONNECT"
        make_match = re.search(
            rf"{reg}\s*,\s*(Varebil|Personbil|Lastebil|Moped|Traktor|Bat|Baat|Tilhenger)\s*,\s*([A-Za-z0-9\s\-.]+?)(?:\s+Pris|\s+\d|\s*\n)",
            section,
            re.IGNORECASE,
        )
        if not make_match:
            continue

        vtype = make_match.group(1).strip().lower()
        make = make_match.group(2).strip()

        year = _extract_year(after)
        mileage = _extract_mileage(after)
        deductible = _extract_deductible(after)
        leasing = _extract_leasing(after)

        type_map = {
            "varebil": "bil",
            "personbil": "bil",
            "lastebil": "bil",
            "tilhenger": "trailer",
            "moped": "moped",
            "traktor": "traktor",
            "bat": "boat",
            "baat": "boat",
        }

        vehicles.append(
            {
                "registration": reg,
                "vehicle_type": type_map.get(vtype, "bil"),
                "make_model_year": f"{make} {year}".strip(),
                "coverage": "kasko",
                "leasing": leasing,
                "annual_mileage": mileage,
                "bonus": "",
                "deductible": deductible,
            }
        )
        st.write(
            f"      - {reg} - {make} {year} | {mileage} km | egenandel: {deductible} | {leasing}"
        )

    st.write(f"    - Total: {len(vehicles)} vehicles")
    return vehicles


def _extract_year(text: str) -> str:
    # Accept normal, ASCII and OCR-damaged labels.
    m = re.search(r"(?:Arsmodell|Aarsmodell|\?rsmodell)\s*:\s*(\d{4})", text, re.IGNORECASE)
    return m.group(1) if m else ""


def _extract_mileage(text: str) -> str:
    m = re.search(
        r"(?:Kjorelengde|Kj\?relengde)\s*:\s*([\d\s]+?)\s*km",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _extract_deductible(text: str) -> str:
    m = re.search(
        r"Egenandel\s*-\s*Skader\s+p(?:a|\?)\s+eget\s+kj(?:oretoy|\?ret\?y)\s*:\s*([\d\s]+?)\s*kr",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _extract_leasing(text: str) -> str:
    known = [
        "Sparebank 1",
        "Nordea Finans",
        "Santander",
        "DNB Finans",
        "BRAGE FINANS",
        "Handelsbanken",
        "BN Bank",
    ]
    for company in known:
        if company in text:
            return company
    if re.search(r"Tredjemannsinteresse/leasing", text, re.IGNORECASE):
        return "Leasing"
    return ""
