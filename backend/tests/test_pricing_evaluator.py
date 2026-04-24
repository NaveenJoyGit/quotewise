import copy
from decimal import Decimal

import pytest

from app.services.pricing import (
    InvalidSlotValueError,
    MissingSlotError,
    RateNotFoundError,
    evaluate_quote,
)
from app.services.pricing.evaluator import validate_slot_value
from app.services.pricing.schemas import InputDef
from app.services.pricing.seed_rules import PAINTING_RULES


# ---------------------------------------------------------------------------
# SPEC §10.2 success criterion
# ---------------------------------------------------------------------------
def test_success_criterion_basic_new_wall_1000_sqft_2_coats():
    q = evaluate_quote(
        PAINTING_RULES,
        {
            "area_sqft": 1000,
            "surface_type": "new_wall",
            "coats": 2,
            "paint_brand_tier": "basic",
        },
    )
    assert q.subtotal == Decimal("14000.00")
    assert q.gst_amount == Decimal("2520.00")
    assert q.total == Decimal("16520.00")
    assert q.confidence_score == 1.0
    assert len(q.line_items) == 1
    assert q.line_items[0].quantity == Decimal("1000")
    assert q.line_items[0].unit == "sqft"
    assert q.line_items[0].rate == Decimal("14")
    assert q.line_items[0].amount == Decimal("14000.00")
    assert q.line_items[0].description == "Painting — basic (new_wall), 2 coats"


# ---------------------------------------------------------------------------
# Every rate-table row hit (3 tiers × 3 surfaces = 9 combos)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tier, surface, rate",
    [
        ("basic", "new_wall", 14),
        ("basic", "repaint_good_condition", 12),
        ("basic", "repaint_damaged", 20),
        ("premium", "new_wall", 22),
        ("premium", "repaint_good_condition", 20),
        ("premium", "repaint_damaged", 28),
        ("luxury", "new_wall", 32),
        ("luxury", "repaint_good_condition", 30),
        ("luxury", "repaint_damaged", 40),
    ],
)
def test_every_rate_combo(tier, surface, rate):
    q = evaluate_quote(
        PAINTING_RULES,
        {"area_sqft": 1000, "surface_type": surface, "coats": 2, "paint_brand_tier": tier},
    )
    assert q.subtotal == Decimal(rate * 1000).quantize(Decimal("0.01"))
    assert q.line_items[0].rate == Decimal(rate)


# ---------------------------------------------------------------------------
# Extra-coat surcharge
# ---------------------------------------------------------------------------
def test_extra_coat_surcharge_one_extra():
    q = evaluate_quote(
        PAINTING_RULES,
        {"area_sqft": 1000, "surface_type": "new_wall", "coats": 3, "paint_brand_tier": "basic"},
    )
    # base 14*1000 = 14000 + surcharge 1*3*1000 = 3000 -> 17000
    assert q.subtotal == Decimal("17000.00")
    assert q.gst_amount == Decimal("3060.00")
    assert q.total == Decimal("20060.00")
    # Line-item amount should absorb the surcharge.
    assert q.line_items[0].amount == Decimal("17000.00")


def test_extra_coat_surcharge_two_extra():
    q = evaluate_quote(
        PAINTING_RULES,
        {"area_sqft": 1000, "surface_type": "new_wall", "coats": 4, "paint_brand_tier": "basic"},
    )
    # base 14000 + 2*3*1000 = 20000
    assert q.subtotal == Decimal("20000.00")


