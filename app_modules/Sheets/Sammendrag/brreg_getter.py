# app_modules/Sheets/Sammendrag/brreg_getter.py
"""
Full BRREG getter implementation placed inside the Sammendrag sheet folder.
Queries the official Enhetsregisteret API and normalizes fields for the sheet.
"""

import requests
import logging

logger = logging.getLogger(__name__)
BRREG_API = "https://data.brreg.no/enhetsregisteret/api/enheter/{}"

def _normalize_address(addr_obj: dict) -> str:
    if not addr_obj:
        return ""
    parts = []
    # 'adresse' may be a list or string depending on API version
    adr = addr_obj.get("adresse")
    if isinstance(adr, list):
        parts.append(", ".join(filter(None, adr)))
    elif adr:
        parts.append(adr)
    postnr = addr_obj.get("postnummer") or addr_obj.get("postnummer")
    poststed = addr_obj.get("poststed")
    if postnr:
        parts.append(str(postnr))
    if poststed:
        parts.append(poststed)
    return ", ".join(filter(None, parts))

def fetch_brreg_info(query: str) -> dict:
    """
    Query BRREG by orgnr (preferred). If query is not numeric, return empty dict.
    Returns normalized keys: name, org_no, address, postnr, poststed, naeringskode, naeringskode_beskrivelse
    """
    if not query:
        return {}
    org = query.strip()
    if not org.isdigit():
        # BRREG lookup by name is more complex; keep minimal here to avoid false positives
        return {}
    url = BRREG_API.format(org)
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            logger.debug("BRREG returned status %s for %s", r.status_code, org)
            return {}
        data = r.json()
        # Forretningsadresse may be nested
        forretningsadresse = data.get("forretningsadresse") or {}
        address = _normalize_address(forretningsadresse)
        postnr = forretningsadresse.get("postnummer") or ""
        poststed = forretningsadresse.get("poststed") or ""
        naerings = data.get("naeringskode1") or {}
        return {
            "name": data.get("navn"),
            "org_no": data.get("organisasjonsnummer"),
            "address": address,
            "postnr": postnr,
            "poststed": poststed,
            "naeringskode": naerings.get("kode"),
            "naeringskode_beskrivelse": naerings.get("beskrivelse"),
        }
    except Exception as e:
        logger.warning("BRREG fetch failed for %s: %s", org, e)
    return {}