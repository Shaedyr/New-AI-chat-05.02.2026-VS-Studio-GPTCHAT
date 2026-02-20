import os
import streamlit as st


def get_app_mode() -> str:
    """
    Resolve app mode with this precedence:
    1) APP_MODE environment variable
    2) Streamlit secret: app_mode
    3) default: production
    """
    env_mode = os.getenv("APP_MODE", "").strip().lower()
    if env_mode:
        return env_mode

    try:
        secret_mode = str(st.secrets.get("app_mode", "")).strip().lower()
        if secret_mode:
            return secret_mode
    except Exception:
        pass

    return "production"


def is_production_mode() -> bool:
    return get_app_mode() == "production"
