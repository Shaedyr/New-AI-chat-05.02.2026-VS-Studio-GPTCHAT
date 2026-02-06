# Fordon Vehicle Extraction - Modular System

## 📁 File Structure

```
app_modules/Sheets/Fordon/
├── mapping.py                          # Main orchestrator
└── extractors/
    ├── __init__.py                     # Package initialization
    ├── if_format.py                    # If Skadeforsikring extractor
    ├── gjensidige_format.py            # Gjensidige extractor
    └── (add new companies here)
```

---

## 🎯 Currently Supported

### 1. **If Skadeforsikring** (`if_format.py`)

**PDF Format:**
```
AB12345, Varebil, VOLKSWAGEN
TRANSPORTER
Årsmodell: 2020
Kommune: Oslo
Kjørelengde: 16 000 km
Egenandel - Skader på eget kjøretøy: 8 000 kr
Tredjemannsinteresse/leasing: Sparebank 1

Bonus section:
AB12345: 60% bonus
```

**Extracts:**
- Registration, Type, Make/Model/Year
- Leasing, Annual Mileage, Deductible, Bonus
- Boat motor type (if applicable)

---

### 2. **Gjensidige** (`gjensidige_format.py`)

**PDF Formats:**

**Cars:**
```
VOLKSWAGEN TRANSPORTER 2020 BU 21895
- Sparebank 1 Sør-Norge ASA
```

**Tractors:**
```
Uregistrert traktor og arb.maskin - Doosan 300 DX 2023 - Uregistrert
```

**Extracts:**
- Registration (removes space: "BU 21895" → "BU21895")
- Make/Model/Year
- Leasing, Bonus

---

## ➕ How to Add a New Insurance Company

### Step 1: Create the Extractor File

Create: `extractors/your_company_format.py`

```python
# app_modules/Sheets/Fordon/extractors/your_company_format.py
"""
YOUR COMPANY NAME FORMAT EXTRACTOR

PDF Format:
-----------
(describe the format here)
"""

import re


def extract_your_company_vehicles(pdf_text: str) -> list:
    """
    Extract vehicles from Your Company PDF.
    
    Args:
        pdf_text: Full PDF text content
        
    Returns:
        List of vehicle dictionaries with these keys:
            - registration (str): e.g. "AB12345" or "Uregistrert"
            - vehicle_type (str): "bil", "traktor", "tilhenger", "moped", "båt"
            - make_model_year (str): e.g. "VOLKSWAGEN TRANSPORTER 2020"
            - coverage (str): usually "kasko"
            - leasing (str): e.g. "Sparebank 1" or ""
            - annual_mileage (str): e.g. "16 000" or ""
            - bonus (str): e.g. "60%" or ""
            - deductible (str): e.g. "8 000" or ""
    """
    vehicles = []
    seen_registrations = set()
    
    # YOUR EXTRACTION LOGIC HERE
    # Use regex patterns to find vehicles
    
    # Example pattern
    pattern = r'YOUR_REGEX_PATTERN_HERE'
    
    for match in re.finditer(pattern, pdf_text):
        reg = match.group(1).strip()
        
        # Skip duplicates
        if reg in seen_registrations:
            continue
        seen_registrations.add(reg)
        
        # Extract details...
        
        vehicles.append({
            "registration": reg,
            "vehicle_type": "bil",
            "make_model_year": "MAKE MODEL YEAR",
            "coverage": "kasko",
            "leasing": "",
            "annual_mileage": "",
            "bonus": "",
            "deductible": "",
        })
    
    return vehicles
```

---

### Step 2: Register in `__init__.py`

Edit: `extractors/__init__.py`

```python
from .if_format import extract_if_vehicles
from .gjensidige_format import extract_gjensidige_vehicles
from .your_company_format import extract_your_company_vehicles  # ← ADD

__all__ = [
    'extract_if_vehicles',
    'extract_gjensidige_vehicles',
    'extract_your_company_vehicles',  # ← ADD
]
```

---

### Step 3: Add to Main Orchestrator

Edit: `mapping.py`

Add import at top:
```python
from .extractors.your_company_format import extract_your_company_vehicles
```

Add extraction attempt in `extract_vehicles_from_pdf()`:
```python
# 3. Your Company Name
st.write("  🔎 **Your Company Name**")
try:
    your_vehicles = extract_your_company_vehicles(pdf_text)
    if your_vehicles:
        st.write(f"    ✅ {len(your_vehicles)} vehicles")
        all_vehicles.extend(your_vehicles)
    else:
        st.write("    ⊘ No matches")
except Exception as e:
    st.write(f"    ❌ Error: {e}")
```

---

### Step 4: Test!

1. Upload a PDF from the new company
2. Check the output:
   - ✅ Vehicles found
   - ✅ Correct registration numbers
   - ✅ Correct make/model/year
   - ✅ Leasing extracted (if available)
   - ✅ Bonus extracted (if available)

