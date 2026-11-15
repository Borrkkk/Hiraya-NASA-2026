import pytest

from spherex_inspect import config
from spherex_inspect.intake import IntakeError, parse_coord, parse_time, to_target
from spherex_inspect.models import InspectRequest


def test_degrees():
    p = parse_coord(269.452, 4.6933)
    assert p.ra == pytest.approx(269.452) and p.dec == pytest.approx(4.6933)


def test_numeric_strings():
    p = parse_coord("269.452", "-4.5")
    assert p.ra == pytest.approx(269.452) and p.dec == pytest.approx(-4.5)


@pytest.mark.parametrize("ra,dec", [("08h55m10.831s", "-07d14m42.53s"), ("08:55:10.831", "-07:14:42.53"), ("08 55 10.831", "-07 14 42.53")])
def test_sexagesimal_wise0855(ra, dec):
    p = parse_coord(ra, dec)
    assert p.ra == pytest.approx(133.79513, abs=1e-4)
    assert p.dec == pytest.approx(-7.24515, abs=1e-4)


def test_ra_wraps():
    assert parse_coord(-10, 0).ra == pytest.approx(350)


@pytest.mark.parametrize("ra,dec", [("abc", "1"), (10, 95)])
def test_bad_coord(ra, dec):
    with pytest.raises(IntakeError):
        parse_coord(ra, dec)


def test_time_mjd_and_iso():
    assert parse_time(61000.5) == 61000.5
    assert parse_time("61000.5") == 61000.5
    assert parse_time("2025-09-01") == pytest.approx(60919.0)
    assert parse_time(None) is None and parse_time("") is None
    with pytest.raises(IntakeError):
        parse_time("not a date")


def test_defaults():
    t = to_target(InspectRequest(ra=1, dec=2))
    assert t.bands == [1, 2, 3, 4, 5, 6]
    assert t.cutout_size_deg == config.DEFAULT_CUTOUT_SIZE_DEG
    assert t.max_frames == config.DEFAULT_MAX_FRAMES
    assert t.time_range.start is None and t.time_range.end is None


def test_bands_dedup_sorted():
    assert to_target(InspectRequest(ra=1, dec=2, bands=[6, 1, 1])).bands == [1, 6]


@pytest.mark.parametrize(
    "kw",
    [
        {"bands": [0]},
        {"bands": [7]},
        {"cutout_size_deg": 0.5},
        {"cutout_size_deg": 0},
        {"max_frames": 0},
        {"time_start": 61001, "time_end": 61000},
    ],
)
def test_invalid(kw):
    with pytest.raises(IntakeError):
        to_target(InspectRequest(ra=1, dec=2, **kw))
