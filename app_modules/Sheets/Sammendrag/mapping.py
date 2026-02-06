# app_modules/Sheets/Sammendrag/mapping.py
"""
Mapping configuration for the Sammendrag (Summary) sheet.
Includes BRREG basic data + Proff.no financial data in multiple locations
"""

# Cell mapping: field_name -> Excel cell reference
CELL_MAP = {
    # B2 - Megler (Broker) - NOT filled
    
    # BRREG Basic Company Info (B3-B11)
    "company_name": "B3",
    "org_number": "B4",
    "address": "B5",
    "post_nr": "B6",
    "city": "B7",
    "employees": "B8",
    "nace_code": "B9",
    "nace_description": "B10",
    # B11 - homepage removed (not needed)
    
    # Proff.no Financial data - First location (D3-F6)
    "sum_driftsinnt_2024": "D3",
    "sum_driftsinnt_2023": "E3",
    "sum_driftsinnt_2022": "F3",
    "driftsresultat_2024": "D4",
    "driftsresultat_2023": "E4",
    "driftsresultat_2022": "F4",
    "ord_res_f_skatt_2024": "D5",
    "ord_res_f_skatt_2023": "E5",
    "ord_res_f_skatt_2022": "F5",
    "sum_eiendeler_2024": "D6",
    "sum_eiendeler_2023": "E6",
    "sum_eiendeler_2022": "F6",
    
    # Proff.no Financial data - Second location (E11-G14)
    # Same data as above, just in different cells
    "sum_driftsinnt_2024_alt": "E11",
    "sum_driftsinnt_2023_alt": "F11",
    "sum_driftsinnt_2022_alt": "G11",
    "driftsresultat_2024_alt": "E12",
    "driftsresultat_2023_alt": "F12",
    "driftsresultat_2022_alt": "G12",
    "ord_res_f_skatt_2024_alt": "E13",
    "ord_res_f_skatt_2023_alt": "F13",
    "ord_res_f_skatt_2022_alt": "G13",
    "sum_eiendeler_2024_alt": "E14",
    "sum_eiendeler_2023_alt": "F14",
    "sum_eiendeler_2022_alt": "G14",
}


def transform_data(extracted: dict) -> dict:
    """
    Transform raw extracted data into the format expected by the Sammendrag sheet.
    
    Args:
        extracted: Raw data dictionary from various sources (BRREG, PDF, Proff.no)
        
    Returns:
        Transformed dictionary with standardized field names
    """
    out = {}
    
    # BRREG Basic Company Info
    out["company_name"] = extracted.get("company_name") or extracted.get("name") or ""
    out["org_number"] = extracted.get("org_number") or extracted.get("org_no") or ""
    out["address"] = extracted.get("address") or ""
    out["post_nr"] = extracted.get("post_nr") or ""
    out["city"] = extracted.get("city") or ""
    out["employees"] = extracted.get("employees") or ""
    out["nace_code"] = extracted.get("nace_code") or ""
    out["nace_description"] = extracted.get("nace_description") or ""
    # Homepage removed - not needed
    
    # Proff.no Financial data
    # First location (D3-F6)
    for key in ("sum_driftsinnt", "driftsresultat", "ord_res_f_skatt", "sum_eiendeler"):
        for year in ("2024", "2023", "2022"):
            field_name = f"{key}_{year}"
            out[field_name] = extracted.get(field_name, "")
    
    # Second location (E11-G14) - same data, different cells
    for key in ("sum_driftsinnt", "driftsresultat", "ord_res_f_skatt", "sum_eiendeler"):
        for year in ("2024", "2023", "2022"):
            field_name = f"{key}_{year}"
            alt_field_name = f"{key}_{year}_alt"
            # Copy the same value to the _alt field
            out[alt_field_name] = extracted.get(field_name, "")
    
    return out