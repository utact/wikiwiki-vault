"""A subset of DMN 1.3 FEEL for checking conditions, limits, decision tables and literal expressions.

Unary tests: "-", comparisons such as "< 50" and "<= 113500", equality such as "120" or "\"정년\"", intervals such as "[1..3)" or "[0..기초일액]", lists separated by commas, and not(...).

Values: numbers, strings, date("2026-01-01"), duration("P60D"), true and false.

Expressions: arithmetic, comparisons, and, or, if then else, lists, names, .year, .month and .day, and the functions in FUNCTIONS.
"""

import re
from fractions import Fraction

INFINITY = None
NUMBER, STRING, BOOLEAN, DATE = "number", "string", "boolean", "date"
DAYS, MONTHS = "days and time duration", "years and months duration"


class FeelError(ValueError):
    pass


VALUE = re.compile(
    r'\s*(?:(?P<number>-?\d+(?:\.\d+)?)|"(?P<string>[^"]*)"|date\(\s*"(?P<date>\d{4}-\d{2}-\d{2})"\s*\)'
    r'|duration\(\s*"(?P<duration>-?P(?:\d+Y)?(?:\d+M)?(?:\d+W)?(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?)"\s*\)|(?P<boolean>true|false))\s*'
)
COMPARISON = re.compile(r"\s*(<=|>=|!=|<|>|=)?")
INTERVAL = re.compile(r"\s*([\[(\]])(.+?)\.\.(.+?)([\])\[])\s*$")
DURATION_PART = re.compile(r"(\d+)([YMWDHS])")


def duration(text):
    """(type, size) of an ISO 8601 duration: months for years and months, seconds for days and time."""
    sign = -1 if text.startswith("-") else 1
    body = text.lstrip("-")[1:]
    date_part, _, time_part = body.partition("T")
    if not body or body == "T" or (time_part == "" and body.endswith("T")):
        raise FeelError(f"empty duration: {text!r}")
    parts = DURATION_PART.findall(date_part)
    if any(unit in "YM" for _, unit in parts) and not any(unit in "WD" for _, unit in parts) and not time_part:
        return MONTHS, sign * sum(int(n) * (12 if unit == "Y" else 1) for n, unit in parts)
    if any(unit in "YM" for _, unit in parts):
        raise FeelError(f"duration mixes years or months with days: {text!r}")
    seconds = sum(int(n) * {"W": 604800, "D": 86400}[unit] for n, unit in parts)
    seconds += sum(int(n) * {"H": 3600, "M": 60, "S": 1}[unit] for n, unit in DURATION_PART.findall(time_part))
    return DAYS, sign * seconds


def value(text):
    """(type, value) of a FEEL value; durations become comparable sizes."""
    match = VALUE.fullmatch(text)
    if not match:
        raise FeelError(f"not a FEEL value: {text!r}")
    if match["number"] is not None:
        return NUMBER, Fraction(match["number"])
    if match["string"] is not None:
        return STRING, match["string"]
    if match["date"]:
        return DATE, match["date"]
    if match["duration"]:
        return duration(match["duration"])
    return BOOLEAN, match["boolean"] == "true"


def split(text):
    """Items of a comma-separated list, keeping commas inside quotes and brackets."""
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


def bound(text):
    """(type, value) of an interval bound or comparison operand: a value, or ("expression", text) for a name or calculation."""
    try:
        return value(text)
    except FeelError:
        if not re.search(r"[A-Za-z가-힣]", text):
            raise
        parse(text)
        return "expression", text.strip()


def unary_tests(text):
    """Parse unary tests into (negated, [(type, low, low_closed, high, high_closed)]); None bounds are open ends.

    A test against an expression has the type "expression" and the expressions as bounds.
    """
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
            low_type, low = bound(interval.group(2))
            high_type, high = bound(interval.group(3))
            if "expression" in (low_type, high_type):
                tests.append(("expression", low if low_type == "expression" else None, interval.group(1) == "[",
                              high if high_type == "expression" else None, interval.group(4) == "]"))
                continue
            if low_type != high_type:
                raise FeelError(f"interval bounds of two types: {item!r}")
            if low > high:
                raise FeelError(f"empty interval: {item!r}")
            tests.append((low_type, low, interval.group(1) == "[", high, interval.group(4) == "]"))
            continue
        op = COMPARISON.match(item).group(1) or "="
        kind, operand = bound(item[COMPARISON.match(item).end():])
        if op == "!=":
            raise FeelError(f"!= is not a unary test: {item!r}")
        if kind == "expression":
            tests.append(("expression", operand, True, operand, True))
        elif op in ("<", "<="):
            tests.append((kind, INFINITY, False, operand, op == "<="))
        elif op in (">", ">="):
            tests.append((kind, operand, op == ">=", INFINITY, False))
        else:
            tests.append((kind, operand, True, operand, True))
    return negated, tests


