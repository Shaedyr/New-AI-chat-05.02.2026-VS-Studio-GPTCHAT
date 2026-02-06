def merge_company_data(brreg_data: dict, proff_data: dict) -> dict:
    """
    Merges BRREG data and Proff.no data into one clean dictionary.

    Rules:
    - BRREG is the primary source for identity + address + NACE.
    - Proff always overrides revenue_2024.
    - Proff fills missing fields from BRREG.
    - Proff adds financials.
    """

    if not brreg_data:
        brreg_data = {}

    if not proff_data:
        proff_data = {}

    # Start with BRREG as the base
    merged = brreg_data.copy()

    # Always prefer Proff revenue
    if proff_data.get("revenue_2024"):
        merged["revenue_2024"] = proff_data["revenue_2024"]

    # Add financials if present
    if proff_data.get("financials"):
        merged["financials"] = proff_data["financials"]

    # Fill missing fields from Proff
    for key, value in proff_data.items():
        if key not in merged or not merged.get(key):
            merged[key] = value

    return merged
