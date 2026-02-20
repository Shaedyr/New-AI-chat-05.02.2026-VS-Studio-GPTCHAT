import streamlit as st
from contextlib import contextmanager

from app_modules.template_loader import load_template
from app_modules.company_data import (
    fetch_company_by_org,
    format_company_data,
    search_brreg_live,
)
from app_modules.Sheets.Sammendrag.summery_getter import generate_company_summary
from app_modules.insurers.shared.pdf_parser import extract_fields_from_pdf
from app_modules.insurers.shared.excel_filler import fill_excel
from app_modules.download import download_excel_file


@st.cache_data(ttl=3600, show_spinner=False)
def _extract_fields_from_pdf_cached(pdf_bytes: bytes, provider_hint: str) -> dict:
    """
    Cache PDF field extraction per file content to avoid re-parsing
    the same uploads on every Streamlit rerun.
    """
    return extract_fields_from_pdf(pdf_bytes, provider_hint=provider_hint)


@contextmanager
def _suppress_streamlit_messages():
    """
    Hide noisy debug output from lower-level modules while processing.
    This keeps the UI clean in production mode.
    """
    funcs = ("write", "info", "warning", "success", "error", "code")
    originals = {name: getattr(st, name) for name in funcs if hasattr(st, name)}
    try:
        for name in originals:
            setattr(st, name, lambda *args, **kwargs: None)
        yield
    finally:
        for name, original in originals.items():
            setattr(st, name, original)


def _collect_pdf_fields(pdf_uploads, provider_hint: str, progress=None, start_pct=10, end_pct=45) -> dict:
    """Extract and merge fields from uploaded PDFs."""
    pdf_fields = {}
    if not pdf_uploads:
        return pdf_fields

    combined_pdf_text_parts = []
    total = len(pdf_uploads)

    for idx, uploaded_pdf in enumerate(pdf_uploads, start=1):
        if progress:
            pct = start_pct + int((idx / total) * (end_pct - start_pct))
            progress.progress(pct, text=f"Reading PDF {idx}/{total}...")

        pdf_bytes = uploaded_pdf.getvalue()
        with _suppress_streamlit_messages():
            extracted_fields = _extract_fields_from_pdf_cached(pdf_bytes, provider_hint)

        if not extracted_fields:
            continue

        text_part = extracted_fields.get("pdf_text", "")
        if text_part:
            combined_pdf_text_parts.append(text_part)

        for key, value in extracted_fields.items():
            if key == "pdf_text":
                continue
            if value and not pdf_fields.get(key):
                pdf_fields[key] = value

    if combined_pdf_text_parts:
        pdf_fields["pdf_text"] = "\n\n".join(combined_pdf_text_parts)

    return pdf_fields


def run():
    st.title("PDF -> Excel (BRREG + Manual Entry)")
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
    st.subheader("Find company")

    query = st.text_input(
        "Search for company",
        placeholder="Type at least 2 characters to search",
        key="search_input",
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
            current_label = (
                f"{st.session_state.selected_company.get('navn', '')} "
                f"({st.session_state.selected_company.get('organisasjonsnummer', '')})"
            )
            if current_label in company_options:
                current_index = company_options.index(current_label)

        selected_label = st.selectbox(
            "Select company",
            company_options,
            index=current_index,
            placeholder="Select a company",
            key="company_selector",
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
    st.subheader("Financial Data (Optional)")

    st.info(
        """
    Enter financial data manually (you can find this on Proff.no)

    Leave blank if not needed - the app will work without it.
    """
    )

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
    if revenue_2024:
        financial_data["sum_driftsinnt_2024"] = revenue_2024.strip()
    if operating_2024:
        financial_data["driftsresultat_2024"] = operating_2024.strip()
    if tax_2024:
        financial_data["ord_res_f_skatt_2024"] = tax_2024.strip()
    if assets_2024:
        financial_data["sum_eiendeler_2024"] = assets_2024.strip()

    if revenue_2023:
        financial_data["sum_driftsinnt_2023"] = revenue_2023.strip()
    if operating_2023:
        financial_data["driftsresultat_2023"] = operating_2023.strip()
    if tax_2023:
        financial_data["ord_res_f_skatt_2023"] = tax_2023.strip()
    if assets_2023:
        financial_data["sum_eiendeler_2023"] = assets_2023.strip()

    if revenue_2022:
        financial_data["sum_driftsinnt_2022"] = revenue_2022.strip()
    if operating_2022:
        financial_data["driftsresultat_2022"] = operating_2022.strip()
    if tax_2022:
        financial_data["ord_res_f_skatt_2022"] = tax_2022.strip()
    if assets_2022:
        financial_data["sum_eiendeler_2022"] = assets_2022.strip()

    if financial_data:
        st.success(f"{len(financial_data)} financial fields entered")
    else:
        st.info("No financial data entered - will use only BRREG company data")

    company_data.update(financial_data)

    st.divider()

    # ---------------------------------------------------------
    # STEP 5: PDF UPLOAD
    # ---------------------------------------------------------
    col_pdf, col_provider = st.columns([2, 1])
    with col_pdf:
        pdf_uploads = st.file_uploader(
            "Upload PDF(s)",
            type=["pdf"],
            accept_multiple_files=True,
        )
    with col_provider:
        vehicle_provider = st.selectbox(
            "Insurance type",
            ["Select insurance type", "Tryg", "Gjensidige", "If", "Ly"],
            index=0,
            help="Select insurer format for vehicle extraction",
        )

    # ---------------------------------------------------------
    # STEP 6: SUMMARY
    # ---------------------------------------------------------
    summary_text = generate_company_summary(company_data)

    # ---------------------------------------------------------
    # STEP 7: PROCESS & DOWNLOAD
    # ---------------------------------------------------------
    if st.button("Process & Update Excel", use_container_width=True):
        if vehicle_provider == "Select insurance type":
            st.warning("Select insurance type before processing.")
            return

        progress = st.progress(0, text="Starting process...")
        try:
            progress.progress(10, text="Preparing inputs...")

            pdf_fields = _collect_pdf_fields(
                pdf_uploads=pdf_uploads,
                provider_hint=vehicle_provider,
                progress=progress,
                start_pct=15,
                end_pct=45,
            )

            progress.progress(55, text="Merging data...")
            merged_fields = {}
            merged_fields.update(pdf_fields)
            merged_fields.update(company_data)
            merged_fields["company_summary"] = summary_text
            merged_fields["vehicle_provider"] = vehicle_provider

            progress.progress(70, text="Generating Excel file...")
            with _suppress_streamlit_messages():
                excel_bytes = fill_excel(
                    template_bytes=template_bytes,
                    field_values=merged_fields,
                    summary_text=summary_text,
                )

            progress.progress(95, text="Finalizing...")
            download_excel_file(
                excel_bytes=excel_bytes,
                company_name=merged_fields.get("company_name", "Company"),
            )

            progress.progress(100, text="Done")
        except Exception as e:
            progress.empty()
            st.error(f"Processing failed: {e}")
