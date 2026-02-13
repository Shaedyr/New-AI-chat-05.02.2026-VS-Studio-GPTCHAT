Generated fixture PDFs for parser validation.

Files:
- fixture_tryg_full_columns.pdf
- fixture_if_full_columns.pdf
- fixture_gjensidige_full_columns.pdf

Expected mapped columns (Fordon sheet):
- B: registration
- C: make_model_year
- D: sum_insured
- E: coverage
- F: leasing
- G: annual_mileage
- H: bonus
- I: deductible

Fixture coverage:
- fixture_tryg_full_columns.pdf -> B,C,D,E,F,G,H,I
- fixture_if_full_columns.pdf -> B,C,E,F,G,I
- fixture_gjensidige_full_columns.pdf -> B,C,D,E,F,G,H (cars), plus tractor/other rows

Notes:
- IF extractor does not currently map bonus or sum_insured.
- Gjensidige extractor does not currently map deductible.
