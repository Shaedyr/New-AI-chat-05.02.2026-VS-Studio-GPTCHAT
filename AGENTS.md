# AGENTS.md

## Purpose
This file defines how Codex should work in this project.

## Core Rules
1. Do not break existing insurer formats when fixing another format.
2. Keep extractor logic isolated per insurer (`If`, `Gjensidige`, `Tryg`).
3. Prefer additive fixes (new patterns) over replacing old patterns.
4. Before changing code, explain what will be changed and why.
5. Do not push, sync, or publish anything unless explicitly requested.
6. Do not run destructive git commands unless explicitly requested.

## Change Safety
1. If changing one extractor, do not change shared mapping/parsing unless necessary.
2. If shared code must change, state regression risk first.
3. After edits, run a quick sanity check for affected insurers.
4. Report exactly what files were changed.

## Extraction Expectations
1. Map only fields that exist in the source PDF.
2. Leave missing fields blank (do not invent values).
3. Support OCR/noisy text variants when safe, but keep support for original labels.
4. Keep Excel mapping stable unless user asks to change mapping.

## Communication
1. Be concise and direct.
2. If uncertain, ask before making broad changes.
3. Offer rollback-safe options first.

