import streamlit as st
import pdfplumber
import re
from io import BytesIO

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

# How many pages to read from PDF
# NOTE: Reading ALL pages (150+) is slow. Adjust as needed.
# Most vehicle info is in pages 1-100.
# Increased to 100 to support Tryg PDFs which have vehicles on later pages.
MAX_PAGES_TO_READ = 100  # Increased for Tryg support!
OCR_MIN_TEXT_LENGTH = 1000  # If extracted text is shorter, try OCR fallback
OCR_MAX_PAGES = 12  # OCR is slow; limit pages for fallback
OCR_LANG = "nor+eng"

# Companies to IGNORE (insurance brokers, not clients)
IGNORE_COMPANIES = [
    "AS FORSIKRINGSMEGLING",
    "IF SKADEFORSIKRING",
    "GJENSIDIGE FORSIKRING",
    "TRYG FORSIKRING",
]

# ---------------------------------------------------------
# REGEX PATTERNS
# ---------------------------------------------------------

ORG_RE = re.compile(r"\b(\d{9})\b")
ORG_IN_TEXT_RE = re.compile(
    r"(organisasjonsnummer|org\.?nr|org nr|orgnummer)[:\s]*?(\d{9})",
    flags=re.I
)

COMPANY_WITH_SUFFIX_RE = re.compile(
    r"([A-ZÆØÅ][A-Za-zÆØÅæøå0-9.\-&\s]{1,120}?)\s+(AS|ASA|ANS|DA|ENK|KS|BA)\b",
    flags=re.I
)

POST_CITY_RE = re.compile(
    r"(\d{4})\s+([A-ZÆØÅa-zæøå\-\s]{2,50})"
)

ADDRESS_RE = re.compile(
    r"([A-ZÆØÅa-zæøå.\-\s]{3,60}\s+\d{1,4}[A-Za-z]?)"
)

REVENUE_RE = re.compile(
    r"omsetning\s*(?:2024)?[:\s]*([\d\s\.,]+(?:kr)?)",
    flags=re.I
)

DEADLINE_RE = re.compile(
    r"(?:anbudsfrist|frist)[:\s]*([0-3]?\d[./-][01]?\d[./-]\d{2,4})",
    flags=re.I
)

