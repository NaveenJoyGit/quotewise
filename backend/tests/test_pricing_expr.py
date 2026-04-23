from decimal import Decimal

import pytest

from app.services.pricing.expr import safe_eval


def test_success_criterion_expression():
    assert safe_eval("area_sqft * rate_per_sqft", {"area_sqft": 1000, "rate_per_sqft": 14}) == Decimal("14000")


@pytest.mark.parametrize(
    "expr, env, expected",
    [
        ("a + b", {"a": 3, "b": 4}, Decimal("7")),
        ("a - b", {"a": 10, "b": 4}, Decimal("6")),
        ("a * b", {"a": 5, "b": 6}, Decimal("30")),
        ("a / b", {"a": 9, "b": 3}, Decimal("3")),
        ("-a", {"a": 5}, Decimal("-5")),
        ("(a + b) * c", {"a": 1, "b": 2, "c": 4}, Decimal("12")),
    ],
)
def test_allowed_ops(expr, env, expected):
    assert safe_eval(expr, env) == expected


def test_numeric_constant_float_converted_via_str():
    # 0.1 as float rounds — we go via str() to preserve the decimal form.
    assert safe_eval("0.1 + 0.2", {}) == Decimal("0.1") + Decimal("0.2")


def test_syntax_error_raises():
    with pytest.raises(ValueError, match="invalid expression syntax"):
        safe_eval("a +", {"a": 1})


def test_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown name"):
        safe_eval("x + y", {"x": 1})


def test_non_numeric_name_raises():
    with pytest.raises(ValueError, match="non-numeric"):
        safe_eval("x", {"x": "hello"})


def test_bool_name_rejected():
    with pytest.raises(ValueError, match="non-numeric"):
        safe_eval("x", {"x": True})


def test_non_numeric_constant_raises():
    with pytest.raises(ValueError, match="only numeric literals allowed"):
        safe_eval("'foo'", {})


def test_bool_constant_rejected():
    with pytest.raises(ValueError, match="only numeric literals allowed"):
        safe_eval("True", {})


def test_function_call_rejected():
    with pytest.raises(ValueError, match="Call not allowed"):
        safe_eval("abs(a)", {"a": -1})


def test_attribute_access_rejected():
    with pytest.raises(ValueError, match="Attribute not allowed"):
        safe_eval("a.b", {"a": 1})


def test_subscript_rejected():
    with pytest.raises(ValueError, match="Subscript not allowed"):
        safe_eval("a[0]", {"a": 1})


def test_disallowed_operator_mod():
    with pytest.raises(ValueError, match="Mod not allowed"):
        safe_eval("a % b", {"a": 5, "b": 2})


def test_disallowed_operator_pow():
    with pytest.raises(ValueError, match="Pow not allowed"):
        safe_eval("a ** b", {"a": 2, "b": 3})
