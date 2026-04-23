"""Hand-written painting PricingConfig.rules (SPEC §3.2).

3 tiers × 3 surface types = 9 rate-table entries. Modifiers: extra-coat
surcharge (+3/sqft per coat beyond 2) and 18% GST.

This dict doubles as (a) the seed payload written into the `pricing_configs`
table and (b) the fixture driving the pricing-evaluator unit tests.
"""

PAINTING_RULES: dict = {
    "schema_version": 1,
    "base_formula": "area_sqft * rate_per_sqft",
    "inputs": [
        {
            "name": "area_sqft",
            "type": "number",
            "required": True,
            "validation": {"min": 10, "max": 10000},
            "question_template": "What's the approximate area to be painted, in square feet?",
        },
        {
            "name": "surface_type",
            "type": "enum",
            "required": True,
            "options": ["new_wall", "repaint_good_condition", "repaint_damaged"],
            "question_template": (
                "Is this a new wall, a repaint over good condition, "
                "or a repaint over damaged walls?"
            ),
        },
        {
            "name": "coats",
            "type": "integer",
            "required": True,
            "default": 2,
            "question_template": "How many coats of paint? (Most jobs use 2.)",
        },
        {
            "name": "paint_brand_tier",
            "type": "enum",
            "required": True,
            "options": ["basic", "premium", "luxury"],
            "question_template": (
                "What paint quality — basic (Tractor Emulsion), premium (Royale), "
                "or luxury (Royale Aspira)?"
            ),
        },
    ],
    "rate_table": [
        {"conditions": {"paint_brand_tier": "basic", "surface_type": "new_wall"}, "rate_per_sqft": 14},
        {"conditions": {"paint_brand_tier": "basic", "surface_type": "repaint_good_condition"}, "rate_per_sqft": 12},
        {"conditions": {"paint_brand_tier": "basic", "surface_type": "repaint_damaged"}, "rate_per_sqft": 20},
        {"conditions": {"paint_brand_tier": "premium", "surface_type": "new_wall"}, "rate_per_sqft": 22},
        {"conditions": {"paint_brand_tier": "premium", "surface_type": "repaint_good_condition"}, "rate_per_sqft": 20},
        {"conditions": {"paint_brand_tier": "premium", "surface_type": "repaint_damaged"}, "rate_per_sqft": 28},
        {"conditions": {"paint_brand_tier": "luxury", "surface_type": "new_wall"}, "rate_per_sqft": 32},
        {"conditions": {"paint_brand_tier": "luxury", "surface_type": "repaint_good_condition"}, "rate_per_sqft": 30},
        {"conditions": {"paint_brand_tier": "luxury", "surface_type": "repaint_damaged"}, "rate_per_sqft": 40},
    ],
    "modifiers": [
        {
            "name": "extra_coat",
            "type": "per_unit_surcharge",
            "condition": {"field": "coats", "op": "gt", "value": 2},
            "over_field": "coats",
            "over_baseline": 2,
            "amount_per_sqft_per_extra_unit": 3,
            "quantity_field": "area_sqft",
        },
        {"name": "gst", "type": "tax", "rate": 0.18},
    ],
    "line_item_template": [
        {
            "description": "Painting — {paint_brand_tier} ({surface_type}), {coats} coats",
            "quantity_field": "area_sqft",
            "unit": "sqft",
            "rate_source": "computed_rate",
        }
    ],
}