# ---------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from PDF pages.
    Reads up to MAX_PAGES_TO_READ pages (default: 50).
    Returns a single string.
    """

    # Handle Streamlit UploadedFile objects
    if hasattr(pdf_bytes, 'read'):
        pdf_bytes = pdf_bytes.read()

    if not pdf_bytes:
        st.warning("⚠️ No PDF bytes provided")
        return ""

    st.write(f"📄 **Extracting text from PDF** ({len(pdf_bytes)} bytes)")

    try:
        text = ""
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            pages_to_read = min(MAX_PAGES_TO_READ, total_pages)
            
            st.success(f"✅ PDF has {total_pages} pages")
            
            if total_pages > MAX_PAGES_TO_READ:
                st.info(f"📖 Reading first {pages_to_read} pages (adjust MAX_PAGES_TO_READ if needed)")
            else:
                st.info(f"📖 Reading all {pages_to_read} pages")
            
            # Show progress for large PDFs
            if pages_to_read > 20:
                progress_bar = st.progress(0)
            
            for i, page in enumerate(pdf.pages[:pages_to_read]):
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
                
                # Update progress bar for large PDFs
                if pages_to_read > 20 and i % 5 == 0:
                    progress_bar.progress((i + 1) / pages_to_read)
            
            if pages_to_read > 20:
                progress_bar.progress(1.0)
                st.write(f"  ✓ Extracted text from {pages_to_read} pages")
            else:
                st.write(f"  ✓ Pages extracted: {pages_to_read}")
        
        if text:
            st.success(f"✅ **Total: {len(text)} characters extracted**")
        else:
            st.error("❌ No text extracted!")
            st.warning("PDF might be image-based, encrypted, or corrupted")
        
        # OCR fallback if text is too short (likely scanned PDF)
        if len(text) < OCR_MIN_TEXT_LENGTH:
            st.warning("⚠️ Extracted text is short; attempting OCR fallback...")
            ocr_text = _ocr_text_from_pdf(pdf_bytes, max_pages=OCR_MAX_PAGES)
            if ocr_text:
                text = (text + "\n" + ocr_text).strip()
                st.success(f"✅ OCR added {len(ocr_text)} characters")
            else:
                st.warning("⚠️ OCR produced no text")

        return text

    except Exception as e:
        st.error(f"❌ PDF extraction error: {e}")
        import traceback
        st.code(traceback.format_exc())
        # Try OCR even if pdfplumber fails
        ocr_text = _ocr_text_from_pdf(pdf_bytes, max_pages=OCR_MAX_PAGES)
        if ocr_text:
            st.success(f"✅ OCR added {len(ocr_text)} characters after error")
            return ocr_text
        return ""


def _ocr_text_from_pdf(pdf_bytes: bytes, max_pages: int = 10) -> str:
    """Fallback OCR for scanned PDFs."""
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
    except Exception as e:
        st.warning(f"⚠️ OCR not available: {e}")
        return ""

    text = ""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            pages_to_read = min(max_pages, total_pages)
            st.info(f"🔎 OCR reading {pages_to_read} page(s)")
            for i, page in enumerate(pdf.pages[:pages_to_read]):
                try:
                    img = page.to_image(resolution=200).original
                    page_text = pytesseract.image_to_string(img, lang=OCR_LANG)
                    if page_text:
                        text += page_text + "\n"
                except Exception as e:
                    st.warning(f"⚠️ OCR failed on page {i+1}: {e}")
    except Exception as e:
        st.warning(f"⚠️ OCR failed to open PDF: {e}")
        return ""

    return text.strip()

# ---------------------------------------------------------
# FIELD EXTRACTION
# ---------------------------------------------------------

def extract_fields_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Extracts fields from PDF:
    - org number
    - company name (ignoring insurance brokers)
    - address, postal code, city
    - revenue, deadline
    - pdf_text (full text for vehicle extraction)
    """
    
    st.write("=" * 50)
    st.write("🔍 **PDF PARSER: Starting extraction**")
    st.write("=" * 50)

    txt = extract_text_from_pdf(pdf_bytes)
    fields = {}

    if not txt:
        st.error("❌ No text extracted - returning empty fields")
        return fields

    # CRITICAL: Store full text for Fordon sheet
    fields["pdf_text"] = txt
    st.write(f"✓ Added 'pdf_text' ({len(txt)} chars)")

    # 1) Org number
    m = ORG_IN_TEXT_RE.search(txt)
    if m:
        fields["org_number"] = m.group(2)
        st.write(f"✓ Org number: {m.group(2)}")
    else:
        m2 = ORG_RE.search(txt)
        if m2:
            fields["org_number"] = m2.group(1)
            st.write(f"✓ Org number: {m2.group(1)}")

    # 2) Company name - SKIP insurance brokers!
    matches = COMPANY_WITH_SUFFIX_RE.finditer(txt)
    for m3 in matches:
        company = m3.group(0).strip()
        
        # Skip insurance brokers
        if any(ignore.upper() in company.upper() for ignore in IGNORE_COMPANIES):
            st.write(f"⊘ Skipped broker: {company}")
            continue
        
        # Found actual client company
        fields["company_name"] = company
        st.write(f"✓ Company: {company}")
        break

    # 3) Postal code + city
    mpc = POST_CITY_RE.search(txt)
    if mpc:
        fields["post_nr"] = mpc.group(1)
        fields["city"] = mpc.group(2).strip()
        st.write(f"✓ Postal: {mpc.group(1)} {mpc.group(2).strip()}")

    # 4) Address
    maddr = ADDRESS_RE.search(txt)
    if maddr:
        fields["address"] = maddr.group(1).strip()
        st.write(f"✓ Address: {maddr.group(1).strip()}")

    # 5) Revenue
    mrev = REVENUE_RE.search(txt)
    if mrev:
        fields["revenue_2024"] = mrev.group(1).strip()
        st.write(f"✓ Revenue: {mrev.group(1).strip()}")

    # 6) Deadline
    mdate = DEADLINE_RE.search(txt)
    if mdate:
        fields["tender_deadline"] = mdate.group(1).strip()
        st.write(f"✓ Deadline: {mdate.group(1).strip()}")

    st.write("=" * 50)
    st.success(f"✅ Returning {len(fields)} fields")
    st.write(f"Keys: {list(fields.keys())}")
    st.write("=" * 50)

    return fields

# ---------------------------------------------------------
# PAGE VIEW
# ---------------------------------------------------------
def run():
    st.title("📄 PDF Parser Module")
    st.write("Dette modulen ekstraherer tekst og felter fra PDF-dokumenter.")
    st.info("Brukes av hovedsiden for å hente data fra PDF.")
