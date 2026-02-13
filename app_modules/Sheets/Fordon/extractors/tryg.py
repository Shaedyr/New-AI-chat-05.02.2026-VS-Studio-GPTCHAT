# app_modules/Sheets/Fordon/extractors/tryg.py
"""
TRYG FORSIKRING FORMAT EXTRACTOR - ENHANCED VERSION

Tryg PDFs have clean structure but vehicles can appear in different formats:
1. Standard format: Kjennemerke → Registration → Make/Model → Type
2. Overview format: Product name → Registration → Price (less detail)

This extractor tries MULTIPLE patterns to catch all vehicles.
"""

import re
import streamlit as st


COVERAGE_WORDS = [
    "Kasko", "Delkasko", "Ansvar", "Brann", "Tyveri", "Glass", "Redning"
]
COVERAGE_RE = re.compile(r"\b(kasko|delkasko|ansvar|brann|tyveri|glass|redning)\b", re.IGNORECASE)
NUMERIC_FIELDS = {"sum_insured", "deductible", "premium"}


def extract_tryg_vehicles(pdf_text: str) -> list:
    """
    Extract vehicles from Tryg Forsikring PDF.
    Uses multiple patterns to ensure we catch all vehicles.
    """
    
    st.write("    🔍 **DEBUG: Tryg pattern matching...**")
    
    vehicles = []
    seen = set()
    
    # PATTERN 0: Forsikringsbevis / Spesifikasjon format (new)
    vehicles_spec = _extract_specification_format(pdf_text, seen)
    vehicles.extend(vehicles_spec)
    st.write(f"    - Pattern 0 (Specification): {len(vehicles_spec)} vehicles")
    
    # PATTERN 1: Detailed format with "Kjennemerke" label
    vehicles_detailed = _extract_detailed_format(pdf_text, seen)
    vehicles.extend(vehicles_detailed)
    st.write(f"    - Pattern 1 (Kjennemerke): {len(vehicles_detailed)} vehicles")
    
    # PATTERN 2: Overview format "Product name + Registration"
    vehicles_overview = _extract_overview_format(pdf_text, seen)
    vehicles.extend(vehicles_overview)
    st.write(f"    - Pattern 2 (Overview): {len(vehicles_overview)} vehicles")
    
    # PATTERN 3: Section headers (backup pattern)
    vehicles_headers = _extract_from_headers(pdf_text, seen)
    vehicles.extend(vehicles_headers)
    st.write(f"    - Pattern 3 (Headers): {len(vehicles_headers)} vehicles")
    
    st.write(f"    📊 Total Tryg vehicles extracted: {len(vehicles)}")
    
    # Convert to standard format
    standardized = []
    for v in vehicles:
        standardized.append(_standardize_vehicle(v))
    
    return standardized


def _extract_detailed_format(pdf_text: str, seen: set) -> list:
    """
    Extract vehicles using detailed format with explicit "Kjennemerke" label.
    
    Format:
        Kjennemerke
        KR3037
        Fabrikat/årsmodell
        TYSSE TYSSE 2013
        Type:
        Varetilhenger
    """
    vehicles = []
    
    # Find all "Kjennemerke" sections
    pattern = r'Kjennemerke\s*\n\s*([A-Z]{2}\d{4,5})'
    matches = list(re.finditer(pattern, pdf_text, re.IGNORECASE))
    
    for match in matches:
        registration = match.group(1).strip()
        
        if registration in seen:
            continue
        seen.add(registration)
        
        # Extract section around match
        start = max(0, match.start() - 500)
        end = min(len(pdf_text), match.end() + 800)
        section = pdf_text[start:end]
        
        # Extract fields
        make_model_year = ""
        year = ""
        vtype = ""
        sum_insured = ""
        deductible = ""
        premium = ""
        
        # Make/Model/Year
        make_match = re.search(
            r'Fabrikat/(?:årsmodell|arsmodell|Ã¥rsmodell|\?rsmodell)\s*\n\s*([A-Za-zÆØÅæøå0-9\s\-]+?)(?:\n|Type:)',
            section,
            re.IGNORECASE
        )
        if make_match:
            make_model_year = make_match.group(1).strip()
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', make_model_year)
            if year_match:
                year = year_match.group(1)
        
        # Type
        type_match = re.search(
            r'Type:\s*\n\s*([A-Za-zÆØÅæøå\s\-]+?)(?:\n|Forsikringssum)',
            section,
            re.IGNORECASE
        )
        if type_match:
            vtype = type_match.group(1).strip()
        
        # Insurance sum
        sum_match = re.search(
            r'Forsikringssum\s+kr:\s*\n?\s*([\d\s]+)',
            section,
            re.IGNORECASE
        )
        if sum_match:
            sum_insured = sum_match.group(1).strip().replace(' ', '')
        
        # Deductible (from table)
        table_match = re.search(
            r'Kasko\s*\n\s*PAU\d+\s*\n\s*([\d\s]+?)\s*\n\s*([\d\s]+?)\s*\n\s*(\d+)',
            section
        )
        if table_match:
            deductible = table_match.group(2).strip().replace(' ', '')
            premium = table_match.group(3).strip().replace(' ', '')
        
        vehicles.append({
            'registration': registration,
            'make_model_year': make_model_year,
            'year': year,
            'type': vtype,
            'sum_insured': sum_insured,
            'deductible': deductible,
            'premium': premium,
            'source': 'detailed'
        })
    
    return vehicles


