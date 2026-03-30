"""
Insurer router.

Routes parser/filler calls to the selected insurer package only.
This avoids cross-insurer execution paths in normal app flow.
"""

from __future__ import annotations

from app_modules.insurers.gjensidige.pdf_parser import extract_fields_from_pdf as extract_gjensidige_pdf
from app_modules.insurers.gjensidige.excel_filler import fill_excel as fill_gjensidige_excel

from app_modules.insurers.if_insurance.pdf_parser import extract_fields_from_pdf as extract_if_pdf
from app_modules.insurers.if_insurance.excel_filler import fill_excel as fill_if_excel

from app_modules.insurers.tryg.pdf_parser import extract_fields_from_pdf as extract_tryg_pdf
from app_modules.insurers.tryg.excel_filler import fill_excel as fill_tryg_excel

from app_modules.insurers.ly.pdf_parser import extract_fields_from_pdf as extract_ly_pdf
from app_modules.insurers.ly.excel_filler import fill_excel as fill_ly_excel

from app_modules.insurers.frende.pdf_parser import extract_fields_from_pdf as extract_frende_pdf
from app_modules.insurers.frende.excel_filler import fill_excel as fill_frende_excel

from app_modules.insurers.landkreditt.pdf_parser import extract_fields_from_pdf as extract_landkreditt_pdf
from app_modules.insurers.landkreditt.excel_filler import fill_excel as fill_landkreditt_excel


def get_insurer_handlers(provider: str):
    key = (provider or "").strip().lower()

    if key == "tryg":
        return extract_tryg_pdf, fill_tryg_excel
    if key == "gjensidige":
        return extract_gjensidige_pdf, fill_gjensidige_excel
    if key in ("if", "if skadeforsikring"):
        return extract_if_pdf, fill_if_excel
    if key == "ly":
        return extract_ly_pdf, fill_ly_excel
    if key == "frende":
        return extract_frende_pdf, fill_frende_excel
    if key == "landkreditt":
        return extract_landkreditt_pdf, fill_landkreditt_excel

    raise ValueError(f"Unsupported insurance type: {provider}")