def types(text):
    """Types that a unary test compares against, without the type of "-" and of expressions, which expression_type checks."""
    _, tests = unary_tests(text)
    return {kind for kind, *_ in tests if kind and kind != "expression"}


def expressions(text):
    """Expressions that a unary test compares against, such as 기초일액 * 80 / 100."""
    _, tests = unary_tests(text)
    found = []
    for kind, low, _, high, _ in tests:
        if kind == "expression":
            found += [e for e in dict.fromkeys((low, high)) if e]
    return found


def overlaps(a, b):
    """Whether two unary tests can both hold for one value, or None when a test compares against an expression."""
    sets = []
    for text in (a, b):
        negated, tests = unary_tests(text)
        if any(kind == "expression" for kind, *_ in tests):
            return None
        sets.append(complement(tests) if negated else tests)
    return any(meet(x, y) for x in sets[0] for y in sets[1])


def complement(tests):
    """The intervals outside a union of intervals of one type."""
    kinds = {kind for kind, *_ in tests if kind}
    if any(kind is None for kind, *_ in tests):
        return []
    if len(kinds) > 1:
        raise FeelError(f"not() over values of two types: {sorted(kinds)}")
    kind = kinds.pop()
    merged = []
    for _, low, low_closed, high, high_closed in sorted(tests, key=lambda t: (t[1] is not INFINITY, 0 if t[1] is INFINITY else t[1], not t[2])):
        if merged:
            last = merged[-1]
            if last[3] is INFINITY:
                continue
            if low is INFINITY or low < last[3] or (low == last[3] and (low_closed or last[4])):
                if high is INFINITY or high > last[3] or (high == last[3] and high_closed):
                    merged[-1] = (last[0], last[1], last[2], high, high_closed)
                continue
        merged.append((kind, low, low_closed, high, high_closed))
    found = []
    if merged[0][1] is not INFINITY:
        found.append((kind, INFINITY, False, merged[0][1], not merged[0][2]))
    for left, right in zip(merged, merged[1:]):
        found.append((kind, left[3], not left[4], right[1], not right[2]))
    if merged[-1][3] is not INFINITY:
        found.append((kind, merged[-1][3], not merged[-1][4], INFINITY, False))
    return found


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


# expressions

PHRASES = {"years and months duration": "years_and_months_duration", "round half up": "round_half_up",
           "round half down": "round_half_down", "round up": "round_up", "round down": "round_down"}
FUNCTIONS = {
    "min", "max", "sum", "mean", "count", "floor", "ceiling", "abs", "decimal", "modulo", "round_half_up",
    "round_half_down", "round_up", "round_down", "date", "duration", "years_and_months_duration", "not", "string", "number",
}
KEYWORDS = {"if", "then", "else", "and", "or", "true", "false", "null"}
TOKEN = re.compile(
    r'\s*(?:(?P<number>\d+(?:\.\d+)?)|"(?P<string>[^"]*)"|\x00(?P<name>\d+)\x00'
    r"|(?P<op><=|>=|!=|\.\.|[-+*/<>=(),.\[\]])|(?P<word>[A-Za-z가-힣_][A-Za-z가-힣_0-9]*))"
)
PROPERTIES = {DATE: {"year", "month", "day", "weekday"}, DAYS: {"days", "hours", "minutes", "seconds"}, MONTHS: {"years", "months"}}


