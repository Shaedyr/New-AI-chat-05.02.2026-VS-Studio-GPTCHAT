import streamlit as st
from contextlib import contextmanager
from datetime import datetime
import json
from io import BytesIO
import zipfile

from app_modules.app_mode import is_production_mode
from app_modules.template_loader import load_template, refresh_template
from app_modules.company_data import (
    fetch_company_by_org,
    format_company_data,
    search_brreg_live,
)
from app_modules.Sammendrag.summery_getter import generate_company_summary
from app_modules.insurers.router import get_insurer_handlers
from app_modules.download import download_excel_file


@st.cache_data(ttl=3600, show_spinner=False)
def _extract_fields_from_pdf_cached(pdf_bytes: bytes, provider_hint: str) -> dict:
    """
    Mellomlagrer PDF-ekstraksjon per filinnhold for å unngå
    ny parsing ved hver Streamlit-rerun.
    """
    extract_fields_from_pdf, _ = get_insurer_handlers(provider_hint)
    return extract_fields_from_pdf(pdf_bytes, provider_hint=provider_hint)


@contextmanager
def _suppress_streamlit_messages(enabled: bool = True):
    """
    Hide noisy debug output from lower-level modules while processing.
    This keeps the UI clean in production mode.
    """
    if not enabled:
        yield
        return

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
    """Ekstraherer og slår sammen felter fra opplastede PDF-er."""
    pdf_fields = {}
    if not pdf_uploads:
        return pdf_fields

    combined_pdf_text_parts = []
    total = len(pdf_uploads)

    for idx, uploaded_pdf in enumerate(pdf_uploads, start=1):
        if progress:
            pct = start_pct + int((idx / total) * (end_pct - start_pct))
            progress.progress(pct, text=f"Leser PDF {idx}/{total}...")

        pdf_bytes = uploaded_pdf.getvalue()
        with _suppress_streamlit_messages(enabled=is_production_mode()):
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


def _trim_large_strings(value, max_chars: int = 15000):
    """Trimmer store tekstfelt i supportpakken."""
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return f"{value[:max_chars]} ... [trimmet {len(value) - max_chars} tegn]"
    if isinstance(value, dict):
        return {k: _trim_large_strings(v, max_chars=max_chars) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim_large_strings(v, max_chars=max_chars) for v in value]
    return value


