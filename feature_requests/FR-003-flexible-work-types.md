# FR-003: Flexible Work Types

## Goal
Overhaul the QuoteWise system to support dynamic, flexible work types (e.g. electrical, plumbing, carpentry) instead of hardcoding "painting" and "false ceiling".

## What was requested
- **DB Models & Migration**: Remove the `WorkType` Postgres enum and change columns to `VARCHAR(64)` strings in `contractor_admin_sessions`, `pricing_configs`, `sessions`, and `quotes`.
- **Pricing Schemas & Evaluator**: Make pricing variables generic by renaming `rate_per_sqft` to `base_rate`, and `amount_per_sqft_per_extra_unit` to `amount_per_extra_unit`. `quantity_field` fallback should be "quantity" instead of "area_sqft".
- **LLM Rate Card Ingest**: Rewrite `rate_card_ingest.jinja` to be trade-agnostic and infer `quantity_field` and `base_formula` directly from the rate card.
- **Contractor Handlers & Work Type Detection**: Remove the hardcoded `parse_work_type` mapping in favor of an automated slugifier. Update few-shot examples to include mapping for electrical/plumbing to prove the LLM can classify new domains.
- **Frontend & Types**: Replace all `WorkType` type hints with generic strings. Remove hardcoded "painting" default states to allow empty initialization or free-form text entry.
- **Testing**: Refactor and update tests to pass with string work_types and new schemas.

## Current State
This feature has been fully implemented, enabling contractors to onboard and manage quotes for any arbitrary trade without code modifications.
