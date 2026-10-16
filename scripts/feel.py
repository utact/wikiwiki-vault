"""A subset of DMN 1.3 FEEL for checking conditions, limits and decision tables.

Unary tests: "-", comparisons such as "< 50" and "<= 113500", equality such as "120" or "\"정년\"", intervals such as "[1..3)", lists separated by commas, and not(...).

Values: numbers, strings, date("2026-01-01"), duration("P60D"), true and false.
"""

import re
from fractions import Fraction

INFINITY = None


class FeelError(ValueError):
    pass


VALUE = re.compile(
    r'\s*(?:(?P<number>-?\d+(?:\.\d+)?)|"(?P<string>[^"]*)"|date\(\s*"(?P<date>\d{4}-\d{2}-\d{2})"\s*\)'
    r'|duration\(\s*"(?P<duration>P[0-9YMWDTHS]+)"\s*\)|(?P<boolean>true|false))\s*'
)
COMPARISON = re.compile(r"\s*(<=|>=|!=|<|>|=)?")
INTERVAL = re.compile(r"\s*([\[(\]])(.+?)\.\.(.+?)([\])\[])\s*$")


def value(text):
    """(type, value) of a FEEL value."""
    match = VALUE.fullmatch(text)
    if not match:
        raise FeelError(f"not a FEEL value: {text!r}")
    if match["number"] is not None:
        return "number", Fraction(match["number"])
    if match["string"] is not None:
        return "string", match["string"]
    if match["date"]:
        return "date", match["date"]
    if match["duration"]:
        unit = "years and months duration" if re.fullmatch(r"P\d+[YM](\d+M)?", match["duration"]) else "days and time duration"
        return unit, match["duration"]
    return "boolean", match["boolean"] == "true"


def split(text):
    """Items of a comma-separated list, keeping commas inside quotes and parentheses."""
    items, depth, quoted, start = [], 0, False, 0
    for index, ch in enumerate(text):
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in "([":
            depth += 1
        elif not quoted and ch in ")]" and depth:
            depth -= 1
        elif not quoted and not depth and ch == ",":
            items.append(text[start:index])
            start = index + 1
    items.append(text[start:])
    return [item.strip() for item in items]


def unary_tests(text):
    """Parse unary tests into (negated, [(type, low, low_closed, high, high_closed)]); None bounds are open ends."""
    text = text.strip()
    if text == "-":
        return False, [(None, INFINITY, False, INFINITY, False)]
    negated = False
    match = re.fullmatch(r"not\s*\((.*)\)", text, re.S)
    if match:
        negated, text = True, match.group(1)
    tests = []
    for item in split(text):
        if not item:
            raise FeelError(f"empty test in {text!r}")
        interval = INTERVAL.match(item)
        if interval and ".." in item:
            low_type, low = value(interval.group(2))
            high_type, high = value(interval.group(3))
            if low_type != high_type:
                raise FeelError(f"interval bounds of two types: {item!r}")
            if low > high:
                raise FeelError(f"empty interval: {item!r}")
            tests.append((low_type, low, interval.group(1) == "[", high, interval.group(4) == "]"))
            continue
        op = COMPARISON.match(item).group(1) or "="
        operand = item[COMPARISON.match(item).end():]
        try:
            kind, bound = value(operand)
        except FeelError:
            if not re.search(r"[A-Za-z가-힣]", operand):
                raise
            tests.append(("expression", operand.strip(), True, operand.strip(), True))
            continue
        if op in ("<", "<="):
            tests.append((kind, INFINITY, False, bound, op == "<="))
        elif op in (">", ">="):
            tests.append((kind, bound, op == ">=", INFINITY, False))
        elif op == "=":
            tests.append((kind, bound, True, bound, True))
        else:
            raise FeelError(f"!= is not a unary test: {item!r}")
    return negated, tests


def types(text):
    """Types that a unary test compares against, without the type of "-" and of expressions, which the caller checks by name."""
    _, tests = unary_tests(text)
    return {kind for kind, *_ in tests if kind and kind != "expression"}


def expressions(text):
    """Expressions that a unary test compares against, such as date(이직일.year, 1, 1)."""
    _, tests = unary_tests(text)
    return [low for kind, low, *_ in tests if kind == "expression"]


def overlaps(a, b):
    """Whether two unary tests can both hold for one value. Negated tests count as overlapping."""
    negated_a, tests_a = unary_tests(a)
    negated_b, tests_b = unary_tests(b)
    if negated_a or negated_b:
        return True
    return any(meet(x, y) for x in tests_a for y in tests_b)


def meet(x, y):
    """Whether two intervals share a value."""
    if x[0] and y[0] and x[0] != y[0]:
        return False
    low, low_closed = max_bound((x[1], x[2]), (y[1], y[2]))
    high, high_closed = min_bound((x[3], x[4]), (y[3], y[4]))
    if low is INFINITY or high is INFINITY:
        return True
    return low < high or (low == high and low_closed and high_closed)


def max_bound(a, b):
    if a[0] is INFINITY:
        return b
    if b[0] is INFINITY:
        return a
    if a[0] != b[0]:
        return a if a[0] > b[0] else b
    return a[0], a[1] and b[1]


def min_bound(a, b):
    if a[0] is INFINITY:
        return b
    if b[0] is INFINITY:
        return a
    if a[0] != b[0]:
        return a if a[0] < b[0] else b
    return a[0], a[1] and b[1]


FUNCTIONS = {"min", "max", "floor", "ceiling", "decimal", "abs", "date", "duration", "years and months duration"}


def unknown_names(expression, names):
    """Words of a literal expression that are neither input names nor FEEL functions, numbers or operators."""
    rest = expression
    for name in sorted(names, key=len, reverse=True):
        rest = re.sub(rf"(?<![\w가-힣]){re.escape(name)}(?![\w가-힣])", " ", rest)
    rest = re.sub(r'"[^"]*"', " ", rest)
    rest = re.sub(r"\.\s*(?:year|month|day)\b", " ", rest)
    words = re.findall(r"[A-Za-z가-힣_][\w가-힣 ]*?(?=\s*[(+\-*/,)<>=]|\s*$)", rest)
    return [w.strip() for w in words if w.strip() and w.strip() not in FUNCTIONS and w.strip() not in ("and", "or", "if", "then", "else")]
