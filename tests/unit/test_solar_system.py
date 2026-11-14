"""Solar-system lookup, offline. Response shapes copied from live calls on 2026-11-14."""
import math

import diskcache
import httpx
import pytest
import respx

from spherex_inspect import config
from spherex_inspect.context.solar_system import (
    SolarSystemLookup,
    jpl_fov,
    parse_horizons_vectors,
    parse_sb_ident,
    parse_skybot,
    topocentric,
)
from spherex_inspect.discovery import row_to_frame
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest

from .test_discovery import make_row

# Vesta seen from SPHEREx at JD 2461285.757702 (Horizons): RA 29.04344, Dec 0.60574.
TARGET = to_target(InspectRequest(ra=29.04344, dec=0.60574, cutout_size_deg=0.05))
MJD = 61285.257702
SPHEREX_KM = (-2189.742159606520, -6332.865800948803, 2132.511968115847)

SKYBOT_ROWS = [
    {"Num": 4, "Name": "Vesta", "RA (hms)": "01 56 10.1302", "DEC (dms)": "+00 36 22.646", "Class": "MB>Inner",
     "VMag (mag)": 7.3, "Err (arcsec)": 0.006, "d (arcsec)": 4.853, "dRA (arcsec/h)": -4.6865,
     "dDEC (arcsec/h)": -11.4326, "dg (ua)": 1.64392382491, "dh (ua)": 2.43151238068},
    {"Name": "2018 BP29", "RA (hms)": "01 56 10.5094", "DEC (dms)": "+00 35 13.312", "Class": "MB>Outer",
     "VMag (mag)": 22.5, "dg (ua)": 2.9},
    {"Name": "C/2099 Z1", "RA (hms)": "01 56 11.0", "DEC (dms)": "+00 36 00.0", "Class": "Comet",
     "VMag (mag)": 15.0, "dg (ua)": 3.0},
]

SB_IDENT = {
    "signature": {"version": "1.1", "source": "NASA/JPL Small-Body Identification API"},
    "fields_second": ["Object name", "Astrometric RA (hh:mm:ss)", "Astrometric Dec (dd mm'ss\")",
                      "Dist. from center RA (\")", "Dist. from center Dec (\")", "Dist. from center Norm (\")",
                      "Visual magnitude (V)", "RA rate (\"/h)", "Dec rate (\"/h)"],
    "data_second_pass": [
        ["4 Vesta (A807 FA)", "01:56:10.42", "+00 36'20.2\"", "-.115", "-.457", ".4715", "7.01", "-1.558E+00", "9.322E+00"],
        ["(2018 BP29)", "01:56:10.69", "+00 35'11.7\"", "3.95", "-69.0", "69.16", "22.6", "-1.033E+00", "-3.856E-01"],
    ],
    "n_second_pass": 2,
}

HORIZONS = {"result": "header\n$$SOE\n"
            "2461285.757702000, A.D. 2026-Sep-02 06:11:05.4528, -2.189742159606520E+03, -6.332865800948803E+03,  "
            "2.132511968115847E+03, -1.79E+00, -1.77E+00, -7.09E+00,\n$$EOE\nfooter"}


def test_topocentric_shift_size():
    # Observer at the geocentre: unchanged.
    assert topocentric(29.0, 0.6, 1.64, (0, 0, 0)) == pytest.approx((29.0, 0.6))
    ra, dec = topocentric(29.0, 0.6, 1.64, SPHEREX_KM)
    shift = math.hypot((ra - 29.0) * math.cos(math.radians(0.6)), dec - 0.6) * 3600
    # ≤ |r_obs| / distance = 7000 km / 1.64 AU ≈ 5.9″
    assert 1.0 < shift < 6.0


def test_parse_skybot_corrects_to_spherex_and_filters_faint():
    bodies = parse_skybot(SKYBOT_ROWS, MJD, TARGET, SPHEREX_KM)
    names = [b.name for b in bodies]
    assert "2018 BP29" not in names  # V 22.5 > SOLAR_MAX_V
    vesta = next(b for b in bodies if b.name == "4 Vesta")
    assert vesta.object_class == "asteroid" and vesta.is_solar_system and vesta.mags == {"V": 7.3}
    assert vesta.ids["observer"] == "spherex" and vesta.ids["skybot_class"] == "MB>Inner"
    # Corrected position agrees with Horizons-from-SPHEREx to ~1″ (geocentric was 4.9″ off).
    assert vesta.separation_arcsec < 1.5
    geo = next(b for b in parse_skybot(SKYBOT_ROWS, MJD, TARGET, None) if b.name == "4 Vesta")
    assert geo.separation_arcsec == pytest.approx(4.85, abs=0.3) and geo.ids["observer"] == "geocentre"
    assert next(b for b in bodies if b.name.startswith("C/")).object_class == "comet"