def _normalize_key(s: str) -> str:
    """Normalize keys for comparison (handles Norwegian chars and encoding)."""
    if not s:
        return ""
    s = s.strip().lower()
    # Handle common encoding artifacts
    s = s.replace("Ã¥", "a").replace("Ã¸", "o").replace("Ã¦", "ae")
    s = s.replace("å", "a").replace("ø", "o").replace("æ", "ae")
    # Remove non-alphanumerics
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _normalize_number(val: str) -> str:
    """Extract a clean numeric value like '20 000' or '6 000'."""
    if not val:
        return ""
    tmp = val.lower().replace("kr", "").strip()
    # If letters remain (other than 'kr'), treat as invalid
    if re.search(r"[a-zæøå]", tmp):
        return ""
    m = re.search(r"\d{1,3}(?:[ .]\d{3})+|\d{3,6}", tmp)
    if not m:
        return ""
    num = m.group(0).replace(".", " ")
    num = re.sub(r"\s+", " ", num).strip()
    if re.fullmatch(r"0+", num.replace(" ", "")):
        return ""
    return num


def _is_valid_coverage(val: str) -> bool:
    return bool(val) and bool(COVERAGE_RE.search(val))


def _extract_key_values(section: str) -> dict:
    """
    Parse key/value lines inside a section, supporting:
    - "Key: Value" on same line
    - "Key  Value" on same line (no colon)
    - "Key" followed by "Value" on next line
    """
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    out = {}

    # Direct same-line patterns (keeps original characters)
    label_patterns = [
        (r"Kjennemerke", "registration"),
        (r"Registreringsnummer", "registration"),
        (r"Fabrikat/årsmodell/Type", "make_model_year"),
        (r"Fabrikat/arsmodell/Type", "make_model_year"),
        (r"Fabrikat/\?rsmodell/Type", "make_model_year"),
        (r"Fabrikat/årsmodell", "make_model_year"),
        (r"Fabrikat/arsmodell", "make_model_year"),
        (r"Fabrikat/\?rsmodell", "make_model_year"),
        (r"Type", "type"),
        (r"Forsikringssum\s*kr", "sum_insured"),
        (r"Forsikringssum", "sum_insured"),
        (r"Dekning", "coverage"),
        (r"Egenandel", "deductible"),
        (r"Pris", "premium"),
        (r"Årlig kjørelengde", "annual_mileage"),
        (r"Arlig kjorelengde", "annual_mileage"),
        (r"\?rlig kj\?relengde", "annual_mileage"),
        (r"Bonus", "bonus"),
        (r"Leasing", "leasing"),
    ]

    for line in lines:
        for pattern, key in label_patterns:
            m = re.match(rf"^{pattern}\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val:
                    if key in NUMERIC_FIELDS:
                        val = _normalize_number(val)
                        if not val:
                            continue
                    if key == "coverage" and not _is_valid_coverage(val):
                        continue
                    # Avoid header line being treated as a value
                    if key == "coverage" and re.search(r"vilkår|vilkÃ¥r|vilkar|forsikringssum|egenandel|pris", val, re.IGNORECASE):
                        continue
                    out[key] = val

    key_map = {
        "kjennemerke": "registration",
        "registreringsnummer": "registration",
        "fabrikatarsmodell": "make_model_year",
        "fabrikatarsmodelltype": "make_model_year",
        "type": "type",
        "forsikringssumkr": "sum_insured",
        "forsikringssum": "sum_insured",
        "dekning": "coverage",
        "egenandel": "deductible",
        "pris": "premium",
        "arligkjorelengde": "annual_mileage",
        "bonus": "bonus",
        "leasing": "leasing",
    }

    for i, line in enumerate(lines):
        # Inline "Key: Value"
        if ":" in line:
            parts = line.split(":", 1)
            key = _normalize_key(parts[0])
            if key in key_map:
                val = parts[1].strip()
                if val:
                    mapped = key_map[key]
                    if mapped in NUMERIC_FIELDS:
                        val = _normalize_number(val)
                        if not val:
                            continue
                    if mapped == "coverage" and not _is_valid_coverage(val):
                        continue
                    if mapped == "coverage" and re.search(r"vilkår|vilkÃ¥r|vilkar|forsikringssum|egenandel|pris", val, re.IGNORECASE):
                        continue
                    out[mapped] = val
                continue

        key = _normalize_key(line)
        if key in key_map:
            # Next non-empty line is value
            if i + 1 < len(lines):
                val = lines[i + 1].strip()
                if val:
                    mapped = key_map[key]
                    if mapped in NUMERIC_FIELDS:
                        val = _normalize_number(val)
                        if not val:
                            continue
                    if mapped == "coverage" and not _is_valid_coverage(val):
                        continue
                    if mapped == "coverage" and re.search(r"vilkår|vilkÃ¥r|vilkar|forsikringssum|egenandel|pris", val, re.IGNORECASE):
                        continue
                    out[mapped] = val

    return out


def _extract_specification_format(pdf_text: str, seen: set) -> list:
    """
    Extract vehicles from "Forsikringsbevis | Spesifikasjon" sections.

    Typical structure:
      Campingvogn og tilhenger - Vilkår PAU18200
      Kjennemerke: KR3037
      Fabrikat/årsmodell: TYSSE TYSSE 2013
      Type: Varetilhenger
      Forsikringssum kr: 20 000
      Dekning / Vilkår / Forsikringssum / Egenandel / Pris (table)
    """
    vehicles = []

    # Headers that usually denote a vehicle-specific section
    header_re = re.compile(
        r"(?P<header>(?:Motorvogn|Personbil|Varebil|Lastebil|Campingvogn og tilhenger|Tilhenger|Traktor|Moped|Motorsykkel|Snøscooter|Båt)[^\n]*?)\s*-\s*Vilk(?:år|ar|Ã¥r|\?r)\s+[A-Z]{2,4}\d+",
        re.IGNORECASE
    )
    matches = list(re.finditer(header_re, pdf_text))

    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(pdf_text), m.start() + 8000)
        section = pdf_text[start:end]

        # Trim at common section boundaries to avoid leaking numbers from other parts
        tail = section[200:]
        end_mark = re.search(r"(Forsikringsbevis\s*\|\s*Spesifikasjon|Avtalenummer|Side\s+\d+\s+av\s+\d+)", tail, re.IGNORECASE)
        if end_mark:
            section = section[:200 + end_mark.start()]

        # Extract key/value lines
        kv = _extract_key_values(section)

        # Targeted fallbacks for Tryg text variants (handles encoding/spacing)
        if not kv.get("registration"):
            reg_match = re.search(
                r'(?:Kjennemerke|Registreringsnummer)\s*[:\-]?\s*([A-Z]{2}\s?\d{4,5})',
                section,
                re.IGNORECASE
            )
            if reg_match:
                kv["registration"] = reg_match.group(1).replace(" ", "")

        if not kv.get("make_model_year"):
            mm_match = re.search(
                r'Fabrikat[^\n]*(?:årsmodell|arsmodell|Ã¥rsmodell|\?rsmodell)\s*[:\-]?\s*([A-Za-zÆØÅæøå0-9\-\s]{3,80})',
                section,
                re.IGNORECASE
            )
            if mm_match:
                kv["make_model_year"] = mm_match.group(1).strip()
        
        # Fallback: registration followed by make/model/year in same line/window
        if not kv.get("make_model_year") and kv.get("registration"):
            reg = kv["registration"]
            mm_inline = re.search(
                rf'{re.escape(reg)}\s+([A-Za-zÆØÅæøå0-9\-\s]{{3,60}}?)\s+((?:19|20)\d{{2}})',
                section
            )
            if mm_inline:
                kv["make_model_year"] = f"{mm_inline.group(1).strip()} {mm_inline.group(2).strip()}"

        if not kv.get("type"):
            type_match = re.search(
                r'Type\s*[:\-]?\s*([A-Za-zÆØÅæøå\s\-]+)',
                section,
                re.IGNORECASE
            )
            if type_match:
                kv["type"] = type_match.group(1).strip()

        if not kv.get("sum_insured"):
            sum_match = re.search(
                r'Forsikringssum\s*(?:kr)?\s*[:\-]?\s*([\d\s]+)',
                section,
                re.IGNORECASE
            )
            if sum_match:
                kv["sum_insured"] = sum_match.group(1).strip()

        # Registration fallback (if not found via key/value)
        reg = kv.get("registration", "")
        if not reg:
            reg_match = re.search(r"\b([A-Z]{2}\s?\d{4,5})\b", section)
            if reg_match:
                reg = reg_match.group(1).replace(" ", "")

        if not reg:
            continue

        reg = reg.replace(" ", "")
        if reg in seen:
            continue
        seen.add(reg)

        # Extract table fields near the registration (limits noise)
        table_context = section
        reg_pos = section.find(reg)
        # Prefer the "Kjennemerke <reg>" anchor if present
        anchor = re.search(rf'Kjennemerke\s*[:\-]?\s*{re.escape(reg)}', section, re.IGNORECASE)
        if anchor:
            table_context = section[anchor.start(): anchor.start() + 1200]
        elif reg_pos != -1:
            table_context = section[reg_pos: reg_pos + 1200]
        table = _extract_table_fields(table_context)
        if table:
            for k, v in table.items():
                # Prefer table values for numeric/coverage fields
                if k in ("sum_insured", "deductible", "premium", "coverage"):
                    kv[k] = v
                elif not kv.get(k):
                    kv[k] = v

        make_model_year = kv.get("make_model_year", "")
        vtype = kv.get("type", "") or m.group("header")

        vehicles.append({
            "registration": reg,
            "make_model_year": make_model_year,
            "type": vtype,
            "sum_insured": kv.get("sum_insured", ""),
            "coverage": kv.get("coverage", ""),
            "leasing": kv.get("leasing", ""),
            "annual_mileage": kv.get("annual_mileage", ""),
            "bonus": kv.get("bonus", ""),
            "deductible": kv.get("deductible", ""),
            "premium": kv.get("premium", ""),
            "source": "specification"
        })

    return vehicles


