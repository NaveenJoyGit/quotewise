import copy

import pytest
from pydantic import ValidationError

from app.services.pricing.schemas import PricingRules
from app.services.pricing.seed_rules import PAINTING_RULES


def test_painting_rules_parse():
    PricingRules.model_validate(PAINTING_RULES)


def test_missing_base_formula_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    del bad["base_formula"]
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_rate_table_entry_with_empty_conditions_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    bad["rate_table"][0]["conditions"] = {}
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_empty_rate_table_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    bad["rate_table"] = []
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_unknown_modifier_type_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    bad["modifiers"].append({"name": "weird", "type": "magic_discount", "rate": 0.5})
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_enum_input_without_options_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    # Find the surface_type enum input and strip its options.
    for i in bad["inputs"]:
        if i["name"] == "surface_type":
            i["options"] = None
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_enum_input_with_empty_options_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    for i in bad["inputs"]:
        if i["name"] == "surface_type":
            i["options"] = []
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)


def test_unknown_top_level_key_rejected():
    bad = copy.deepcopy(PAINTING_RULES)
    bad["unexpected_field"] = "oops"
    with pytest.raises(ValidationError):
        PricingRules.model_validate(bad)
