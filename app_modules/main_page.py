import streamlit as st

from app_modules.template_loader import load_template
from app_modules.company_data import (
    fetch_company_by_org,
    format_company_data,
    search_brreg_live
)
from app_modules.Sheets.Sammendrag.summery_getter import generate_company_summary
from app_modules.insurers.shared.pdf_parser import extract_fields_from_pdf
from app_modules.insurers.shared.excel_filler import fill_excel
from app_modules.download import download_excel_file


@st.cache_data(ttl=3600, show_spinner=False)
def _extract_fields_from_pdf_cached(pdf_bytes: bytes) -> dict:
    """
    Cache PDF field extraction per file content to avoid re-parsing
    the same uploads on every Streamlit rerun.
    """
    return extract_fields_from_pdf(pdf_bytes)


def run():
    st.title("📄 PDF → Excel (BRREG + Manual Entry)")
    st.caption("Fetch company information and update Excel automatically")
    st.divider()

    # =========================================================
    # INITIALIZE SESSION STATE
    # =========================================================
    if "selected_company" not in st.session_state:
        st.session_state.selected_company = None
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "query" not in st.session_state:
        st.session_state.query = ""

    # ---------------------------------------------------------
    # STEP 1: SEARCH BAR + RESULT DROPDOWN
    # ---------------------------------------------------------
    st.subheader("🔍 Find company")

    query = st.text_input(
        "Search for company",
        placeholder="Type at least 2 characters to search",
        key="search_input"
    )

    # If query changed, search again
    if query != st.session_state.query:
        st.session_state.query = query
        if query and len(query) >= 2:
            results = search_brreg_live(query)
            st.session_state.search_results = results if isinstance(results, list) else []
        else:
            st.session_state.search_results = []
        # Clear selected company when searching again
        st.session_state.selected_company = None

    # Build company options
    company_options = [
        f"{c.get('navn', '')} ({c.get('organisasjonsnummer', '')})"
        for c in st.session_state.search_results
    ]

    # Show dropdown only if we have results
    if company_options:
        # Find current selection index
        current_index = None
        if st.session_state.selected_company:
            current_label = f"{st.session_state.selected_company.get('navn', '')} ({st.session_state.selected_company.get('organisasjonsnummer', '')})"
            if current_label in company_options:
                current_index = company_options.index(current_label)
        
        selected_label = st.selectbox(
            "Select company",
            company_options,
            index=current_index,
            placeholder="Select a company",
            key="company_selector"
        )

        # Update selected company when dropdown changes
        if selected_label and selected_label in company_options:
            idx = company_options.index(selected_label)
            st.session_state.selected_company = st.session_state.search_results[idx]

    # Check if we have a selected company
    if not st.session_state.selected_company:
        st.info("Select a company to continue.")
        return

    # ---------------------------------------------------------
    # STEP 2: LOAD TEMPLATE
    # ---------------------------------------------------------
    if "template_bytes" not in st.session_state:
        st.session_state.template_bytes = load_template()

    template_bytes = st.session_state.template_bytes

    # ---------------------------------------------------------
    # STEP 3: FETCH BRREG COMPANY DATA
    # ---------------------------------------------------------
    org_number = st.session_state.selected_company.get("organisasjonsnummer")

    raw_company_data = (
        fetch_company_by_org(org_number)
        if org_number
        else st.session_state.selected_company
    )

    company_data = format_company_data(raw_company_data)

    st.divider()
    
    # ---------------------------------------------------------
    # STEP 4: MANUAL FINANCIAL DATA ENTRY
    # ---------------------------------------------------------
    st.subheader("💰 Financial Data (Optional)")
    
    st.info("""
    **Enter financial data manually** (you can find this on Proff.no)
    
    Leave blank if not needed - the app will work without it!
    """)
    
    # Create 3 columns for 3 years
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**2024**")
        revenue_2024 = st.text_input("Revenue", key="rev_2024", placeholder="e.g., 15000000")
        operating_2024 = st.text_input("Operating Result", key="op_2024", placeholder="e.g., 1500000")
        tax_2024 = st.text_input("Result Before Tax", key="tax_2024", placeholder="e.g., 1200000")
        assets_2024 = st.text_input("Total Assets", key="assets_2024", placeholder="e.g., 8000000")
    
    with col2:
        st.markdown("**2023**")
        revenue_2023 = st.text_input("Revenue", key="rev_2023", placeholder="e.g., 14000000")
        operating_2023 = st.text_input("Operating Result", key="op_2023", placeholder="e.g., 1400000")
        tax_2023 = st.text_input("Result Before Tax", key="tax_2023", placeholder="e.g., 1100000")
        assets_2023 = st.text_input("Total Assets", key="assets_2023", placeholder="e.g., 7500000")
    
    with col3:
        st.markdown("**2022**")
        revenue_2022 = st.text_input("Revenue", key="rev_2022", placeholder="e.g., 13000000")
        operating_2022 = st.text_input("Operating Result", key="op_2022", placeholder="e.g., 1300000")
        tax_2022 = st.text_input("Result Before Tax", key="tax_2022", placeholder="e.g., 1000000")
        assets_2022 = st.text_input("Total Assets", key="assets_2022", placeholder="e.g., 7000000")
    
    # Collect financial data
    financial_data = {}
    if revenue_2024: financial_data["sum_driftsinnt_2024"] = revenue_2024.strip()
    if operating_2024: financial_data["driftsresultat_2024"] = operating_2024.strip()
    if tax_2024: financial_data["ord_res_f_skatt_2024"] = tax_2024.strip()
    if assets_2024: financial_data["sum_eiendeler_2024"] = assets_2024.strip()
    
    if revenue_2023: financial_data["sum_driftsinnt_2023"] = revenue_2023.strip()
    if operating_2023: financial_data["driftsresultat_2023"] = operating_2023.strip()
    if tax_2023: financial_data["ord_res_f_skatt_2023"] = tax_2023.strip()
    if assets_2023: financial_data["sum_eiendeler_2023"] = assets_2023.strip()
    
    if revenue_2022: financial_data["sum_driftsinnt_2022"] = revenue_2022.strip()
    if operating_2022: financial_data["driftsresultat_2022"] = operating_2022.strip()
    if tax_2022: financial_data["ord_res_f_skatt_2022"] = tax_2022.strip()
    if assets_2022: financial_data["sum_eiendeler_2022"] = assets_2022.strip()
    
    # Show status
    if financial_data:
        st.success(f"✅ {len(financial_data)} financial fields entered")
    else:
        st.info("ℹ️ No financial data entered - will use only BRREG company data")
    
    # Merge financial data
    company_data.update(financial_data)

    st.divider()

    # ---------------------------------------------------------
    # STEP 5: PDF UPLOAD
    # ---------------------------------------------------------
    col_pdf, col_provider = st.columns([2, 1])
    with col_pdf:
        pdf_uploads = st.file_uploader(
            "Upload PDF(s) (optional)",
            type=["pdf"],
            accept_multiple_files=True
        )
    with col_provider:
        vehicle_provider = st.selectbox(
            "Vehicle PDF type",
            ["Auto-detect", "Tryg", "Gjensidige", "If", "Ly"],
            index=0,
            help="Select insurer format for vehicle extraction"
        )
    
    # ---------------------------------------------------------
    # STEP 6: SUMMARY
    # ---------------------------------------------------------
    summary_text = generate_company_summary(company_data)

    # ---------------------------------------------------------
    # STEP 7: PDF FIELDS
    # ---------------------------------------------------------
    pdf_fields = {}
    if pdf_uploads:
        combined_pdf_text_parts = []

        for uploaded_pdf in pdf_uploads:
            pdf_bytes = uploaded_pdf.getvalue()
            extracted_fields = _extract_fields_from_pdf_cached(pdf_bytes)
            if not extracted_fields:
                continue

            # Keep all PDF text to support multi-part insurance documents.
            text_part = extracted_fields.get("pdf_text", "")
            if text_part:
                combined_pdf_text_parts.append(text_part)

            # For non-text fields, keep first non-empty value.
            for key, value in extracted_fields.items():
                if key == "pdf_text":
                    continue
                if value and not pdf_fields.get(key):
                    pdf_fields[key] = value

        if combined_pdf_text_parts:
            pdf_fields["pdf_text"] = "\n\n".join(combined_pdf_text_parts)

    # ---------------------------------------------------------
    # DEBUG: VEHICLE EXTRACTION (optional)
    # ---------------------------------------------------------
    debug_vehicles = st.checkbox(
        "Debug vehicle extraction",
        value=False,
        help="Show extracted PDF text snippet and raw vehicle data"
    )

    if debug_vehicles:
        st.divider()
        st.subheader("🔧 Vehicle Extraction Debug")

        pdf_text = pdf_fields.get("pdf_text", "")
        if not pdf_text:
            st.warning("No pdf_text found. Upload a PDF and run again.")
        else:
            st.write(f"PDF text length: {len(pdf_text)} characters")
            preview_start = st.number_input(
                "Preview start (char index)",
                min_value=0,
                max_value=max(len(pdf_text) - 1, 0),
                value=0,
                step=1000
            )
            preview_len = st.number_input(
                "Preview length",
                min_value=500,
                max_value=20000,
                value=6000,
                step=500
            )
            preview_end = min(len(pdf_text), int(preview_start + preview_len))
            st.text_area(
                f"PDF text preview (chars {int(preview_start)}-{preview_end})",
                value=pdf_text[int(preview_start):preview_end],
                height=200
            )

            import re

            keyword = st.text_input(
                "Find keyword in PDF text",
                placeholder="e.g. Kjennemerke, Fabrikat, Type, Tilhenger"
            )
            if keyword:
                matches = [m.start() for m in re.finditer(re.escape(keyword), pdf_text, flags=re.IGNORECASE)]
                st.write(f"Found {len(matches)} matches for '{keyword}'")
                max_hits = st.number_input(
                    "Max matches to show",
                    min_value=1,
                    max_value=20,
                    value=5,
                    step=1
                )
                context = st.number_input(
                    "Context size (chars)",
                    min_value=50,
                    max_value=1000,
                    value=300,
                    step=50
                )
                for i, pos in enumerate(matches[:int(max_hits)]):
                    start = max(0, pos - int(context))
                    end = min(len(pdf_text), pos + int(context))
                    st.text_area(
                        f"Match {i+1} at {pos}",
                        value=pdf_text[start:end],
                        height=120
                    )

            show_regs = st.checkbox("Show registration matches (first 50)", value=False)
            if show_regs:
                regs = set()

                # Strict pattern: KR3037
                strict = set()
                for m in re.finditer(r"\\b[A-Z]{2}\\d{4,5}\\b", pdf_text):
                    strict.add(m.group(0).upper())

                # Normal patterns: KR3037, KR 3037, KR-3037
                normal = set()
                for m in re.finditer(r"\\b[A-Z]{2}\\s*[-]?\\s*\\d{4,5}\\b", pdf_text):
                    reg = re.sub(r"[\\s\\-]+", "", m.group(0)).upper()
                    if re.fullmatch(r"[A-Z]{2}\\d{4,5}", reg):
                        normal.add(reg)

                # OCR-spaced patterns: K R 3 0 3 7 (spaces between chars)
                spaced = set()
                for m in re.finditer(r"([A-Z])\\W*([A-Z])\\W*([0-9])\\W*([0-9])\\W*([0-9])\\W*([0-9])(?:\\W*([0-9]))?", pdf_text, re.IGNORECASE):
                    parts = [p for p in m.groups() if p]
                    reg = "".join(parts).upper()
                    if re.fullmatch(r"[A-Z]{2}\\d{4,5}", reg):
                        spaced.add(reg)

                regs.update(strict)
                regs.update(normal)
                regs.update(spaced)

                unique = sorted(regs)
                st.write(f"Unique registrations found: {len(unique)}")
                st.write(f"  strict: {len(strict)}, normal: {len(normal)}, spaced: {len(spaced)}")
                st.write(unique[:50])

            try:
                from app_modules.insurers.shared.vehicle_mapping import extract_vehicles_from_pdf
                categorized = extract_vehicles_from_pdf(pdf_text)
                if categorized:
                    st.write("Categorized vehicles:")
                    for cat, items in categorized.items():
                        st.write(f"- {cat}: {len(items)}")
                        if items:
                            st.json(items)
                else:
                    st.warning("No vehicles extracted by Fordon parser.")
            except Exception as e:
                st.error(f"Vehicle extraction debug failed: {e}")

    # ---------------------------------------------------------
    # MERGE ALL FIELDS
    # ---------------------------------------------------------
    merged_fields = {}
    # Keep BRREG/manual values as the source of truth for shared company fields.
    # PDF data is merged first so it can still provide sheet-specific fields
    # (e.g. pdf_text for vehicle extraction) without overriding BRREG basics.
    merged_fields.update(pdf_fields)
    merged_fields.update(company_data)
    merged_fields["company_summary"] = summary_text
    merged_fields["vehicle_provider"] = vehicle_provider

    st.divider()
    st.subheader("📋 Data Preview")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Company Info (from BRREG):**")
        st.write("• Company name:", merged_fields.get("company_name", ""))
        st.write("• Organization number:", merged_fields.get("org_number", ""))
        st.write("• Address:", merged_fields.get("address", ""))
        st.write("• Postal code:", merged_fields.get("post_nr", ""))
        st.write("• City:", merged_fields.get("city", ""))
        st.write("• Employees:", merged_fields.get("employees", ""))
        st.write("• NACE code:", merged_fields.get("nace_code", ""))
        st.write("• NACE description:", merged_fields.get("nace_description", ""))

    with col_right:
        st.markdown("**Summary:**")
        st.info(summary_text or "No company description available.")
        
        # Show financial data if entered
        if financial_data:
            st.markdown("**Financial Data (manually entered):**")
            if merged_fields.get("sum_driftsinnt_2024"):
                st.write("• Revenue 2024:", merged_fields.get("sum_driftsinnt_2024"))
            if merged_fields.get("driftsresultat_2024"):
                st.write("• Operating result 2024:", merged_fields.get("driftsresultat_2024"))
            if merged_fields.get("sum_driftsinnt_2023"):
                st.write("• Revenue 2023:", merged_fields.get("sum_driftsinnt_2023"))

    st.divider()

    # ---------------------------------------------------------
    # STEP 8: PROCESS & DOWNLOAD
    # ---------------------------------------------------------
    if st.button("🚀 Process & Update Excel", use_container_width=True):
        with st.spinner("Processing and filling Excel..."):
            excel_bytes = fill_excel(
                template_bytes=template_bytes,
                field_values=merged_fields,
                summary_text=summary_text,
            )

        download_excel_file(
            excel_bytes=excel_bytes,
            company_name=merged_fields.get("company_name", "Company")
        )
