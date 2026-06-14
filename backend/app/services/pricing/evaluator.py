"""Pure deterministic pricing evaluator.

No I/O, no LLM, no randomness. Given a PricingConfig.rules dict + a dict of
filled slot values, returns line items, subtotal, tax, total.

SPEC §2.2 / §4.2 — "never ask an LLM to multiply two numbers".
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.services.pricing.errors import (
    InvalidSlotValueError,
    MissingSlotError,
    RateNotFoundError,
)
from app.services.pricing.expr import safe_eval
from app.services.pricing.schemas import (
    InputDef,
    ModifierCondition,
    PerUnitSurcharge,
    PricingRules,
    TaxModifier,
)

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class EvaluatedLineItem:
    description: str
    quantity: Decimal
    unit: str
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class EvaluatedQuote:
    line_items: list[EvaluatedLineItem]
    subtotal: Decimal
    gst_amount: Decimal
    total: Decimal
    confidence_score: float


def evaluate_quote(rules: dict, slots: dict) -> EvaluatedQuote:
    parsed = PricingRules.model_validate(rules)

    resolved = _resolve_slots(parsed.inputs, slots)

    rate = _lookup_rate(parsed.rate_table, resolved)

    env = {**_numeric_env(resolved), "base_rate": float(rate)}
    per_unit_base = safe_eval(parsed.base_formula, env)
    # base_formula yields the "per matched combination" amount; we treat its
    # numeric result as the subtotal contribution from the primary line item.
    subtotal = _money(per_unit_base)

    # Apply non-tax modifiers (surcharges) before tax.
    for mod in parsed.modifiers:
        if isinstance(mod, PerUnitSurcharge):
            subtotal += _apply_surcharge(mod, resolved)

    subtotal = _money(subtotal)

    # Tax applies to subtotal after surcharges.
    gst_amount = Decimal("0")
    for mod in parsed.modifiers:
        if isinstance(mod, TaxModifier):
            gst_amount += subtotal * Decimal(str(mod.rate))
    gst_amount = _money(gst_amount)

    total = _money(subtotal + gst_amount)

    line_items = _render_line_items(
        parsed.line_item_template, resolved, rate, subtotal
    )

    return EvaluatedQuote(
        line_items=line_items,
        subtotal=subtotal,
        gst_amount=gst_amount,
        total=total,
        confidence_score=1.0,
    )


def _resolve_slots(inputs: list[InputDef], slots: dict) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for i in inputs:
        if i.name in slots:
            value = slots[i.name]
        elif i.default is not None:
            value = i.default
        elif i.required:
            raise MissingSlotError(i.name)
        else:
            continue
        resolved[i.name] = validate_slot_value(i, value)
    return resolved


def validate_slot_value(i: InputDef, value: Any) -> Any:
    if i.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidSlotValueError(i.name, value, "expected integer")
        _check_range(i, value)
        return value
    if i.type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidSlotValueError(i.name, value, "expected number")
        _check_range(i, value)
        return value
    if i.type == "enum":
        if value not in (i.options or []):
            raise InvalidSlotValueError(
                i.name, value, f"not one of {i.options}"
            )
        return value
    if i.type == "string":
        if not isinstance(value, str):
            raise InvalidSlotValueError(i.name, value, "expected string")
        return value
    raise InvalidSlotValueError(i.name, value, f"unsupported input type {i.type}")  # pragma: no cover


def _check_range(i: InputDef, value: float) -> None:
    v = i.validation
    if v is None:
        return
    if v.min is not None and value < v.min:
        raise InvalidSlotValueError(i.name, value, f"below min {v.min}")
    if v.max is not None and value > v.max:
        raise InvalidSlotValueError(i.name, value, f"above max {v.max}")


def _lookup_rate(rate_table, resolved: dict) -> Decimal:
    for entry in rate_table:
        if all(resolved.get(k) == v for k, v in entry.conditions.items()):
            return Decimal(str(entry.base_rate))
    raise RateNotFoundError(resolved)


def _numeric_env(resolved: dict) -> dict[str, float]:
    return {k: v for k, v in resolved.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _apply_surcharge(mod: PerUnitSurcharge, resolved: dict) -> Decimal:
    if not _condition_met(mod.condition, resolved):
        return Decimal("0")
    over = Decimal(str(resolved[mod.over_field])) - Decimal(str(mod.over_baseline))
    per_sqft = Decimal(str(mod.amount_per_extra_unit))
    qty = Decimal(str(resolved[mod.quantity_field]))
    return over * per_sqft * qty


def _condition_met(cond: ModifierCondition, resolved: dict) -> bool:
    lhs = resolved.get(cond.field)
    if lhs is None:
        return False
    rhs = cond.value
    if cond.op == "gt":
        return lhs > rhs
    if cond.op == "gte":
        return lhs >= rhs
    if cond.op == "lt":
        return lhs < rhs
    if cond.op == "lte":
        return lhs <= rhs
    return lhs == rhs  # eq — only remaining Op literal


def _render_line_items(
    templates, resolved: dict, rate: Decimal, subtotal: Decimal
) -> list[EvaluatedLineItem]:
    items: list[EvaluatedLineItem] = []
    for t in templates:
        description = t.description.format(**{**resolved, "computed_rate": rate})
        qty = Decimal(str(resolved[t.quantity_field]))
        amount = _money(qty * rate)
        items.append(
            EvaluatedLineItem(
                description=description,
                quantity=qty,
                unit=t.unit,
                rate=rate,
                amount=amount,
            )
        )
    # Replace the first line item's amount with the subtotal to absorb surcharges.
    if items:
        first = items[0]
        items[0] = EvaluatedLineItem(
            description=first.description,
            quantity=first.quantity,
            unit=first.unit,
            rate=first.rate,
            amount=subtotal,
        )
    return items


def _money(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_CENTS, rounding=ROUND_HALF_UP)