def _build_support_bundle(company_name: str, vehicle_provider: str, merged_fields: dict, fill_report: dict) -> bytes:
    """
    Lager en zip-pakke for feilsøking uten å eksponere hemmeligheter.
    Inneholder rapport + trimmet datasett + notater.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "production" if is_production_mode() else "development"

    trimmed_fields = _trim_large_strings(dict(merged_fields))
    support_report = {
        "generated_at": timestamp,
        "mode": mode,
        "insurance_type": vehicle_provider,
        "company_name": company_name,
        "fill_report": fill_report,
    }

    notes = [
        f"Generert: {timestamp}",
        f"Modus: {mode}",
        f"Forsikringstype: {vehicle_provider}",
        f"Selskap: {company_name}",
        "",
        "Denne pakken ekskluderer hemmeligheter og API-nøkler.",
    ]

    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("support_report.json", json.dumps(support_report, indent=2, ensure_ascii=False))
        zf.writestr("merged_fields.json", json.dumps(trimmed_fields, indent=2, ensure_ascii=False))
        zf.writestr("notes.txt", "\n".join(notes))

    out.seek(0)
    return out.getvalue()


def _render_sidebar_tools():
    with st.sidebar:
        st.markdown("### Verktøy")
        st.caption("Bruk pilen oppe til venstre for å åpne/lukke denne menyen.")

        loaded_at = st.session_state.get("template_loaded_at")
        if loaded_at:
            st.caption(f"Excel-mal sist hentet: {loaded_at}")
        else:
            st.caption("Excel-mal er ikke hentet ennå.")

        if st.button("Oppdater Excel-mal nå", key="refresh_template_btn", use_container_width=True):
            with st.spinner("Henter nyeste Excel-mal fra Google Sheets..."):
                refresh_template(show_status=False)
            st.success("Excel-mal oppdatert.")
            st.rerun()


def run():
    st.markdown(
        """
        <div class="ui-hero">
          <h1>ForsikringsUtfyller</h1>
          <p>Hent selskapsinformasjon, les forsikrings-PDF-er og fyll Excel automatisk.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =========================================================
    # INITIALIZE SESSION STATE
    # =========================================================
    if "selected_company" not in st.session_state:
        st.session_state.selected_company = None
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "template_loaded_at" not in st.session_state:
        st.session_state["template_loaded_at"] = None

    _render_sidebar_tools()

    # ---------------------------------------------------------
    # STEP 1: SEARCH BAR + RESULT DROPDOWN
    # ---------------------------------------------------------
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.markdown("### Finn selskap")
    st.markdown("<p>Søk i Brreg og velg riktig foretak før du fortsetter.</p>", unsafe_allow_html=True)

    query = st.text_input(
        "Søk etter selskap",
        placeholder="Skriv minst 2 tegn for å søke",
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
            "Velg selskap",
            company_options,
            index=current_index,
            placeholder="Velg et selskap",
            key="company_selector",
        )

        # Update selected company when dropdown changes
        if selected_label and selected_label in company_options:
            idx = company_options.index(selected_label)
            st.session_state.selected_company = st.session_state.search_results[idx]

    st.markdown("</div>", unsafe_allow_html=True)

    # Check if we have a selected company
    if not st.session_state.selected_company:
        st.info("Velg et selskap for å fortsette.")
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

    # Always prefer BRREG entity lookup, but if that fails we still keep
    # the selected company from search (never fall back to PDF company name).
    raw_company_data = fetch_company_by_org(org_number) if org_number else None
    if not raw_company_data:
        raw_company_data = st.session_state.selected_company or {}

    company_data = format_company_data(raw_company_data)

    # Hard guard: company identity must come from BRREG/search selection,
    # not from parsed PDF fields.
    if not company_data.get("company_name"):
        company_data["company_name"] = st.session_state.selected_company.get("navn", "")
    if not company_data.get("org_number"):
        company_data["org_number"] = st.session_state.selected_company.get("organisasjonsnummer", "")

    # ---------------------------------------------------------
    # STEP 4: MANUAL FINANCIAL DATA ENTRY
    # ---------------------------------------------------------
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.markdown("### Økonomiske data (valgfritt)")

    st.info(
        """
    Fyll inn økonomiske data manuelt (du kan finne disse på Proff.no)

    La feltene stå tomme hvis det ikke trengs - appen fungerer uten.
    """
    )

    # Create 3 columns for 3 years
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**2024**")
        revenue_2024 = st.text_input("Omsetning", key="rev_2024", placeholder="f.eks. 15000000")
        operating_2024 = st.text_input("Driftsresultat", key="op_2024", placeholder="f.eks. 1500000")
        tax_2024 = st.text_input("Resultat før skatt", key="tax_2024", placeholder="f.eks. 1200000")
        assets_2024 = st.text_input("Sum eiendeler", key="assets_2024", placeholder="f.eks. 8000000")

    with col2:
        st.markdown("**2023**")
        revenue_2023 = st.text_input("Omsetning", key="rev_2023", placeholder="f.eks. 14000000")
        operating_2023 = st.text_input("Driftsresultat", key="op_2023", placeholder="f.eks. 1400000")
        tax_2023 = st.text_input("Resultat før skatt", key="tax_2023", placeholder="f.eks. 1100000")
        assets_2023 = st.text_input("Sum eiendeler", key="assets_2023", placeholder="f.eks. 7500000")

    with col3:
        st.markdown("**2022**")
        revenue_2022 = st.text_input("Omsetning", key="rev_2022", placeholder="f.eks. 13000000")
        operating_2022 = st.text_input("Driftsresultat", key="op_2022", placeholder="f.eks. 1300000")
        tax_2022 = st.text_input("Resultat før skatt", key="tax_2022", placeholder="f.eks. 1000000")
        assets_2022 = st.text_input("Sum eiendeler", key="assets_2022", placeholder="f.eks. 7000000")

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
        st.success(f"{len(financial_data)} økonomifelter registrert")
    else:
        st.info("Ingen økonomidata registrert - bruker kun BRREG-data")

    company_data.update(financial_data)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # STEP 5: PDF UPLOAD
    # ---------------------------------------------------------
    st.markdown('<div class="ui-card">', unsafe_allow_html=True)
    st.markdown("### Last opp dokumenter")
    st.markdown("<p>Legg til en eller flere PDF-er, og velg riktig forsikringstype.</p>", unsafe_allow_html=True)
    col_pdf, col_provider = st.columns([2, 1])
    with col_pdf:
        pdf_uploads = st.file_uploader(
            "Last opp PDF(er)",
            type=["pdf"],
            accept_multiple_files=True,
        )
    with col_provider:
        vehicle_provider = st.selectbox(
            "Forsikringstype",
            ["Velg forsikringstype", "Tryg", "Gjensidige", "If", "Ly", "Frende", "Landkreditt"],
            index=0,
            help="Velg forsikringsformat for uthenting",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # STEP 6: SUMMARY
    # ---------------------------------------------------------
    summary_text = generate_company_summary(company_data)

    # ---------------------------------------------------------
    # STEP 7: PROCESS & DOWNLOAD
    # ---------------------------------------------------------
    if st.button("Behandle og oppdater Excel", use_container_width=True):
        if vehicle_provider == "Velg forsikringstype":
            st.warning("Velg forsikringstype før behandling.")
            return

        progress = st.progress(0, text="Starter behandling...")
        try:
            progress.progress(10, text="Forbereder inndata...")

            pdf_fields = _collect_pdf_fields(
                pdf_uploads=pdf_uploads,
                provider_hint=vehicle_provider,
                progress=progress,
                start_pct=15,
                end_pct=45,
            )

            progress.progress(55, text="Slår sammen data...")
            merged_fields = {}
            merged_fields.update(pdf_fields)
            merged_fields.update(company_data)
            # Ensure these never get sourced from PDF.
            merged_fields["company_name"] = company_data.get("company_name", "")
            merged_fields["org_number"] = company_data.get("org_number", "")
            merged_fields["company_summary"] = summary_text
            merged_fields["vehicle_provider"] = vehicle_provider

            progress.progress(70, text="Genererer Excel-fil...")
            _, fill_excel = get_insurer_handlers(vehicle_provider)
            with _suppress_streamlit_messages(enabled=is_production_mode()):
                excel_bytes, fill_report = fill_excel(
                    template_bytes=template_bytes,
                    field_values=merged_fields,
                    summary_text=summary_text,
                    return_report=True,
                )

            failed_sheets = [
                s for s in fill_report.get("sheets", [])
                if s.get("status") == "failed"
            ]
            if failed_sheets:
                failed_names = ", ".join(s.get("sheet", "?") for s in failed_sheets)
                st.warning(f"Eksport fullført med delvise feil i: {failed_names}")

            progress.progress(90, text="Forbereder nedlasting...")
            download_excel_file(
                excel_bytes=excel_bytes,
                company_name=merged_fields.get("company_name", "Selskap"),
            )

            support_bytes = _build_support_bundle(
                company_name=merged_fields.get("company_name", "Selskap"),
                vehicle_provider=vehicle_provider,
                merged_fields=merged_fields,
                fill_report=fill_report,
            )

            safe_name = "".join(
                c for c in merged_fields.get("company_name", "Selskap")
                if c.isalnum() or c in " _-"
            ).strip() or "Selskap"
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            support_filename = f"{safe_name}_{stamp}_support.zip"

            st.download_button(
                label="Last ned supportpakke (.zip)",
                data=support_bytes,
                file_name=support_filename,
                mime="application/zip",
            )

            progress.progress(100, text="Ferdig")
        except Exception as e:
            progress.empty()
            if is_production_mode():
                st.error("Behandling feilet. Sjekk logger for detaljer.")
            else:
                st.error(f"Behandling feilet: {e}")
