from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Alignment, Color
from io import BytesIO
from copy import copy
from app_modules.insurers.shared.sheet_config import SHEET_MAPPINGS, transform_for_sheet
import streamlit as st

HEADLINE_COLORS = ["FF0BD7B5", "0BD7B5"]


def fill_excel(template_bytes, field_values, summary_text):
    """
    Fill Excel template with data from field_values.
    
    Args:
        template_bytes: Excel template file as bytes
        field_values: Dictionary of field values to fill
        summary_text: Company summary text
        
    Returns:
        Filled Excel file as bytes
    """
    # Keep partial rich-text formatting in template header cells
    # (e.g., "Forsikringssum (kr) / Premium" where only "Premium" is blue).
    try:
        wb = load_workbook(filename=BytesIO(template_bytes), rich_text=True)
    except TypeError:
        # Fallback for environments where rich_text is not supported.
        wb = load_workbook(filename=BytesIO(template_bytes))

    # DEBUG: Show what data we received
    st.write("🔍 **EXCEL_FILLER DEBUG:**")
    st.write(f"📦 field_values keys: {list(field_values.keys())}")
    if "pdf_text" in field_values:
        st.success(f"✅ pdf_text EXISTS in field_values! Length: {len(field_values['pdf_text'])} chars")
    else:
        st.error("❌ pdf_text NOT in field_values!")
        st.write("Available keys:", list(field_values.keys()))

    # Process each sheet that has a mapping configured
    for sheet_name in SHEET_MAPPINGS.keys():
        if sheet_name not in wb.sheetnames:
            st.warning(f"⚠️ Sheet '{sheet_name}' not found in Excel template")
            continue

        ws = wb[sheet_name]
        
        st.write(f"📄 Processing sheet: {sheet_name}")
        
        # Transform data for this specific sheet
        transformed_data = transform_for_sheet(sheet_name, field_values)
        
        st.write(f"  ✓ Transformed data has {len(transformed_data)} fields")

        # Check if this sheet uses static mapping or dynamic mapping
        cell_map = SHEET_MAPPINGS.get(sheet_name, {})
        
        if cell_map:
            # STATIC MAPPING (like Sammendrag)
            # Uses predefined field_name -> cell_ref mapping
            st.write(f"  📌 Using static mapping ({len(cell_map)} mappings)")
            
            for field_key, cell_ref in cell_map.items():
                value = transformed_data.get(field_key, "")

                cell = ws[cell_ref]

                # Skip cells with headline colors (headers)
                fill = cell.fill
                if (
                    fill and isinstance(fill, PatternFill)
                    and fill.fgColor and fill.fgColor.rgb
                    and fill.fgColor.rgb.upper() in HEADLINE_COLORS
                ):
                    continue

                cell.value = value
                
        else:
            # DYNAMIC MAPPING (like Fordon)
            # transform_data() returns cell_ref -> value directly
            st.write(f"  📌 Using dynamic mapping ({len(transformed_data)} cells)")

            cell_styles = {}
            if isinstance(transformed_data, dict):
                raw_styles = transformed_data.pop("_cell_styles", {})
                if isinstance(raw_styles, dict):
                    cell_styles = raw_styles
            
            for cell_ref, value in transformed_data.items():
                # cell_ref is like "B3", "C3", etc.
                if isinstance(cell_ref, str) and len(cell_ref) >= 2:
                    try:
                        cell = ws[cell_ref]
                        
                        # Skip cells with headline colors (headers)
                        fill = cell.fill
                        if (
                            fill and isinstance(fill, PatternFill)
                            and fill.fgColor and fill.fgColor.rgb
                            and fill.fgColor.rgb.upper() in HEADLINE_COLORS
                        ):
                            continue
                        
                        cell.value = value

                        style_cfg = cell_styles.get(cell_ref, {})
                        font_color = style_cfg.get("font_color")
                        font_bold = style_cfg.get("font_bold")
                        if font_color or font_bold is not None:
                            new_font = copy(cell.font)
                            if font_color:
                                rgb = str(font_color).replace("#", "").upper()
                                if len(rgb) == 6:
                                    rgb = f"FF{rgb}"
                                new_font.color = Color(rgb=rgb)
                            if font_bold is not None:
                                new_font.bold = bool(font_bold)
                            cell.font = new_font

                        number_format = style_cfg.get("number_format")
                        if number_format:
                            cell.number_format = str(number_format)

                        align_horizontal = style_cfg.get("align_horizontal")
                        if align_horizontal:
                            new_alignment = copy(cell.alignment)
                            new_alignment.horizontal = str(align_horizontal)
                            cell.alignment = new_alignment

                        st.write(f"    ✓ Filled {cell_ref}: {str(value)[:50]}")
                    except Exception as e:
                        st.error(f"    ❌ Error filling {cell_ref}: {e}")

    # Handle summary text placement in first sheet
    first_sheet = wb.sheetnames[0]
    ws_first = wb[first_sheet]

    if summary_text:
        st.write(f"📝 Placing summary text in {first_sheet}")
        placed = False
        for row in ws_first.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "skriv her" in cell.value.lower():
                    cell.value = summary_text
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    placed = True
                    st.success(f"  ✓ Summary placed in cell {cell.coordinate}")
                    break
            if placed:
                break

        if not placed:
            ws_first["A46"] = summary_text
            ws_first["A46"].alignment = Alignment(wrap_text=True, vertical="top")
            st.info(f"  ℹ️ Summary placed in default cell A46")

    # Save and return
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    
    st.success("✅ Excel file filled successfully!")
    
    return out.getvalue()


def run():
    """Streamlit page view for the excel filler module"""
    st.title("📊 Excel Filler Module")
    st.write("This module fills Excel templates with extracted data.")
    st.info("Used by the main page to create filled Excel files.")
