"""Hand-written PricingConfig.rules for painting and false ceiling (SPEC §3.2).

Doubles as (a) seed payloads written into `pricing_configs` and (b) fixtures
driving the pricing-evaluator unit tests.
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

FALSE_CEILING_RULES: dict = {
    "schema_version": 1,
    "base_formula": "area_sqft * rate_per_sqft",
    "inputs": [
        {
            "name": "area_sqft",
            "type": "number",
            "required": True,
            "validation": {"min": 10, "max": 5000},
            "question_template": "What's the approximate false ceiling area in square feet?",
        },
        {
            "name": "ceiling_type",
            "type": "enum",
            "required": True,
            "options": ["grid_ceiling", "gypsum_board", "pop_ceiling"],
            "question_template": (
                "What type of false ceiling — grid ceiling (T-bar), "
                "gypsum board, or POP ceiling?"
            ),
        },
        {
            "name": "finish",
            "type": "enum",
            "required": True,
            "options": ["plain", "cornice", "curved"],
            "question_template": (
                "What finish are you looking for — plain flat, with cornice border, "
                "or curved/designer shape?"
            ),
        },
    ],
    "rate_table": [
        {"conditions": {"ceiling_type": "grid_ceiling", "finish": "plain"}, "rate_per_sqft": 85},
        {"conditions": {"ceiling_type": "grid_ceiling", "finish": "cornice"}, "rate_per_sqft": 100},
        {"conditions": {"ceiling_type": "grid_ceiling", "finish": "curved"}, "rate_per_sqft": 120},
        {"conditions": {"ceiling_type": "gypsum_board", "finish": "plain"}, "rate_per_sqft": 120},
        {"conditions": {"ceiling_type": "gypsum_board", "finish": "cornice"}, "rate_per_sqft": 145},
        {"conditions": {"ceiling_type": "gypsum_board", "finish": "curved"}, "rate_per_sqft": 180},
        {"conditions": {"ceiling_type": "pop_ceiling", "finish": "plain"}, "rate_per_sqft": 95},
        {"conditions": {"ceiling_type": "pop_ceiling", "finish": "cornice"}, "rate_per_sqft": 115},
        {"conditions": {"ceiling_type": "pop_ceiling", "finish": "curved"}, "rate_per_sqft": 155},
    ],
    "modifiers": [
        {"name": "gst", "type": "tax", "rate": 0.18},
    ],
    "line_item_template": [
        {
            "description": "False ceiling — {ceiling_type} ({finish})",
            "quantity_field": "area_sqft",
            "unit": "sqft",
            "rate_source": "computed_rate",
        }
    ],
}