def test_parse_sb_ident():
    bodies = parse_sb_ident(SB_IDENT, MJD, TARGET)
    assert [b.name for b in bodies] == ["4 Vesta (A807 FA)"]  # 2018 BP29 is V 22.6
    v = bodies[0]
    assert v.separation_arcsec < 1.0 and v.ids["rate_dec_arcsec_h"] == "9.322E+00"
    assert v.source_catalogs == ["jpl_sb_ident"]


def test_parse_horizons_and_fov_format():
    vec = parse_horizons_vectors(HORIZONS["result"])
    assert vec[2461285.757702] == pytest.approx(SPHEREX_KM)
    with pytest.raises(ValueError):
        parse_horizons_vectors("No ephemeris for target")
    assert jpl_fov(133.795, -7.245) == ("08-55-10.80", "M07-14-42.0")
    assert jpl_fov(29.04344, 0.60574)[1] == "00-36-20.7"


def frames(n_obs=3, dets=(1, 4)):
    out = []
    for i in range(n_obs):
        for d in dets:
            # t_mid of exposure o0 == MJD
            out.append(row_to_frame(make_row(obs_id=f"o{i}", det=d, t=MJD - 0.00065 + i * 3), TARGET, "spherex_dr1"))
    return out


@pytest.fixture
def cache(tmp_path):
    c = diskcache.Cache(str(tmp_path / "c"))
    yield c
    c.close()


@respx.mock
async def test_lookup_maps_bodies_to_every_detector_of_the_exposure(cache):
    respx.get(config.HORIZONS_URL).mock(return_value=httpx.Response(200, json=HORIZONS))
    calls = []

    def skybot(request):
        calls.append(request)
        # only the first exposure has Vesta in the field
        return httpx.Response(200, json=SKYBOT_ROWS) if len(calls) == 1 else httpx.Response(204)

    respx.get(config.SKYBOT_URL).mock(side_effect=skybot)
    fs = frames()
    out, status = await SolarSystemLookup(cache=cache).lookup(TARGET, fs)
    assert len(calls) == 3  # one per exposure, not per detector
    assert set(out) == {"o0D1", "o0D4"} and out["o0D1"][0].name == "4 Vesta"
    assert status["skybot"] == "ok (3/3 exposures)" and status["horizons"].startswith("ok")

    # second run: everything from cache
    out2, _ = await SolarSystemLookup(cache=cache).lookup(TARGET, fs)
    assert len(calls) == 3 and set(out2) == set(out)


@respx.mock
async def test_skybot_down_falls_back_to_jpl_capped(cache, monkeypatch):
    monkeypatch.setattr(config, "SB_IDENT_MAX_CALLS", 1)
    respx.get(config.HORIZONS_URL).mock(return_value=httpx.Response(200, json=HORIZONS))
    respx.get(config.SKYBOT_URL).mock(return_value=httpx.Response(503))
    jpl = respx.get(config.SB_IDENT_URL).mock(return_value=httpx.Response(200, json=SB_IDENT))
    out, status = await SolarSystemLookup(cache=cache).lookup(TARGET, frames())
    assert jpl.call_count == 1  # capped
    assert set(out) == {"o0D1", "o0D4"} and out["o0D1"][0].source_catalogs == ["jpl_sb_ident"]
    assert status["skybot"].startswith("partial: 3/3") and "fallback for 1 of 3" in status["jpl_sb_ident"]
    # xobs carries the SPHEREx state from Horizons
    assert jpl.calls[0].request.url.params["xobs"].startswith("-2189.742160,-6332.865801")
    # the 503 is remembered: next request skips SkyBoT without calling it
    assert cache.get("solar:outage:skybot") is not None


@respx.mock
async def test_horizons_down_uses_geocentric_positions(cache):
    respx.get(config.HORIZONS_URL).mock(return_value=httpx.Response(500))
    respx.get(config.SKYBOT_URL).mock(return_value=httpx.Response(200, json=SKYBOT_ROWS))
    out, status = await SolarSystemLookup(cache=cache).lookup(TARGET, frames(n_obs=1))
    assert status["horizons"].startswith("error") and "geocentric" in status["horizons"]
    assert out["o0D1"][0].ids["observer"] == "geocentre"


async def test_lookup_without_frames():
    assert await SolarSystemLookup(cache={}).lookup(TARGET, []) == ({}, {})
