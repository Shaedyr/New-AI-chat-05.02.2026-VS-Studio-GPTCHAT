import streamlit as st
import app_modules.input as input_module

# SIDEBAR IS NOW VISIBLE!
st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded"  # Changed from "collapsed" to "expanded"
)

# REMOVED the CSS that hides the sidebar!
# The sidebar will now be visible for debugging

# Clean imports
from app_modules import main_page
from app_modules import company_data
from app_modules import pdf_parser
from app_modules.Sheets.Sammendrag import summery_getter as summary
from app_modules.Sheets import excel_filler
from app_modules import template_loader
from app_modules import download

# Sidebar page mapping
PAGES = {
    "🏠 Hovedside": main_page,
    "📄 Input-modul": input_module,
    "🏢 Company Data": company_data,
    "📄 PDF Parser": pdf_parser,
    "📝 Summary Generator": summary,
    "📊 Excel Filler": excel_filler,
    "📁 Template Loader": template_loader,
    "📥 Download": download,
}

def main():
    st.sidebar.title("Navigasjon")
    choice = st.sidebar.radio("Velg side:", list(PAGES.keys()))
    page = PAGES[choice]
    page.run()

if __name__ == "__main__":
    main()