def tokens(text, names):
    """Tokens of an expression, with each known name as one token, and runs of unknown words joined as one name."""
    for phrase, word in PHRASES.items():
        text = re.sub(rf"(?<![\w가-힣]){phrase}(?=\s*\()", word, text)
    ordered = sorted(names, key=len, reverse=True)
    for index, name in enumerate(ordered):
        text = re.sub(rf"(?<![\w가-힣]){re.escape(name)}(?![\w가-힣])", f"\x00{index}\x00", text)
    found, position = [], 0
    while position < len(text.rstrip()):
        match = TOKEN.match(text, position)
        if not match or match.end() == position:
            raise FeelError(f"unexpected text in {text!r} at {position}")
        position = match.end()
        if match["number"] is not None:
            found.append(("number", match["number"]))
        elif match["string"] is not None:
            found.append(("string", match["string"]))
        elif match["name"] is not None:
            found.append(("name", ordered[int(match["name"])]))
        elif match["op"]:
            found.append(("op", match["op"]))
        elif match["word"] in KEYWORDS or match["word"] in FUNCTIONS and TOKEN.match(text, position) and text[position:].lstrip().startswith("("):
            found.append(("word", match["word"]))
        elif found and found[-1][0] == "unknown":
            found[-1] = ("unknown", found[-1][1] + " " + match["word"])
        else:
            found.append(("unknown", match["word"]))
    return found


class Parser:
    """Recursive descent over the tokens of an expression, giving its FEEL type, or None when a name has no known type."""

    def __init__(self, text, names):
        self.text, self.names = text, names
        self.items, self.index, self.unknown = tokens(text, names), 0, []

    def peek(self, *values):
        if self.index < len(self.items) and (not values or self.items[self.index][1] in values):
            return self.items[self.index]
        return None

    def take(self, *values):
        item = self.peek(*values)
        if item is None:
            found = self.items[self.index][1] if self.index < len(self.items) else "the end"
            raise FeelError(f"expected {' or '.join(values) or 'more'} but found {found!r} in {self.text!r}")
        self.index += 1
        return item

    def parse(self):
        kind = self.expression()
        if self.index != len(self.items):
            raise FeelError(f"unexpected {self.items[self.index][1]!r} in {self.text!r}")
        return kind

    def expression(self):
        if self.peek("if"):
            self.take("if")
            condition = self.expression()
            self.take("then")
            first = self.expression()
            self.take("else")
            second = self.expression()
            expect(condition, BOOLEAN, "if condition", self.text)
            if first and second and "null" not in (first, second) and first != second:
                raise FeelError(f"if branches of two types, {first} and {second}, in {self.text!r}")
            return first if first not in (None, "null") else second
        return self.disjunction()

    def disjunction(self):
        kind = self.conjunction()
        while self.peek("or"):
            self.take("or")
            expect(kind, BOOLEAN, "or", self.text)
            expect(self.conjunction(), BOOLEAN, "or", self.text)
            kind = BOOLEAN
        return kind

    def conjunction(self):
        kind = self.comparison()
        while self.peek("and"):
            self.take("and")
            expect(kind, BOOLEAN, "and", self.text)
            expect(self.comparison(), BOOLEAN, "and", self.text)
            kind = BOOLEAN
        return kind

    def comparison(self):
        kind = self.sum()
        if self.peek("<=", ">=", "!=", "<", ">", "="):
            op = self.take()[1]
            other = self.sum()
            if kind and other and "null" not in (kind, other) and kind != other:
                raise FeelError(f"{op} compares {kind} with {other} in {self.text!r}")
            return BOOLEAN
        return kind

    def sum(self):
        kind = self.product()
        while self.peek("+", "-"):
            op = self.take()[1]
            kind = arithmetic(op, kind, self.product(), self.text)
        return kind

    def product(self):
        kind = self.unary()
        while self.peek("*", "/"):
            op = self.take()[1]
            kind = arithmetic(op, kind, self.unary(), self.text)
        return kind

    def unary(self):
        if self.peek("-"):
            self.take("-")
            kind = self.unary()
            if kind not in (None, NUMBER, DAYS, MONTHS):
                raise FeelError(f"- before {kind} in {self.text!r}")
            return kind
        return self.postfix()

    def postfix(self):
        kind = self.primary()
        while self.peek("."):
            self.take(".")
            item = self.take()
            if kind is not None and item[1] not in PROPERTIES.get(kind, ()):
                raise FeelError(f"{kind} has no property {item[1]!r} in {self.text!r}")
            kind = NUMBER
        return kind

    def primary(self):
        item = self.take()
        sort, text = item
        if sort == "number":
            return NUMBER
        if sort == "string":
            return STRING
        if sort == "name":
            return self.names[text]
        if sort == "unknown":
            self.unknown.append(text)
            return None
        if text in ("true", "false"):
            return BOOLEAN
        if text == "null":
            return "null"
        if text == "(":
            kind = self.expression()
            self.take(")")
            return kind
        if text == "[":
            kinds = []
            if not self.peek("]"):
                kinds.append(self.expression())
                while self.peek(","):
                    self.take(",")
                    kinds.append(self.expression())
            self.take("]")
            known = {k for k in kinds if k}
            if len(known) > 1:
                raise FeelError(f"list of {sorted(known)} in {self.text!r}")
            return "list of " + known.pop() if known else "list"
        if sort == "word" and text in FUNCTIONS:
            return self.call(text)
        raise FeelError(f"unexpected {text!r} in {self.text!r}")

    def call(self, function):
        start = self.index
        self.take("(")
        arguments = []
        if not self.peek(")"):
            arguments.append(self.expression())
            while self.peek(","):
                self.take(",")
                arguments.append(self.expression())
        self.take(")")
        literal = [t for _, t in self.items[start + 1: self.index - 1]]
        return function_type(function, arguments, literal, self.text)


