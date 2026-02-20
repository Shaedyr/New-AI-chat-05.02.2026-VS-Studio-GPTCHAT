import streamlit as st
from app_modules import main_page


st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide the Streamlit sidebar and collapsed menu button for a cleaner UI.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def main():
    main_page.run()


if __name__ == "__main__":
    main()
