import streamlit as st
import requests
from datetime import datetime

TEMPLATE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZgo_lI3n1uTuOz6DzJnKUU--_Cs991MzQ_NNtkqxUmEq5k8W6Qki_O0hwngLVxHoD9GcAxRG-mq7w/pub?output=xlsx"
_SESSION = requests.Session()


@st.cache_data(ttl=3600)
def _fetch_template_bytes() -> bytes:
    response = _SESSION.get(TEMPLATE_URL, timeout=20)
    response.raise_for_status()
    return response.content


def _store_template_in_session(template_bytes: bytes) -> bytes:
    st.session_state["template_bytes"] = template_bytes
    st.session_state["template_loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template_bytes


def load_template(force_refresh: bool = False, show_status: bool = True):
    try:
        if force_refresh:
            _fetch_template_bytes.clear()

        template_bytes = _fetch_template_bytes()  # <-- THIS is what fill_excel needs

        _store_template_in_session(template_bytes)
        if show_status:
            if force_refresh:
                st.success("Excel-mal oppdatert fra Google Sheets")
            else:
                st.success("Excel-mal lastet fra Google Sheets")
        return template_bytes

    except Exception as e:
        st.error(f"Kunne ikke laste Excel-mal: {e}")
        st.stop()


def refresh_template(show_status: bool = True) -> bytes:
    return load_template(force_refresh=True, show_status=show_status)