def _extract_table_fields(section: str) -> dict:
    """
    Try to parse the coverage row in the specification table.
    Expected patterns like:
      Kasko  PAU18255  20 000  6 000  968
    """
    coverage_words = [
        "Kasko", "Delkasko", "Ansvar", "Brann", "Tyveri", "Glass", "Redning"
    ]
    cov_re = "|".join(coverage_words)

    # Normalize whitespace and reconnect split thousands (e.g., "6\n000" -> "6 000")
    flat = re.sub(r"(\d)\s*[\r\n]+\s*(\d{3})", r"\1 \2", section)
    flat = re.sub(r"\s+", " ", flat)
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]

    def _try_row(text: str) -> dict:
        num_re = r"\d{1,3}(?:\s\d{3})+|\d{3,6}"
        row = re.search(
            rf'({cov_re})\s+(?:[A-Z]{{2,5}}\d+\s+)?({num_re})\s+({num_re})\s+({num_re})',
            text,
            re.IGNORECASE
        )
        if not row:
            return {}
        coverage = row.group(1).strip()
        sum_insured = _normalize_number(row.group(2))
        deductible = _normalize_number(row.group(3))
        premium = _normalize_number(row.group(4))
        if not _is_valid_coverage(coverage):
            return {}
        if not sum_insured or not deductible:
            return {}
        return {
            "coverage": coverage,
            "sum_insured": sum_insured,
            "deductible": deductible,
            "premium": premium,
        }

    # First: try after the table header line (flattened)
    header = re.search(r"Dekning\s+Vilk(?:år|Ã¥r|ar)\s+Forsikringssum\s+Egenandel\s+Pris", flat, re.IGNORECASE)
    if header:
        row_text = flat[header.end(): header.end() + 200]
        found = _try_row(row_text)
        if found:
            return found

    # Second: try after the table header line (line-based)
    for i, line in enumerate(lines):
        if re.search(r"Dekning.*Vilk.*Forsikringssum.*Egenandel.*Pris", line, re.IGNORECASE):
            for j in range(i + 1, min(i + 6, len(lines))):
                combo = " ".join(lines[j:j + 3])
                found = _try_row(combo)
                if found:
                    return found
            break

    # Third: try from the first coverage word
    cov_match = re.search(COVERAGE_RE, flat)
    if cov_match:
        row_text = flat[cov_match.start(): cov_match.start() + 200]
        found = _try_row(row_text)
        if found:
            return found

    # Fallback A: table is split by columns (labels + values on separate lines)
    labels = {
        "dekning": "coverage",
        "forsikringssum": "sum_insured",
        "egenandel": "deductible",
        "pris": "premium",
    }
    found = {}
    for i, line in enumerate(lines):
        key = _normalize_key(line)
        if key in labels:
            # next non-empty line is the value
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j].strip()
                if nxt and _normalize_key(nxt) not in labels:
                    mapped = labels[key]
                    if mapped in NUMERIC_FIELDS:
                        nxt = _normalize_number(nxt)
                        if not nxt:
                            break
                    if mapped == "coverage" and not _is_valid_coverage(nxt):
                        break
                    if mapped == "coverage" and re.search(r"vilkår|vilkÃ¥r|vilkar|forsikringssum|egenandel|pris", nxt, re.IGNORECASE):
                        break
                    found[mapped] = nxt
                    break

    # Attempt to detect coverage word if still missing
    if "coverage" not in found:
        cov = re.search(rf'({cov_re})', section, re.IGNORECASE)
        if cov:
            found["coverage"] = cov.group(1).strip()

    if found.get("coverage") and (found.get("sum_insured") or found.get("deductible") or found.get("premium")):
        return found

    # Fallback B: coverage word + first three numbers after it
    cov = re.search(rf'({cov_re})', flat, re.IGNORECASE)
    if cov:
        tail = flat[cov.end(): cov.end() + 200]
        nums = re.findall(r'\d{1,3}(?:\s\d{3})+|\d{3,6}', tail)
        if len(nums) >= 2:
            sum_insured = _normalize_number(nums[0])
            deductible = _normalize_number(nums[1])
            premium = _normalize_number(nums[2]) if len(nums) >= 3 else ""
            if sum_insured and deductible:
                return {
                    "coverage": cov.group(1).strip(),
                    "sum_insured": sum_insured,
                    "deductible": deductible,
                    "premium": premium,
                }

    return found


