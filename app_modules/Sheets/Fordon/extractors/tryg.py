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


def extract_tryg_vehicles(pdf_text: str) -> list:
    """
    Extract vehicles from Tryg Forsikring PDF.
    Uses multiple patterns to ensure we catch all vehicles.
    """
    
    st.write("    🔍 **DEBUG: Tryg pattern matching...**")
    
    vehicles = []
    seen = set()
    
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
            r'Fabrikat/årsmodell\s*\n\s*([A-Za-zÆØÅæøå0-9\s\-]+?)(?:\n|Type:)',
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
    header_pattern = r'(Motorvogn|Campingvogn og tilhenger|Tilhenger|Traktor|Moped|Motorsykkel|Snøscooter|Båt|Personbil|Varebil|Lastebil)\s*-\s*Vilkår\s+([A-Z]+\d+)'
    
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
        'coverage': '',  # Not extracted from Tryg PDFs
        'leasing': '',
        'annual_mileage': '',
        'bonus': '',
        'deductible': vehicle.get('deductible', ''),
        'sum_insured': vehicle.get('sum_insured', ''),
        'premium': vehicle.get('premium', ''),
        'source': vehicle.get('source', ''),  # For debugging
    }


# Helper function for categorization (used by mapping.py)
def categorize_tryg_vehicle(vehicle: dict) -> str:
    """Categorize a Tryg vehicle based on its type field."""
    return vehicle.get('vehicle_type', 'other')
