"""Tests for scripts/feel.py: unary tests, overlaps and expression types."""

import pytest

import feel

NAMES = {"기초일액": "number", "이직일": "date", "피보험기간": "number", "수급기간": "days and time duration", "정년 여부": "boolean"}


@pytest.mark.parametrize("a, b, expected", [
    ("< 50", "[50..60)", False),
    ("<= 50", "[50..60)", True),
    ("[1..3)", "[3..5)", False),
    ("not(< 50)", "< 50", False),
    ("not(< 50)", "50", True),
    ("not([1..3), [5..7))", "[3..5)", True),
    ("not([1..3), [5..7))", "2", False),
    ("not(\"정년\")", "\"정년\"", False),
    ("-", "120", True),
    ("not(1, 2)", "3", True),
    ("not(1, 2)", "2", False),
])
def test_overlaps(a, b, expected):
    assert feel.overlaps(a, b) is expected


def test_durations_compare_by_size():
    assert feel.overlaps('> duration("P60D")', 'duration("P100D")')
    assert not feel.overlaps('< duration("P60D")', 'duration("P100D")')
    assert feel.overlaps('< duration("P1Y")', 'duration("P11M")')
    assert feel.types('duration("P60D")') == {"days and time duration"}
    assert feel.types('duration("P2Y")') == {"years and months duration"}


def test_interval_bounds_may_be_names():
    assert feel.expressions("[0..기초일액]") == ["기초일액"]
    assert feel.overlaps("[0..기초일액]", "0") is None


def test_unary_test_errors():
    for text in ("[3..1]", "!= 3", "", "[1..\"a\"]"):
        with pytest.raises(feel.FeelError):
            feel.unary_tests(text)


@pytest.mark.parametrize("text, expected", [
    ("기초일액 * 60 / 100", "number"),
    ("min(기초일액, 66000)", "number"),
    ("if 정년 여부 then 120 else 150", "number"),
    ("이직일 + duration(\"P12M\")", "date"),
    ("이직일 - date(\"2026-01-01\")", "days and time duration"),
    ("date(이직일.year, 1, 1)", "date"),
    ("이직일 >= date(\"2026-01-01\") and 기초일액 > 0", "boolean"),
    ("floor(기초일액 * 0.8)", "number"),
    ("수급기간 / duration(\"P1D\")", "number"),
])
def test_expression_types(text, expected):
    assert feel.expression_type(text, NAMES) == (expected, [])


@pytest.mark.parametrize("text", [
    "기초일액 + 이직일",
    "if 기초일액 then 1 else 2",
    "if 정년 여부 then 120 else \"없음\"",
    "이직일 > 3",
    "floor(이직일)",
    "기초일액 *",
    "min(기초일액, 이직일)",
    "date(\"2026-13-01\")",
    "date(\"2026-02-30\")",
    "duration(\"P1W\")",
    "\"a\" + 1",
])
def test_expression_type_errors(text):
    with pytest.raises(feel.FeelError):
        feel.expression_type(text, NAMES)


def test_unknown_names_are_reported():
    assert feel.unknown_names("min(기초일액, 상한 금액)", ["기초일액"]) == ["상한 금액"]
    assert feel.unknown_names("years and months duration(이직일, 이직일)", ["이직일"]) == []


def test_dates_are_discrete():
    assert not feel.overlaps('> date("2025-12-31")', '< date("2026-01-01")')
    assert feel.overlaps('>= date("2025-12-31")', '< date("2026-01-01")')


def test_values_that_are_not_valid():
    for text in ('date("2026-13-01")', 'date("2026-02-30")', 'duration("P1W")', 'duration("PT")'):
        with pytest.raises(feel.FeelError):
            feel.unary_tests(text)


@pytest.mark.parametrize("text, expected", [
    ("2 ** 3", "number"),
    ("\"고용\" + \"보험\"", "string"),
    ("date and time(\"2026-01-01T09:00:00\") + duration(\"PT8H\")", "date and time"),
    ("date and time(\"2026-01-01T09:00:00\").hour", "number"),
])
def test_more_expression_types(text, expected):
    assert feel.expression_type(text, NAMES) == (expected, [])
