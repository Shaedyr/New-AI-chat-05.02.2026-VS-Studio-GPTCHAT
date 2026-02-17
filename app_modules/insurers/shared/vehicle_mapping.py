# app_modules/insurers/shared/vehicle_mapping.py
"""
FORDON SHEET - MAIN ORCHESTRATOR (shared)

This file coordinates all vehicle extractors.
Each insurance company has its own extractor in extractors/
"""

import re
import streamlit as st
from app_modules.Sheets.Fordon.extractors.if_skadeforsikring import extract_if_vehicles
from app_modules.Sheets.Fordon.extractors.gjensidige import extract_gjensidige_vehicles
from app_modules.Sheets.Fordon.extractors.ly import extract_ly_vehicles
from app_modules.Sheets.Fordon.extractors.tryg import extract_tryg_vehicles


VEHICLE_ROWS = {
    "car": {"start": 3, "end": 22, "name": "Cars"},
    "trailer": {"start": 26, "end": 34, "name": "Trailers"},
    "moped": {"start": 38, "end": 46, "name": "Mopeds"},
    "tractor": {"start": 50, "end": 60, "name": "Tractors"},
    "boat": {"start": 64, "end": 72, "name": "Boats"},
    "other": {"start": 76, "end": 84, "name": "Øvrig (Other)"},
}

VEHICLE_COLUMNS = {
    "registration": "B",
    "make_model_year": "C",
    "sum_insured": "D",
    "coverage": "E",
    "leasing": "F",
    "annual_mileage": "G",
    "bonus": "H",
    "deductible": "I",
}

PREMIUM_FONT_COLOR = "0129F6"

NUMERIC_CELL_STYLE = {
    "number_format": "0",
    "align_horizontal": "right",
    "font_bold": False,
}