def expect(kind, wanted, where, text):
    if kind is not None and kind != wanted:
        raise FeelError(f"{where} needs {wanted}, not {kind}, in {text!r}")


def arithmetic(op, a, b, text):
    """Type of a + b, a - b, a * b or a / b."""
    if a is None or b is None:
        return None
    durations = (DAYS, MONTHS)
    if a == b == NUMBER:
        return NUMBER
    if op in "+-":
        if a == b and a in durations:
            return a
        if a == DATE and b in durations:
            return DATE
        if op == "+" and b == DATE and a in durations:
            return DATE
        if op == "-" and a == b == DATE:
            return DAYS
    if op == "*" and {a, b} in ({NUMBER, DAYS}, {NUMBER, MONTHS}):
        return a if a != NUMBER else b
    if op == "/" and a in durations and b == NUMBER:
        return a
    if op == "/" and a == b and a in durations:
        return NUMBER
    raise FeelError(f"{a} {op} {b} in {text!r}")


def function_type(function, arguments, literal, text):
    known = [a for a in arguments if a]
    if function in ("min", "max", "sum", "mean"):
        items = [a.removeprefix("list of ") for a in known]
        if len(set(items)) > 1:
            raise FeelError(f"{function} over {sorted(set(items))} in {text!r}")
        kind = items[0] if items else None
        if function in ("sum", "mean") and kind not in (None, NUMBER, DAYS, MONTHS):
            raise FeelError(f"{function} over {kind} in {text!r}")
        return None if kind == "list" else kind
    if function == "count":
        return NUMBER
    if function in ("floor", "ceiling", "abs", "decimal", "modulo", "round_half_up", "round_half_down", "round_up", "round_down"):
        for kind in known:
            if kind != NUMBER:
                raise FeelError(f"{function} of {kind} in {text!r}")
        return NUMBER
    if function == "date":
        if len(literal) == 1 and arguments == [STRING]:
            value(f'date("{literal[0]}")')
        elif len(arguments) == 3:
            for kind in known:
                if kind != NUMBER:
                    raise FeelError(f"date of {kind} in {text!r}")
        return DATE
    if function == "duration":
        if len(literal) == 1 and arguments == [STRING]:
            return duration(literal[0])[0]
        return None
    if function == "years_and_months_duration":
        for kind in known:
            if kind != DATE:
                raise FeelError(f"years and months duration of {kind} in {text!r}")
        return MONTHS
    if function == "not":
        for kind in known:
            if kind != BOOLEAN:
                raise FeelError(f"not of {kind} in {text!r}")
        return BOOLEAN
    return STRING if function == "string" else NUMBER


def parse(text, names=None):
    """The FEEL type of an expression, given the types of the names it may use; None when it depends on an unknown name."""
    parser = Parser(text, dict(names or {}))
    return parser.parse()


def expression_type(text, names):
    """(type, unknown names) of an expression; the type is None when it depends on an unknown name."""
    parser = Parser(text, dict(names))
    kind = parser.parse()
    return kind, parser.unknown


def unknown_names(expression, names):
    """Names in an expression that are neither the given names nor FEEL functions and keywords."""
    return expression_type(expression, {name: None for name in names})[1]
