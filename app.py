import streamlit as st
from app_modules import main_page


st.set_page_config(
    page_title="ForsikringsUtfyller",
    page_icon=":page_facing_up:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide Streamlit chrome and apply app theme.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
      background: #1f2128;
      border-right: 1px solid #4b5363;
    }

    [data-testid="collapsedControl"] svg {
      color: #ffffff !important;
      fill: #ffffff !important;
      stroke: #ffffff !important;
      opacity: 1 !important;
    }

    [data-testid="stSidebar"] * {
      color: #ffffff !important;
    }

    [data-testid="stHeader"] {
      background: transparent !important;
    }

    [data-testid="stToolbar"] button,
    [data-testid="stToolbar"] svg {
      color: #1d2f2a !important;
      fill: #1d2f2a !important;
      opacity: 1 !important;
    }

    :root {
      --brand: #008272;
      --brand-2: #00bba4;
      --panel: #ffffff;
      --bg: #f3f3f3;
      --text: #222222;
      --muted: #5d6c7b;
      --border: #dddddd;
    }

    [data-testid="stAppViewContainer"] {
      background:
        radial-gradient(900px 500px at 5% -15%, #f3f3f3, transparent 70%),
        radial-gradient(700px 400px at 95% -20%, #e2e2e2, transparent 65%),
        var(--bg);
      color: var(--text);
    }

    .stMainBlockContainer {
      max-width: 1180px;
      padding-top: 0.8rem;
      padding-bottom: 2rem;
    }

    .ui-hero {
      border-radius: 20px;
      padding: 16px 20px;
      margin: 0 0 0.9rem 0;
      color: #ffffff;
      background: linear-gradient(130deg, #262730, #1f2128);
      border: 1px solid #4b5363;
      box-shadow: 0 14px 30px rgba(11, 12, 16, 0.28);
    }

    .ui-hero h1 {
      margin: 0;
      font-size: 1.32rem;
      line-height: 1.25;
    }

    .ui-hero p {
      margin: 6px 0 0 0;
      font-size: 0.92rem;
      color: #ffffff !important;
    }

    .ui-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px 8px 14px;
      margin: 0 0 0.8rem 0;
      box-shadow: 0 4px 14px rgba(16, 34, 29, 0.06);
    }

    .ui-card h3 {
      color: var(--text);
      margin-top: 0;
      margin-bottom: 0.15rem;
      font-size: 1.04rem;
    }

    .ui-card p {
      color: var(--muted);
      margin: 0 0 0.5rem 0;
      font-size: 0.9rem;
    }

    .stMarkdown p,
    .stCaption,
    label,
    .stTextInput label,
    .stSelectbox label {
      color: var(--text) !important;
    }

    .stMarkdown .ui-hero p {
      color: #ffffff !important;
    }

    .stTextInput input::placeholder {
      color: #5c736d !important;
      opacity: 1;
    }

    [data-testid="stFileUploaderDropzone"] {
      border-radius: 10px;
      border: 1px solid #4b5363 !important;
      background: #262730 !important;
    }

    [data-testid="stFileUploaderDropzone"] [data-baseweb="button"],
    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"],
    [data-testid="stFileUploaderDropzone"] button {
      border-radius: 10px !important;
      border: 1px solid #5b6475 !important;
      background: #262730 !important;
      color: #ffffff !important;
      -webkit-text-fill-color: #ffffff !important;
      font-weight: 600 !important;
      opacity: 1 !important;
      text-shadow: none !important;
    }

    [data-testid="stFileUploaderDropzone"] [data-baseweb="button"] *,
    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] *,
    [data-testid="stFileUploaderDropzone"] button * {
      color: #ffffff !important;
      -webkit-text-fill-color: #ffffff !important;
      fill: #ffffff !important;
      stroke: #ffffff !important;
      opacity: 1 !important;
    }

    [data-testid="stFileUploaderDropzone"] [data-baseweb="button"]:hover,
    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stFileUploaderDropzone"] button:hover {
      background: #1f2128 !important;
      border-color: #707989 !important;
    }

    [data-testid="stFileUploaderDropzoneInstructions"] div,
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small {
      color: #ffffff !important;
    }

    [data-testid="stFileUploaderFile"] {
      background: #ffffff !important;
      border: 1px solid #c8dcd6 !important;
      border-radius: 8px !important;
    }

    [data-testid="stFileUploaderFile"] *,
    [data-testid="stFileUploaderFileName"] {
      color: #222222 !important;
      fill: #222222 !important;
    }

    [data-testid="stFileUploaderDeleteBtn"],
    [data-testid="stFileUploaderDeleteBtn"] * {
      background: transparent !important;
      box-shadow: none !important;
    }

    [data-testid="stFileUploaderDeleteBtn"] button,
    [data-testid="stFileUploaderDeleteBtn"] [role="button"],
    [data-testid="stFileUploaderFile"] button {
      background: transparent !important;
      border: none !important;
      box-shadow: none !important;
      color: #222222 !important;
    }

    [data-testid="stFileUploaderFile"] button:hover {
      background: #eef4f2 !important;
      border-radius: 6px !important;
    }

    [data-testid="stFileUploaderFile"] button svg,
    [data-testid="stFileUploaderFile"] svg,
    [data-testid="stFileUploaderDeleteBtn"] svg {
      color: #222222 !important;
      fill: #222222 !important;
      stroke: #222222 !important;
      background: transparent !important;
    }

    [data-testid="stFileUploaderDeleteBtn"] button::before,
    [data-testid="stFileUploaderDeleteBtn"] button::after {
      box-shadow: none !important;
    }

    /* Prevent broken icon glyph squares in uploader file rows */
    [data-testid="stFileUploaderFile"] > div:first-child svg {
      display: none !important;
    }

    [data-testid="stFileUploaderFile"] > div:first-child::before {
      content: "PDF";
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 2rem;
      height: 1.25rem;
      border-radius: 6px;
      background: #eef4f2;
      color: #1d2f2a !important;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }

    [data-testid="stFileUploaderDeleteBtn"] svg {
      display: none !important;
    }

    [data-testid="stFileUploaderDeleteBtn"] button {
      min-width: 1.45rem;
      min-height: 1.45rem;
      padding: 0 !important;
      line-height: 1 !important;
    }

    [data-testid="stFileUploaderDeleteBtn"] button::after {
      content: "x";
      color: #222222 !important;
      font-size: 0.95rem;
      font-weight: 700;
      line-height: 1;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    .stTextInput input {
      border-radius: 10px !important;
      border-color: #c8dcd6 !important;
    }

    .stButton > button,
    .stDownloadButton > button {
      border-radius: 10px;
      border: 1px solid #008272 !important;
      font-weight: 600;
      background: linear-gradient(180deg, #00bba4, #008272);
      color: #ffffff;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
      border-color: #008272 !important;
      background: linear-gradient(180deg, #008272, #006e61);
      color: #ffffff;
    }

    [data-testid="stAlert"] {
      border-radius: 10px;
    }

    [data-testid="stAlert"] p {
      color: #15312b !important;
      font-weight: 600;
    }

    [data-testid="stProgressBar"] > div > div > div > div {
      background-color: var(--brand);
    }

    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def main():
    main_page.run()


if __name__ == "__main__":
    main()