def _to_excel_number(value):
    """Convert plain numeric strings (e.g. '10 500') to numbers for Excel formulas."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return value

    raw = value.strip().replace(" ", " ")
    if not raw:
        return ""

    # Keep mixed values as text (e.g. "3 000/6 000", "70%", "20 000 km").
    if "/" in raw or "%" in raw:
        return value
    if re.search(r"[^0-9\s.,]", raw):
        return value
    if not re.fullmatch(r"[0-9][0-9\s.,]*", raw):
        return value

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return value

    return int(digits)


def _looks_like_ly_document(pdf_text: str) -> bool:
    text = (pdf_text or "").lower()
    if "ly forsikring" not in text:
        return False
    ly_markers = (
        "firmabil flåte",
        "firmabil flate",
        "tilhenger flåte",
        "tilhenger flate",
        "registreringsnummer ureg",
        "kjøretøy som inngår i gruppen",
        "kjoretoy som inngar i gruppen",
    )
    return any(marker in text for marker in ly_markers)


def extract_vehicles_from_pdf(pdf_text: str, provider: str | None = None) -> dict:
    """
    Main extraction orchestrator.
    Tries all available extractors and combines results.
    """
    
    st.write("🔍 **FORDON: Multi-format extraction**")
    st.info("📝 Supports: If Skadeforsikring, Gjensidige, Ly, Tryg")
    
    if not pdf_text:
        st.error("❌ No PDF text!")
        return {}

    if len(pdf_text) < 1000:
        st.warning("⚠️ PDF text is short; attempting extraction anyway.")
    
    st.write(f"📄 PDF text: {len(pdf_text)} chars")
    provider_norm = (provider or "").strip().lower()
    if provider_norm:
        st.write(f"🔀 Provider selected: {provider_norm}")
    st.write("---")
    
    all_vehicles = []
    run_broad_extractors = True

    # Ly PDFs can be falsely matched by broad extractors (especially Gjensidige fallback).
    # Prioritize Ly-only extraction when the document clearly looks like Ly.
    ly_priority = provider_norm in ("ly", "ly forsikring")
    if not ly_priority and provider_norm in ("", "auto-detect"):
        ly_priority = _looks_like_ly_document(pdf_text)

    if ly_priority:
        st.write("  🔎 **Ly Forsikring (priority)**")
        try:
            ly_vehicles = extract_ly_vehicles(pdf_text)
            if ly_vehicles:
                st.write(f"    ✅ {len(ly_vehicles)} vehicles")
                st.info("Detected Ly format. Skipping broad cross-format extractors to avoid false car matches.")
                all_vehicles.extend(ly_vehicles)
                run_broad_extractors = False
            else:
                st.write("    ⊘ No matches")
        except Exception as e:
            st.write(f"    ❌ Error: {e}")
    
    if run_broad_extractors:
        # Try If Skadeforsikring
        st.write("  🔎 **If Skadeforsikring**")
        try:
            if_vehicles = extract_if_vehicles(pdf_text)
            if if_vehicles:
                st.write(f"    ✅ {len(if_vehicles)} vehicles")
                all_vehicles.extend(if_vehicles)
            else:
                st.write("    ⊘ No matches")
        except Exception as e:
            st.write(f"    ❌ Error: {e}")
        
        # Try Gjensidige
        st.write("  🔎 **Gjensidige**")
        try:
            gjen_vehicles = extract_gjensidige_vehicles(pdf_text)
            if gjen_vehicles:
                st.write(f"    ✅ {len(gjen_vehicles)} vehicles")
                all_vehicles.extend(gjen_vehicles)
            else:
                st.write("    ⊘ No matches")
        except Exception as e:
            st.write(f"    ❌ Error: {e}")
        
        # Try Tryg Forsikring
        st.write("  🔎 **Tryg Forsikring**")
        try:
            tryg_vehicles = extract_tryg_vehicles(pdf_text)
            if tryg_vehicles:
                st.write(f"    ✅ {len(tryg_vehicles)} vehicles")
                all_vehicles.extend(tryg_vehicles)
            else:
                st.write("    ⊘ No matches")
        except Exception as e:
            st.write(f"    ❌ Error: {e}")

        # Try Ly Forsikring
        st.write("  🔎 **Ly Forsikring**")
        try:
            ly_vehicles = extract_ly_vehicles(pdf_text)
            if ly_vehicles:
                st.write(f"    ✅ {len(ly_vehicles)} vehicles")
                all_vehicles.extend(ly_vehicles)
            else:
                st.write("    ⊘ No matches")
        except Exception as e:
            st.write(f"    ❌ Error: {e}")
    
    if not all_vehicles:
        st.error("❌ No vehicles found!")
        st.warning("💡 Need a new insurance company? Add an extractor in extractors/")
        return {}
    
    # Remove duplicates:
    # - Registered vehicles: key on registration only (first occurrence wins, it's the most complete)
    # - Unregistered (tractors etc): key on reg + make_model_year (they all share "Uregistrert")
    unique = {}
    for v in all_vehicles:
        if v['registration'].lower() == 'uregistrert':
            key = f"{v['registration']}_{v['make_model_year']}"
        else:
            key = v['registration']
        if key not in unique:
            unique[key] = v
    
    all_vehicles = list(unique.values())
    
    # Categorize
    categorized = _categorize_vehicles(all_vehicles)
    
    # Display summary
    st.write("---")
    st.write("📦 **Categorized:**")
    for cat, vehs in categorized.items():
        if vehs:
            name = VEHICLE_ROWS[cat]['name']
            st.write(f"  🚗 **{name}**: {len(vehs)}")
            
            for v in vehs[:3]:
                extras = []
                if v.get('leasing'):
                    extras.append(f"Leasing: {v['leasing']}")
                if v.get('bonus'):
                    extras.append(f"Bonus: {v['bonus']}")
                if v.get('annual_mileage'):
                    extras.append(f"{v['annual_mileage']} km")
                
                extra_str = f" | {' | '.join(extras)}" if extras else ""
                st.write(f"    - {v['registration']} - {v['make_model_year']}{extra_str}")
            
            if len(vehs) > 3:
                st.write(f"    ... +{len(vehs)-3} more")
    
    total = sum(len(v) for v in categorized.values())
    st.success(f"✅ **TOTAL: {total} vehicles extracted**")
    
    return categorized


def _categorize_vehicles(vehicles: list) -> dict:
    """Categorize vehicles by type."""
    categorized = {
        "car": [],
        "trailer": [],
        "moped": [],
        "tractor": [],
        "boat": [],
        "other": [],
    }
    
    for v in vehicles:
        vtype = v.get("vehicle_type", "").lower()
        reg = v.get("registration", "").lower()
        
        # Check explicit vehicle_type first
        if vtype == "other":
            cat = "other"
        elif vtype == "trailer":
            cat = "trailer"
        elif vtype == "tractor":
            cat = "tractor"
        elif vtype == "boat":
            cat = "boat"
        elif vtype == "car":
            cat = "car"
        elif "tilhenger" in vtype or "henger" in vtype:
            cat = "trailer"
        elif "moped" in vtype:
            cat = "moped"
        elif "traktor" in vtype:
            cat = "tractor"
        elif "båt" in vtype:
            cat = "boat"
        elif "bil" in vtype or "varebil" in vtype or "personbil" in vtype:
            cat = "car"
        # Fallback: check registration for "uregistrert" → tractor
        elif "uregistrert" in reg:
            cat = "tractor"
        else:
            # Unknown goes to "other"
            cat = "other"
        
        categorized[cat].append(v)
    
    return categorized


def transform_data(extracted: dict) -> dict:
    """Transform extracted vehicle data to Excel cell mappings."""
    
    st.write("🔄 **FORDON: transform_data**")
    st.info("✅ Fields: Leasing, Årlig kjørelengde, Bonus, Egenandel")
    
    out = {}
    cell_styles = {}
    pdf_text = extracted.get("pdf_text", "")
    
    if not pdf_text:
        st.error("❌ No pdf_text!")
        return out
    
    provider = (extracted.get("vehicle_provider") or "").strip().lower()
    if provider in ("tryg", "gjensidige", "if", "if skadeforsikring", "ly", "ly forsikring"):
        st.write(f"🔀 Provider override: {provider}")
        if provider in ("if", "if skadeforsikring"):
            vehicles = extract_if_vehicles(pdf_text)
        elif provider == "gjensidige":
            vehicles = extract_gjensidige_vehicles(pdf_text)
        elif provider in ("ly", "ly forsikring"):
            vehicles = extract_ly_vehicles(pdf_text)
        else:
            vehicles = extract_tryg_vehicles(pdf_text)
        categorized = _categorize_vehicles(vehicles)
    else:
        categorized = extract_vehicles_from_pdf(pdf_text)
    
    if not categorized:
        st.warning("⚠️ No vehicles extracted")
        return out
    
    st.write("---")
    st.write("📋 **Mapping to Excel:**")
    
    total = 0
    
    for cat, vehicles in categorized.items():
        if not vehicles:
            continue
        
        config = VEHICLE_ROWS[cat]
        start, end, name = config["start"], config["end"], config["name"]
        
        st.write(f"  📌 **{name}**: Rows {start}-{end}")
        
        for idx, vehicle in enumerate(vehicles):
            row = start + idx
            
            if row > end:
                st.warning(f"  ⚠️ Too many {name}!")
                break
            
            for field, column in VEHICLE_COLUMNS.items():
                cell_ref = f"{column}{row}"
                if field == "sum_insured":
                    sum_insured = vehicle.get("sum_insured", "")
                    premium = vehicle.get("premium", "")
                    if sum_insured:
                        out[cell_ref] = _to_excel_number(sum_insured)
                        if out[cell_ref] != "":
                            cell_styles[cell_ref] = dict(NUMERIC_CELL_STYLE)
                    elif premium:
                        out[cell_ref] = _to_excel_number(premium)
                        style = dict(NUMERIC_CELL_STYLE)
                        style["font_color"] = PREMIUM_FONT_COLOR
                        cell_styles[cell_ref] = style
                    else:
                        out[cell_ref] = ""
                    continue

                value = vehicle.get(field, "")
                if field in {"annual_mileage", "deductible"}:
                    value = _to_excel_number(value)
                    if value != "":
                        cell_styles[cell_ref] = dict(NUMERIC_CELL_STYLE)
                out[cell_ref] = value
            
            details = f"{vehicle['registration']} - {vehicle['make_model_year']}"
            if vehicle.get('leasing'):
                details += f" | Leasing: {vehicle['leasing']}"
            if vehicle.get('annual_mileage'):
                details += f" | {vehicle['annual_mileage']} km"
            if vehicle.get('bonus'):
                details += f" | Bonus: {vehicle['bonus']}"
            if vehicle.get('deductible'):
                details += f" | Egenandel: {vehicle['deductible']}"
            if (not vehicle.get('sum_insured')) and vehicle.get('premium'):
                details += f" | Premium(D): {vehicle['premium']}"
            
            st.write(f"    Row {row}: {details}")
            total += 1
    
    if cell_styles:
        out["_cell_styles"] = cell_styles

    st.success(f"✅ Mapped {total} vehicles to Excel")
    
    return out


CELL_MAP = {}