def test_defaults_applied_for_coats_when_omitted():
    q = evaluate_quote(
        PAINTING_RULES,
        {"area_sqft": 1000, "surface_type": "new_wall", "paint_brand_tier": "basic"},
    )
    # coats defaults to 2 -> no surcharge
    assert q.subtotal == Decimal("14000.00")


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
def test_missing_required_slot_raises():
    with pytest.raises(MissingSlotError) as exc_info:
        evaluate_quote(
            PAINTING_RULES,
            {"surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )
    assert exc_info.value.slot == "area_sqft"


def test_enum_out_of_options_raises():
    with pytest.raises(InvalidSlotValueError) as exc_info:
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": 1000, "surface_type": "glass", "coats": 2, "paint_brand_tier": "basic"},
        )
    assert exc_info.value.slot == "surface_type"


def test_number_below_min_raises():
    with pytest.raises(InvalidSlotValueError, match="below min"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": 5, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )


def test_number_above_max_raises():
    with pytest.raises(InvalidSlotValueError, match="above max"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": 99999, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )


def test_wrong_type_for_number_raises():
    with pytest.raises(InvalidSlotValueError, match="expected number"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": "lots", "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )


def test_bool_for_number_rejected():
    with pytest.raises(InvalidSlotValueError, match="expected number"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": True, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )


def test_wrong_type_for_integer_raises():
    with pytest.raises(InvalidSlotValueError, match="expected integer"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": 1000, "surface_type": "new_wall", "coats": 2.5, "paint_brand_tier": "basic"},
        )


def test_bool_for_integer_rejected():
    with pytest.raises(InvalidSlotValueError, match="expected integer"):
        evaluate_quote(
            PAINTING_RULES,
            {"area_sqft": 1000, "surface_type": "new_wall", "coats": True, "paint_brand_tier": "basic"},
        )


def test_rate_not_found_raises():
    # Drop all basic-tier rates; then query with basic tier.
    rules = copy.deepcopy(PAINTING_RULES)
    rules["rate_table"] = [
        e for e in rules["rate_table"] if e["conditions"]["paint_brand_tier"] != "basic"
    ]
    with pytest.raises(RateNotFoundError):
        evaluate_quote(
            rules,
            {"area_sqft": 1000, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
        )


# ---------------------------------------------------------------------------
# String-typed input + non-required-with-no-default branch
# ---------------------------------------------------------------------------
def test_string_input_type():
    rules = copy.deepcopy(PAINTING_RULES)
    rules["inputs"].append(
        {"name": "notes", "type": "string", "required": False, "question_template": "Any notes?"}
    )
    q = evaluate_quote(
        rules,
        {
            "area_sqft": 1000,
            "surface_type": "new_wall",
            "coats": 2,
            "paint_brand_tier": "basic",
            "notes": "interior only",
        },
    )
    assert q.subtotal == Decimal("14000.00")


def test_string_input_wrong_type_raises():
    rules = copy.deepcopy(PAINTING_RULES)
    rules["inputs"].append(
        {"name": "notes", "type": "string", "required": False, "question_template": "Any notes?"}
    )
    with pytest.raises(InvalidSlotValueError, match="expected string"):
        evaluate_quote(
            rules,
            {
                "area_sqft": 1000,
                "surface_type": "new_wall",
                "coats": 2,
                "paint_brand_tier": "basic",
                "notes": 123,
            },
        )


def test_optional_input_absent_no_default_is_skipped():
    rules = copy.deepcopy(PAINTING_RULES)
    rules["inputs"].append(
        {"name": "notes", "type": "string", "required": False, "question_template": "Any notes?"}
    )
    q = evaluate_quote(
        rules,
        {"area_sqft": 1000, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
    )
    assert q.subtotal == Decimal("14000.00")


# ---------------------------------------------------------------------------
# Modifier condition operator coverage
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "op, coats_value, baseline, triggers",
    [
        ("gt", 3, 2, True),
        ("gt", 2, 2, False),
        ("gte", 2, 2, True),
        ("gte", 1, 2, False),
        ("lt", 1, 2, True),
        ("lt", 2, 2, False),
        ("lte", 2, 2, True),
        ("lte", 3, 2, False),
        ("eq", 2, 2, True),
        ("eq", 3, 2, False),
    ],
)
def test_modifier_condition_operators(op, coats_value, baseline, triggers):
    rules = copy.deepcopy(PAINTING_RULES)
    # Configure a surcharge that fires via the given op.
    rules["modifiers"] = [
        {
            "name": "test_mod",
            "type": "per_unit_surcharge",
            "condition": {"field": "coats", "op": op, "value": baseline},
            "over_field": "coats",
            "over_baseline": 0,
            "amount_per_sqft_per_extra_unit": 1,
            "quantity_field": "area_sqft",
        }
    ]
    q = evaluate_quote(
        rules,
        {
            "area_sqft": 1000,
            "surface_type": "new_wall",
            "coats": coats_value,
            "paint_brand_tier": "basic",
        },
    )
    expected_delta = Decimal(coats_value * 1000) if triggers else Decimal("0")
    assert q.subtotal == (Decimal("14000") + expected_delta).quantize(Decimal("0.01"))


def test_modifier_condition_missing_field_not_met():
    # Surcharge conditioned on a field that isn't in resolved slots -> no-op.
    rules = copy.deepcopy(PAINTING_RULES)
    rules["modifiers"] = [
        {
            "name": "ghost",
            "type": "per_unit_surcharge",
            "condition": {"field": "nonexistent", "op": "gt", "value": 0},
            "over_field": "coats",
            "over_baseline": 0,
            "amount_per_sqft_per_extra_unit": 10,
            "quantity_field": "area_sqft",
        }
    ]
    q = evaluate_quote(
        rules,
        {"area_sqft": 1000, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
    )
    assert q.subtotal == Decimal("14000.00")


# ---------------------------------------------------------------------------
# validate_slot_value (public surface used by SlotExtractor)
# ---------------------------------------------------------------------------
def test_validate_slot_value_number_valid():
    idef = InputDef(name="area_sqft", type="number", validation={"min": 10, "max": 10000})
    assert validate_slot_value(idef, 500) == 500


def test_validate_slot_value_enum_valid():
    idef = InputDef(name="surface_type", type="enum", options=["new_wall", "repaint_good_condition"])
    assert validate_slot_value(idef, "new_wall") == "new_wall"


def test_validate_slot_value_enum_invalid():
    idef = InputDef(name="surface_type", type="enum", options=["new_wall"])
    with pytest.raises(InvalidSlotValueError):
        validate_slot_value(idef, "marble")


def test_validate_slot_value_number_below_min():
    idef = InputDef(name="area_sqft", type="number", validation={"min": 10, "max": 10000})
    with pytest.raises(InvalidSlotValueError):
        validate_slot_value(idef, 5)