def _extract_overview_format(pdf_text: str, seen: set) -> list:
    """
    Extract vehicles from overview section.
    
    Format:
        Campingvogn og tilhenger
        KR3037
        968
    """
    vehicles = []
    
    # Vehicle product patterns
    product_patterns = [
        r'(Motorvogn|Personbil|Varebil|Lastebil)\s*\n\s*([A-Z]{2}\d{4,5})',
        r'(Campingvogn og tilhenger|Tilhenger)\s*\n\s*([A-Z]{2}\d{4,5})',
        r'(Motorsykkel|Moped|Snøscooter)\s*\n\s*([A-Z]{2}\d{4,5})',
        r'(Traktor|Arbeidsmaskiner?)\s*\n\s*([A-Z]{2}\d{4,5})',
    ]
    
    for pattern in product_patterns:
        matches = re.finditer(pattern, pdf_text, re.IGNORECASE)
        
        for match in matches:
            product_type = match.group(1).strip()
            registration = match.group(2).strip()
            
            if registration in seen:
                continue
            seen.add(registration)
            
            # Try to get price (usually follows registration)
            section = pdf_text[match.start():match.end()+200]
            price_match = re.search(r'\n\s*(\d{1,6})\s*\n', section)
            premium = price_match.group(1) if price_match else ""
            
            vehicles.append({
                'registration': registration,
                'make_model_year': '',  # Not available in overview
                'year': '',
                'type': product_type.lower(),
                'sum_insured': '',
                'deductible': '',
                'premium': premium,
                'source': 'overview'
            })
    
    return vehicles


