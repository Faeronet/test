from app.dimension_parser import parse_dimension


def test_diameter_simple():
    r = parse_dimension("Ø40")
    assert r.kind == "diameter"
    assert r.value == 40.0
    assert r.unit == "mm"


def test_diameter_cyrillic_F():
    r = parse_dimension("Ф40")
    assert r.kind == "diameter"
    assert r.value == 40.0


def test_diameter_with_h11():
    r = parse_dimension("Ø40H11")
    assert r.kind == "diameter"
    assert r.value == 40.0
    assert r.tolerance == "H11"


def test_radius():
    r = parse_dimension("R25")
    assert r.kind == "radius"
    assert r.value == 25.0


def test_thread():
    r = parse_dimension("M12")
    assert r.kind == "thread"
    assert r.value == 12.0
    assert r.extra["thread_designator"] == "M12"


def test_thread_with_pitch():
    r = parse_dimension("M12x1.5")
    assert r.kind == "thread"
    assert r.extra["pitch"] == 1.5


def test_linear_plus_minus():
    r = parse_dimension("80±0.2")
    assert r.kind == "linear"
    assert r.value == 80.0
    assert r.tolerance == "±0.2"


def test_linear_signed():
    plus = parse_dimension("10+0.2")
    minus = parse_dimension("10-0.1")
    assert plus.tolerance == "+0.2"
    assert minus.tolerance == "-0.1"


def test_chamfer():
    for s in ("1x45°", "1×45°"):
        r = parse_dimension(s)
        assert r.kind == "chamfer"
        assert r.value == 1.0
        assert r.extra["angle_deg"] == 45.0


def test_fit_only():
    r = parse_dimension("H11")
    assert r.kind == "tolerance"
    assert r.tolerance == "H11"


def test_count_diameter_russian():
    r = parse_dimension("2 отв. Ø10")
    assert r.kind == "diameter"
    assert r.value == 10.0
    assert r.extra["count"] == 2


def test_count_diameter_english():
    r = parse_dimension("2 holes Ø10")
    assert r.kind == "diameter"
    assert r.extra["count"] == 2


def test_comma_decimal_separator():
    r = parse_dimension("10±0,2")
    assert r.kind == "linear"
    assert r.value == 10.0
    assert r.tolerance == "±0.2"


def test_value_fit():
    r = parse_dimension("40H11")
    assert r.kind == "linear"
    assert r.value == 40.0
    assert r.tolerance == "H11"


def test_unknown():
    r = parse_dimension("garbage 123 ###")
    assert r.kind == "unknown"
