from app_modules.insurers.shared.excel_filler import fill_excel as fill_excel_base
from app_modules.insurers.if_insurance.sheet_config import SHEET_MAPPINGS, transform_for_sheet


def fill_excel(template_bytes, field_values, summary_text, return_report=False):
    return fill_excel_base(
        template_bytes=template_bytes,
        field_values=field_values,
        summary_text=summary_text,
        return_report=return_report,
        sheet_mappings=SHEET_MAPPINGS,
        transform_for_sheet_fn=transform_for_sheet,
    )


__all__ = ["fill_excel"]

