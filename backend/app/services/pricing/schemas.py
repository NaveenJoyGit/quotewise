"""Pydantic schemas that validate PricingConfig.rules JSON.

Mirrors the shape documented in SPEC §3.2 but with a *structured* modifier
grammar so the evaluator stays fully deterministic (no string-trigger parsing).
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

InputType = Literal["number", "integer", "enum", "string"]


class InputValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: float | None = None
    max: float | None = None


class InputDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: InputType
    required: bool = True
    default: object | None = None
    options: list[str] | None = None
    validation: InputValidation | None = None
    question_template: str | None = None

    @field_validator("options")
    @classmethod
    def _enum_has_options(cls, v, info):
        # Enum inputs must supply options. Validator only checks the list
        # content; cross-field enforcement happens in PricingRules.
        if v is not None and len(v) == 0:
            raise ValueError("options must be non-empty when provided")
        return v


class RateTableEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conditions: dict[str, object] = Field(..., min_length=1)
    base_rate: float


Op = Literal["gt", "gte", "lt", "lte", "eq"]


class ModifierCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    op: Op
    value: float


class PerUnitSurcharge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: Literal["per_unit_surcharge"]
    condition: ModifierCondition
    over_field: str
    over_baseline: float
    amount_per_extra_unit: float
    quantity_field: str = "quantity"


class TaxModifier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: Literal["tax"]
    rate: float


Modifier = Annotated[Union[PerUnitSurcharge, TaxModifier], Field(discriminator="type")]


class LineItemTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    quantity_field: str
    unit: str
    rate_source: Literal["computed_rate"] = "computed_rate"


class PricingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    base_formula: str
    inputs: list[InputDef] = Field(..., min_length=1)
    rate_table: list[RateTableEntry] = Field(..., min_length=1)
    modifiers: list[Modifier] = Field(default_factory=list)
    line_item_template: list[LineItemTemplate] = Field(..., min_length=1)

    @field_validator("inputs")
    @classmethod
    def _enum_inputs_have_options(cls, inputs: list[InputDef]) -> list[InputDef]:
        for i in inputs:
            if i.type == "enum" and not i.options:
                raise ValueError(f"enum input {i.name!r} missing non-empty options")
        return inputs
