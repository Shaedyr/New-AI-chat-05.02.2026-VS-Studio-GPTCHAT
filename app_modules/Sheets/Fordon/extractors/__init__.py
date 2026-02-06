# app_modules/Sheets/Fordon/extractors/__init__.py
"""
Vehicle extractors for different insurance companies.
Each company has its own extractor file.
"""

# Don't import here - let mapping.py import directly from the modules
__all__ = [
    'if_skadeforsikring',
    'gjensidige',
]