def _extract_from_headers(pdf_text: str, seen: set) -> list:
    """
    Extract from section headers like "Campingvogn og tilhenger - Vilkår PAU18200"
    This is a backup pattern in case the main patterns miss something.
    """
    vehicles = []
    
    # Find sections with Vilkår codes (indicates vehicle insurance)
    header_pattern = r'(Motorvogn|Campingvogn og tilhenger|Tilhenger|Traktor|Moped|Motorsykkel|Snøscooter|Båt|Personbil|Varebil|Lastebil)\s*-\s*Vilk(?:år|ar|Ã¥r|\?r)\s+([A-Z]+\d+)'
    
    matches = re.finditer(header_pattern, pdf_text, re.IGNORECASE)
    
    for match in matches:
        product_type = match.group(1).strip()
        
        # Look for registration numbers in the next 1000 chars
        section = pdf_text[match.end():match.end()+1000]
        
        # Try to find "Kjennemerke" or just registration pattern
        reg_match = re.search(r'Kjennemerke\s*\n\s*([A-Z]{2}\d{4,5})', section, re.IGNORECASE)
        
        if not reg_match:
            # Try direct registration pattern
            reg_match = re.search(r'\b([A-Z]{2}\d{4,5})\b', section)
        
        if reg_match:
            registration = reg_match.group(1).strip()
            
            if registration in seen:
                continue
            seen.add(registration)
            
            vehicles.append({
                'registration': registration,
                'make_model_year': '',
                'year': '',
                'type': product_type.lower(),
                'sum_insured': '',
                'deductible': '',
                'premium': '',
                'source': 'header'
            })
    
    return vehicles


