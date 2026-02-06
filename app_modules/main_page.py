import streamlit as st

from app_modules.template_loader import load_template
from app_modules.company_data import (
    fetch_company_by_org,
    format_company_data,
    search_brreg_live
)
from app_modules.Sheets.Sammendrag.summery_getter import generate_company_summary
from app_modules.pdf_parser import extract_fields_from_pdf
from app_modules.Sheets.excel_filler import fill_excel
from app_modules.download import download_excel_file


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
    pdf_bytes = st.file_uploader("Upload PDF (optional)", type=["pdf"])
    
    # ---------------------------------------------------------
    # STEP 6: SUMMARY
    # ---------------------------------------------------------
    summary_text = generate_company_summary(company_data)

    # ---------------------------------------------------------
    # STEP 7: PDF FIELDS
    # ---------------------------------------------------------
    pdf_fields = extract_fields_from_pdf(pdf_bytes) if pdf_bytes else {}

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
            preview_len = 6000
            st.text_area(
                "PDF text preview (first 6,000 chars)",
                value=pdf_text[:preview_len],
                height=200
            )

            try:
                from app_modules.Sheets.Fordon.mapping import extract_vehicles_from_pdf
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
    merged_fields.update(company_data)
    merged_fields.update(pdf_fields)
    merged_fields["company_summary"] = summary_text

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