---

## 🧪 Testing Tips

### 1. Print PDF Text

```python
def extract_your_company_vehicles(pdf_text: str) -> list:
    # Print first 2000 chars to see format
    print(pdf_text[:2000])
    # ... rest of code
```

### 2. Test Regex Patterns

```python
import re

test_text = """
PASTE SAMPLE FROM PDF HERE
"""

pattern = r'YOUR_PATTERN'
matches = re.findall(pattern, test_text)
print(f"Found {len(matches)} matches:")
for m in matches:
    print(m)
```

### 3. Use regex101.com

- Paste your PDF sample
- Test patterns interactively
- See match groups highlighted

---

## 📊 Vehicle Dictionary Format

**Every extractor MUST return this format:**

```python
{
    "registration": "AB12345",              # Required
    "vehicle_type": "bil",                   # Required
    "make_model_year": "FORD TRANSIT 2023", # Required
    "coverage": "kasko",                     # Required
    "leasing": "Sparebank 1",               # Optional ("")
    "annual_mileage": "16 000",             # Optional ("")
    "bonus": "60%",                          # Optional ("")
    "deductible": "8 000",                  # Optional ("")
}
```

**Vehicle types:**
- `"bil"` - Cars/vans
- `"traktor"` - Tractors/machines
- `"tilhenger"` - Trailers
- `"moped"` - Mopeds/scooters
- `"båt"` - Boats

---

## 🔍 Common Regex Patterns

### Registration Numbers
```python
r'([A-Z]{2}\s?\d{5})'  # Matches: "AB12345" or "AB 12345"
```

### Year
```python
r'(20\d{2})'  # Matches: 2020, 2021, 2022, etc.
```

### Make/Model
```python
r'(VOLKSWAGEN|FORD|TOYOTA)\s+([A-Z\s]+)'
```

### Numbers with space
```python
r'(\d+\s?\d+)\s*km'  # Matches: "16 000 km" or "16000 km"
```

---

## ⚠️ Important Rules

1. **Always strip whitespace** from extracted values
2. **Handle missing data** with empty strings `""` (not `None`)
3. **Remove duplicates** using registration numbers
4. **Test with real PDFs** from the company
5. **Document the format** in docstrings
6. **Handle errors gracefully** with try/except

---

## 🎨 Best Practices

### Clean Model Names
```python
model = match.group(1).strip()
model = re.sub(r'\s*-\s*Uregistrert.*$', '', model).strip()
model = re.sub(r'\s+(arb|maskin).*$', '', model, flags=re.I).strip()
```

### Normalize Registration
```python
reg = reg_with_space.replace(" ", "")  # "BU 21895" → "BU21895"
reg = reg.upper()  # Ensure uppercase
```

### Extract from Section
```python
# Get context around match
pos = match.start()
section = pdf_text[max(0, pos-200):min(len(pdf_text), pos+500)]

# Extract details from section
leasing = _extract_leasing(section)
```

---

## 🆘 Debugging

### If vehicles aren't found:

1. **Print the PDF text:**
   ```python
   print("PDF TEXT:", pdf_text[:1000])
   ```

2. **Check pattern matches:**
   ```python
   matches = re.findall(pattern, pdf_text)
   print(f"Pattern found {len(matches)} matches")
   ```

3. **Check for case sensitivity:**
   ```python
   re.finditer(pattern, pdf_text, re.I)  # Add re.I flag
   ```

4. **Use `st.write()` for debugging:**
   ```python
   st.write(f"DEBUG: Found {len(vehicles)} vehicles")
   st.write(f"DEBUG: Pattern: {pattern}")
   ```

---

## 📝 Example: Adding "Tryg"

**1. Create** `extractors/tryg_format.py`:
```python
def extract_tryg_vehicles(pdf_text: str) -> list:
    vehicles = []
    # ... extraction logic
    return vehicles
```

**2. Update** `extractors/__init__.py`:
```python
from .tryg_format import extract_tryg_vehicles
__all__ = [..., 'extract_tryg_vehicles']
```

**3. Update** `mapping.py`:
```python
from .extractors.tryg_format import extract_tryg_vehicles

# In extract_vehicles_from_pdf():
st.write("  🔎 **Tryg**")
tryg_vehicles = extract_tryg_vehicles(pdf_text)
all_vehicles.extend(tryg_vehicles)
```

**Done!** 🎉

---

## 🚀 Benefits of This System

✅ **Easy to maintain** - Each company isolated  
✅ **Easy to debug** - Know exactly which extractor failed  
✅ **Easy to extend** - Just add a new file  
✅ **Clean code** - No giant if/else chains  
✅ **Testable** - Each extractor can be tested independently

---

**Happy extracting!** 🎯