def _standardize_vehicle(vehicle: dict) -> dict:
    """
    Convert Tryg vehicle data to standard format expected by mapping.py
    """
    vtype = vehicle.get('type', '').lower()
    
    # Determine vehicle_type category
    if any(word in vtype for word in ['tilhenger', 'henger', 'campingvogn']):
        vehicle_type = 'trailer'
    elif any(word in vtype for word in ['personbil', 'varebil', 'lastebil', 'motorvogn', 'bil']):
        vehicle_type = 'car'
    elif any(word in vtype for word in ['traktor', 'arbeid', 'redskap']):
        vehicle_type = 'tractor'
    elif any(word in vtype for word in ['moped', 'motorsykkel', 'snøscooter']):
        vehicle_type = 'moped'
    elif 'båt' in vtype:
        vehicle_type = 'boat'
    else:
        vehicle_type = 'other'
    
    return {
        'registration': vehicle.get('registration', ''),
        'make_model_year': vehicle.get('make_model_year', ''),
        'year': vehicle.get('year', ''),
        'vehicle_type': vehicle_type,
        'type': vtype,  # Original type for debugging
        'coverage': vehicle.get('coverage', ''),
        'leasing': vehicle.get('leasing', ''),
        'annual_mileage': vehicle.get('annual_mileage', ''),
        'bonus': vehicle.get('bonus', ''),
        'deductible': vehicle.get('deductible', ''),
        'sum_insured': vehicle.get('sum_insured', ''),
        'premium': vehicle.get('premium', ''),
        'source': vehicle.get('source', ''),  # For debugging
    }


# Helper function for categorization (used by mapping.py)
def categorize_tryg_vehicle(vehicle: dict) -> str:
    """Categorize a Tryg vehicle based on its type field."""
    return vehicle.get('vehicle_type', 'other')
