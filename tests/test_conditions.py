from decimal import Decimal

import pytest
from pydantic import ValidationError

from modular_data_ci.conditions import Condition, Tolerance


@pytest.mark.parametrize(
    ("text", "operator", "value"),
    [
        ("> 0", ">", 0.0),
        ("==100", "==", 100.0),
        (" <= -2.5 ", "<=", -2.5),
        ("!= 1e3", "!=", 1000.0),
    ],
)
def test_shorthand_is_parsed(text, operator, value):
    condition = Condition.model_validate(text)
    assert condition.operator == operator
    assert condition.value == value
    assert condition.tolerance is None


@pytest.mark.parametrize("text", ["", "0", "> abc", "=> 1", "> 1 2"])
def test_invalid_shorthand_is_rejected(text):
    with pytest.raises(ValidationError, match="invalid condition"):
        Condition.model_validate(text)


@pytest.mark.parametrize(
    ("operator", "actual", "expected"),
    [
        ("==", 10, True),
        ("==", 11, False),
        ("!=", 11, True),
        (">", 11, True),
        (">", 10, False),
        (">=", 10, True),
        ("<", 9, True),
        ("<=", 10, True),
        ("<=", 11, False),
    ],
)
def test_evaluate_without_tolerance(operator, actual, expected):
    assert Condition(operator=operator, value=10).evaluate(actual) is expected


def test_relative_tolerance_on_equality():
    condition = Condition(operator="==", value=1000, tolerance=Tolerance(relative=0.05))
    assert condition.evaluate(1049)
    assert condition.evaluate(951)
    assert not condition.evaluate(1051)


def test_larger_allowance_wins():
    tolerance = Tolerance(absolute=10, relative=0.01)
    assert tolerance.allowance(100) == 10
    assert tolerance.allowance(10_000) == 100


def test_tolerance_relaxes_inequalities():
    condition = Condition(operator=">", value=100, tolerance=Tolerance(absolute=5))
    assert condition.evaluate(96)
    assert not condition.evaluate(95)


@pytest.mark.parametrize("actual", [None, float("nan"), True])
def test_missing_or_non_numeric_values_never_pass(actual):
    assert not Condition(operator=">=", value=0).evaluate(actual)


def test_decimal_values_are_supported():
    assert Condition(operator="==", value=1.5).evaluate(Decimal("1.5"))


def test_tolerance_requires_a_value():
    with pytest.raises(ValidationError, match="absolute"):
        Tolerance()


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValidationError):
        Tolerance(absolute=-1)


def test_unknown_operator_is_rejected():
    with pytest.raises(ValidationError):
        Condition(operator="~=", value=1)


def test_describe():
    assert Condition.model_validate("> 0").describe() == "> 0"
    with_tol = Condition(operator="==", value=100, tolerance=Tolerance(relative=0.1))
    assert with_tol.describe() == "== 100 (tolerance ±10)"
