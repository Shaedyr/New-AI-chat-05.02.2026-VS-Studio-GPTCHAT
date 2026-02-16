"""
Yrkesskade mapping orchestrator (shared).

Dispatches to insurer-specific mapping modules while keeping
logic isolated per insurer.
"""

from __future__ import annotations

from app_modules.insurers.gjensidige.workers_comp_mapping import (
    transform_data as transform_gjensidige_workers_comp,
)


CELL_MAP: dict = {}


def _detect_provider(pdf_text: str) -> str:
    text = (pdf_text or "").lower()
    if "gjensidige" in text:
        return "gjensidige"
    if "tryg" in text:
        return "tryg"
    if "if skadeforsikring" in text or " if " in f" {text} ":
        return "if"
    return ""


def transform_data(extracted: dict) -> dict:
    """
    Dynamic mapping entry point for Yrkesskade sheet.
    """
    data = dict(extracted or {})
    provider = (data.get("vehicle_provider") or "").strip().lower()
    pdf_text = data.get("pdf_text", "") or ""

    if provider == "auto-detect":
        provider = ""
    if not provider:
        provider = _detect_provider(pdf_text)

    if provider == "gjensidige":
        return transform_gjensidige_workers_comp(data)

    # Other insurer mappings can be added here later.
    return {}

