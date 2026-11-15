import asyncio
import json
import math
from pathlib import Path

import pytest
from astropy.time import Time

from spherex_inspect.context import FieldContextService
from spherex_inspect.context.base import CatalogAdapter, CatalogSource, ConeQuery
from spherex_inspect.context.fixed import CatWiseAdapter, GaiaAdapter, SimbadAdapter
from spherex_inspect.context.match import decide, group_sources, object_class, score_body, sep_arcsec
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest, PointSummary, PositionSample, ProperMotion, QualitySummary, SpectrumSample

G = json.loads((Path(__file__).parent.parent / "fixtures" / "manifest.json").read_text())["_gaia_dr3_barnard"]
T_FRAME = 61285.257702  # barnard_latest_d1


def barnard_gaia() -> CatalogSource:
    return CatalogSource(catalog="gaia_dr3", id=str(G["source_id"]), ra=G["ra"], dec=G["dec"], epoch_jyear=2016.0,
                         pm_ra_cosdec=G["pmra"], pm_dec=G["pmdec"], parallax=G["parallax"], rv=G["radial_velocity"],
                         name=f"Gaia DR3 {G['source_id']}", mags={"G": 8.19})


def barnard_simbad() -> CatalogSource:
    # SIMBAD gives J2000 positions; back-propagate Gaia to J2000 to build a consistent row.
    ra, dec = barnard_gaia().position_at(Time(2000.0, format="jyear").mjd)
    return CatalogSource(catalog="simbad", id="BD+04 3561a", ra=ra, dec=dec, epoch_jyear=2000.0,
                         pm_ra_cosdec=G["pmra"], pm_dec=G["pmdec"], parallax=G["parallax"], rv=G["radial_velocity"],
                         name="Barnard's Star", otype="BY*")


def neighbour(dra_arcsec, ddec_arcsec, mjd=T_FRAME, cat="gaia_dr3", id_="n1", **kw) -> CatalogSource:
    ra0, dec0 = barnard_gaia().position_at(mjd)
    return CatalogSource(catalog=cat, id=id_, ra=ra0 + dra_arcsec / 3600 / math.cos(math.radians(dec0)),
                         dec=dec0 + ddec_arcsec / 3600, epoch_jyear=Time(mjd, format="mjd").jyear, **kw)


def summary_at(ra, dec, err=1.5, t=T_FRAME, pm=None, spectrum=()):
    lp = PositionSample(t_mid=t, ra=ra, dec=dec, err=err)
    return PointSummary(latest_position=lp, first_position=lp, positions=[lp], proper_motion=pm,
                        spectrum=list(spectrum), quality=QualitySummary(n_frames=1, n_usable=1))


TARGET = to_target(InspectRequest(ra=269.4462668809119, dec=4.7682222752734695))


def test_propagation_matches_pm_times_dt():
    """Brief verification: Barnard moved J2016 → frame time ≈ published pm × Δt."""
    s = barnard_gaia()
    ra, dec = s.position_at(T_FRAME)
    dt = Time(T_FRAME, format="mjd").jyear - 2016.0
    ddec = (dec - G["dec"]) * 3600
    dra = (ra - G["ra"]) * 3600 * math.cos(math.radians(G["dec"]))
    assert ddec == pytest.approx(G["pmdec"] / 1000 * dt, rel=0.01)
    assert dra == pytest.approx(G["pmra"] / 1000 * dt, abs=0.5)  # + perspective acceleration
    assert 100 < math.hypot(dra, ddec) < 115  # ~10.4"/yr × 10.7 yr


def test_propagation_without_parallax_or_pm():
    s = CatalogSource(catalog="x", id="a", ra=10, dec=20, epoch_jyear=2016.0, pm_ra_cosdec=1000, pm_dec=0)
    ra, dec = s.position_at(Time(2026.0, format="jyear").mjd)
    assert (ra - 10) * 3600 * math.cos(math.radians(20)) == pytest.approx(10.0, rel=0.01)
    still = CatalogSource(catalog="x", id="b", ra=10, dec=20, epoch_jyear=2016.0)
    assert still.position_at(61000) == (10, 20)


def test_grouping_merges_catalogs_and_names_from_simbad():
    cw = neighbour(0.4, -0.3, cat="catwise2020", id_="J175747", mags={"W1": 4.0, "W2": 3.9},
                   pm_ra_cosdec=G["pmra"], pm_dec=G["pmdec"])
    bodies = group_sources([barnard_gaia(), barnard_simbad(), cw, neighbour(20, 0, id_="far")],
                           T_FRAME, (TARGET.coord.ra, TARGET.coord.dec), 90)
    b = bodies[0] if bodies[0].name == "Barnard's Star" else bodies[1]
    assert b.name == "Barnard's Star" and b.source_catalogs == ["gaia_dr3", "simbad", "catwise2020"]
    assert b.object_class == "variable_star"  # SIMBAD BY* (BY Draconis variable)
    assert b.ids["gaia_dr3"] == str(G["source_id"]) and b.mags["W1"] == 4.0 and b.mags["G"] == 8.19
    assert len(bodies) == 2


def test_grouping_filters_to_cone():
    bodies = group_sources([barnard_gaia()], T_FRAME, (TARGET.coord.ra, TARGET.coord.dec + 0.1), 90)
    assert bodies == []


@pytest.mark.parametrize("otype,mags,pm,cls", [
    ("BD*", {}, None, "brown_dwarf"), ("Mi*", {}, None, "variable_star"), ("PM*", {}, None, "star"),
    ("*", {}, None, "star"), ("QSO", {}, None, "qso"), ("Sy2", {}, None, "galaxy"), ("Rad", {}, None, "unknown"),
    (None, {"W1": 14.0, "W2": 12.5}, 800.0, "brown_dwarf"), (None, {"W1": 14.0, "W2": 12.5}, 50.0, "unknown"),
    (None, {"W1": 10.0, "W2": 9.9}, 900.0, "unknown"),
])
def test_object_class(otype, mags, pm, cls):
    assert object_class(otype, mags, pm) == cls


def _bodies(*sources, centre=None, t=T_FRAME):
    c = centre or (TARGET.coord.ra, TARGET.coord.dec)
    bodies = group_sources(list(sources), t, c, 90)
    return bodies


def _with_sep(bodies, ra, dec):
    for b in bodies:
        b.separation_arcsec = sep_arcsec(b.ra_at_t, b.dec_at_t, ra, dec)
    return sorted(bodies, key=lambda b: b.separation_arcsec)


def test_matched_isolated_star():
    ra, dec = barnard_gaia().position_at(T_FRAME)
    bodies = _with_sep(_bodies(barnard_gaia(), barnard_simbad(), neighbour(25, 10, id_="n")), ra, dec + 1 / 3600)
    best, verdict, note = decide(bodies, summary_at(ra, dec + 1 / 3600))
    assert verdict == "matched" and best.name == "Barnard's Star" and best.match_score > 0.9


def test_ambiguous_blend():
    ra, dec = barnard_gaia().position_at(T_FRAME)
    srcs = [neighbour(-1.8, 0, id_="a"), neighbour(1.8, 0, id_="b")]
    bodies = _with_sep(_bodies(*srcs), ra, dec)
    best, verdict, note = decide(bodies, summary_at(ra, dec))
    assert verdict == "ambiguous" and "2 known bodies" in note


def test_no_known_match_is_candidate_discovery():
    ra, dec = barnard_gaia().position_at(T_FRAME)
    bodies = _with_sep(_bodies(neighbour(30, 0, id_="far")), ra, dec)
    best, verdict, note = decide(bodies, summary_at(ra, dec))
    assert verdict == "no_known_match" and best is None and "candidate discovery" in note
    assert decide([], summary_at(ra, dec))[1] == "no_known_match"


def test_nothing_detected():
    s = PointSummary(quality=QualitySummary(n_frames=3, n_usable=0))
    best, verdict, note = decide([], s)
    assert best is None and verdict == "no_known_match" and "nothing detected" in note


def test_pm_term_ranks_coincident_stars():
    """Two catalog stars 0.5" apart: the measured pm ranks the fast one first. With the brief's
    weights (position 0.6, pm 0.25) the margin stays < 0.2, so the verdict is ambiguous."""
    ra, dec = barnard_gaia().position_at(T_FRAME)
    still = neighbour(0.5, 0, id_="still", pm_ra_cosdec=0.0, pm_dec=0.0)
    bodies = _with_sep(_bodies(barnard_gaia(), still), ra, dec)
    pm = ProperMotion(pm_ra_cosdec=-1886, pm_dec=10190, err=268, significance=38.7, pm_total=10363)
    s = summary_at(ra, dec, pm=pm)
    scores = {b.ids.get("gaia_dr3"): score_body(b, s) for b in bodies}
    fast, slow = scores[str(G["source_id"])], scores["still"]
    assert fast[1]["pm"] > 0.4 and slow[1]["pm"] < 0.01  # live SPHEREx pm (biased RA) still agrees
    assert fast[0] > slow[0] + 0.1
    best, verdict, _ = decide(bodies, s)
    assert verdict == "ambiguous" and best.ids["gaia_dr3"] == str(G["source_id"])


def test_ir_term_uses_catalog_mags():
    ra, dec = barnard_gaia().position_at(T_FRAME)
    b = _with_sep(_bodies(neighbour(0, 0, cat="catwise2020", id_="w", mags={"W1": 10.0})), ra, dec)[0]
    w1_jy = 309.54 * 10 ** (-0.4 * 10.0)
    good = summary_at(ra, dec, spectrum=[SpectrumSample(wavelength_um=3.35, flux=w1_jy, err=w1_jy / 50, frame_id="f")])
    bad = summary_at(ra, dec, spectrum=[SpectrumSample(wavelength_um=3.35, flux=w1_jy * 10, err=w1_jy / 50, frame_id="f")])
    assert score_body(b, good)[1]["ir"] == pytest.approx(1.0)
    assert score_body(b, bad)[1]["ir"] < 0.01
    far = summary_at(ra, dec, spectrum=[SpectrumSample(wavelength_um=2.5, flux=1, err=0.1, frame_id="f")])
    assert "ir" not in score_body(b, far)[1]  # no SPHEREx sample within 0.3 µm of W1


def test_simbad_parse_skips_planets_and_uses_name():
    # As returned live on 2026-11-14: main_id is itself a NAME identifier.
    rows = [
        {"main_id": "NAME Barnard's star", "otype": "BY*", "ra": 269.45, "dec": 4.69, "pmra": -802, "pmdec": 10362,
         "plx_value": 547, "rvz_radvel": -110, "name": "NAME Barnard Star"},
        {"main_id": "NAME Barnard's star", "otype": "BY*", "ra": 269.45, "dec": 4.69, "pmra": -802, "pmdec": 10362,
         "plx_value": 547, "rvz_radvel": -110, "name": "NAME Barnard's star"},
        {"main_id": "HD 1", "otype": "*", "ra": 269.47, "dec": 4.71, "pmra": 1, "pmdec": 1,
         "plx_value": None, "rvz_radvel": None, "name": "NAME Zeta"},
        {"main_id": "HD 1", "otype": "*", "ra": 269.47, "dec": 4.71, "pmra": 1, "pmdec": 1,
         "plx_value": None, "rvz_radvel": None, "name": "NAME Alpha"},
        {"main_id": "Barnard's Star b", "otype": "Pl", "ra": 269.45, "dec": 4.69, "pmra": -802, "pmdec": 10362,
         "plx_value": 547, "rvz_radvel": None, "name": "NAME Barnard's Star b"},
        {"main_id": "TYC 1", "otype": "*", "ra": 269.46, "dec": 4.70, "pmra": None, "pmdec": None,
         "plx_value": None, "rvz_radvel": None, "name": None},
    ]
    srcs = SimbadAdapter(cache={}).parse(rows)
    assert [s.name for s in srcs] == ["Barnard's star", "Alpha", "TYC 1"]
    assert srcs[0].otype == "BY*" and srcs[2].pm_ra_cosdec is None


def test_catwise_parse_units():
    rows = [{"source_name": "J175747.09+044605.4", "ra_pm": 269.44, "dec_pm": 4.76, "pmra": -0.8, "pmdec": 10.3,
             "w1mpro_pm": 4.1, "w2mpro_pm": 3.9}]
    [s] = CatWiseAdapter(cache={}).parse(rows)
    assert s.pm_ra_cosdec == pytest.approx(-800) and s.pm_dec == pytest.approx(10300)  # arcsec/yr → mas/yr
    assert s.epoch_jyear == pytest.approx(2015.405) and s.mags == {"W1": 4.1, "W2": 3.9}


def test_queries_are_pm_aware():
    q = ConeQuery(ra=269.446, dec=4.768, radius_arcsec=90, mjd=61040.0)
    for a in (SimbadAdapter(cache={}), GaiaAdapter(cache={}), CatWiseAdapter(cache={})):
        adql = a.build_query(q)
        assert "CONTAINS" in adql and "DISTANCE" in adql and "SQRT(POWER(" in adql
    # SIMBAD (J2000) needs a far wider search ring than Gaia (J2016)
    big = lambda a: float(a.build_query(q).split("CIRCLE('ICRS', ")[1].split(",")[2].split(")")[0])
    assert big(SimbadAdapter(cache={})) > big(GaiaAdapter(cache={})) + 0.04
    assert "POINT('ICRS', ra, dec), CIRCLE" in CatWiseAdapter(cache={}).build_query(q)  # indexed columns


class FakeAdapter(CatalogAdapter):
    def __init__(self, name, sources=(), exc=None, delay=0.0, timeout=5.0):
        super().__init__(cache={})
        self.name, self._sources, self._exc, self._delay, self.timeout_s = name, list(sources), exc, delay, timeout
        self.calls = 0

    async def cone(self, q):
        self.calls += 1
        if self._delay:
            await asyncio.wait_for(asyncio.sleep(self._delay), timeout=self.timeout_s)
        if self._exc:
            raise self._exc
        return list(self._sources)


async def test_service_status_and_partial_failure():
    svc = FieldContextService([
        FakeAdapter("gaia_dr3", [barnard_gaia()]),
        FakeAdapter("simbad", exc=ConnectionError("404 capabilities")),
        FakeAdapter("catwise2020", delay=1.0, timeout=0.01),
    ])
    sources, status, _ = await svc.fetch(TARGET, [])
    assert status["gaia_dr3"] == "ok (1 rows)" and status["simbad"].startswith("error")
    assert status["catwise2020"].startswith("timeout")
    ra, dec = barnard_gaia().position_at(T_FRAME)
    ctx = svc.build(TARGET, [], sources, status, summary_at(ra, dec))
    assert ctx.verdict == "matched" and ctx.best_match.source_catalogs == ["gaia_dr3"]
    assert ctx.status_by_source == status and ctx.t_ref == T_FRAME


async def test_adapter_caches_raw_rows():
    class Counting(GaiaAdapter):
        n = 0

        def run_query(self, adql):
            Counting.n += 1
            return [{"source_id": 1, "ra": 10.0, "dec": 20.0, "pmra": 1.0, "pmdec": 2.0, "parallax": None,
                     "radial_velocity": None, "ref_epoch": 2016.0, "phot_g_mean_mag": 12.0}]

    import diskcache, tempfile
    with tempfile.TemporaryDirectory() as d:
        a = Counting(cache=diskcache.Cache(d))
        q = ConeQuery(ra=10, dec=20, radius_arcsec=60, mjd=61000)
        r1, r2 = await a.cone(q), await a.cone(q)
        assert Counting.n == 1 and r1[0].id == r2[0].id == "1"


async def test_outage_is_remembered_and_skipped(tmp_path):
    """After a timeout, later requests skip the catalog without waiting; a bad query does not trip it."""
    import diskcache

    from spherex_inspect.context.base import CatalogUnavailable, is_outage

    class Slow(GaiaAdapter):
        calls = 0

        def run_query(self, adql):
            Slow.calls += 1
            raise TimeoutError("Read timed out. (read timeout=40.5)")

    cache = diskcache.Cache(str(tmp_path / "c"))
    q1 = ConeQuery(ra=10, dec=20, radius_arcsec=60, mjd=61000)
    q2 = ConeQuery(ra=11, dec=21, radius_arcsec=60, mjd=61000)  # different cone: not a cache hit
    with pytest.raises(TimeoutError):
        await Slow(cache=cache).cone(q1)
    with pytest.raises(CatalogUnavailable, match="skipped: unavailable since"):
        await Slow(cache=cache).cone(q2)  # fresh instance (e.g. next request / process)
    assert Slow.calls == 1

    svc = FieldContextService([Slow(cache=cache)])
    _, status, _ = await svc.fetch(TARGET, [])
    assert status["gaia_dr3"].startswith("skipped: unavailable since")

    assert is_outage(Exception("502 Server Error: Proxy Error"))
    assert not is_outage(Exception("Incorrect ADQL query: Encountered '.'"))


async def test_query_error_does_not_trip_outage(tmp_path):
    import diskcache

    class Broken(GaiaAdapter):
        calls = 0

        def run_query(self, adql):
            Broken.calls += 1
            raise ValueError("Incorrect ADQL query")

    cache = diskcache.Cache(str(tmp_path / "c"))
    q = ConeQuery(ra=10, dec=20, radius_arcsec=60, mjd=61000)
    for _ in range(2):
        with pytest.raises(ValueError):
            await Broken(cache=cache).cone(q)
    assert Broken.calls == 2  # retried each time, never skipped


def test_asteroid_in_latest_frame_explains_detection():
    """A detection that coincides with a solar-system body in its own frame is matched to it,
    not reported as a candidate discovery."""
    from spherex_inspect.models import KnownBody

    ra, dec = 222.86623, -11.90754
    tgt = to_target(InspectRequest(ra=ra, dec=dec))
    lp = PositionSample(t_mid=60891.4618, ra=ra, dec=dec + 0.5 / 3600, err=1.5, frame_id="F1D3")
    s = PointSummary(latest_position=lp, first_position=lp, positions=[lp], quality=QualitySummary(n_frames=1, n_usable=0))
    vesta = KnownBody(name="4 Vesta", object_class="asteroid", source_catalogs=["skybot"], ra_at_t=ra, dec_at_t=dec,
                      t_ref=60891.4618, separation_arcsec=0.0, is_solar_system=True)
    star = neighbour(0, 0)  # irrelevant field star far away after re-centring
    star.ra, star.dec = ra + 0.01, dec
    svc = FieldContextService([])
    no_solar = svc.build(tgt, [], [star], {}, s)
    # unexplained, but seen in only one frame → flagged as a likely artifact, not a discovery
    assert no_solar.verdict == "no_known_match" and not no_solar.candidate_discovery
    assert "only 1 artifact-free frame" in no_solar.note
    ctx = svc.build(tgt, [], [star], {}, s, solar_by_frame={"F1D3": [vesta], "F1D6": [vesta]})
    assert ctx.verdict == "matched" and ctx.best_match.name == "4 Vesta" and ctx.best_match.is_solar_system
    assert all(not b.is_solar_system for b in ctx.nearby)  # nearby stays the fixed-sky list
    # an asteroid in some OTHER frame does not explain the latest detection
    other = svc.build(tgt, [], [star], {}, s, solar_by_frame={"F9D1": [vesta]})
    assert other.verdict == "no_known_match"


def test_brightness_veto_same_wavelength_only():
    from spherex_inspect.context.match import brightness_veto
    from spherex_inspect.models import KnownBody, SpectrumSample

    ra, dec = 248.1676, 66.755
    lp = PositionSample(t_mid=61000, ra=ra, dec=dec, err=3.0, frame_id="F")
    sat = [SpectrumSample(wavelength_um=0.8, flux=6.0, err=0.02, frame_id="a", flags=["OVERFLOW", "MASKED_PIXELS"])]
    s = PointSummary(latest_position=lp, first_position=lp, positions=[lp], spectrum_flagged=sat,
                     quality=QualitySummary(n_frames=1, n_usable=0))
    faint = KnownBody(name="faint", ra_at_t=ra, dec_at_t=dec, t_ref=61000, separation_arcsec=0.1, mags={"G": 19.4})
    mira = KnownBody(name="V* R Dra", object_class="variable_star", ra_at_t=ra, dec_at_t=dec + 4.1 / 3600,
                     t_ref=61000, separation_arcsec=4.1, mags={"G": 6.4, "RP": 6.2})
    assert brightness_veto(faint, s) and not brightness_veto(mira, s)
    best, verdict, _ = decide([faint, mira], s)
    assert verdict == "matched" and best.name == "V* R Dra"
    # A very red object (faint in Gaia) measured only at 4.5 µm is never vetoed by Gaia mags.
    red = PointSummary(latest_position=lp, first_position=lp, positions=[lp],
                       spectrum=[SpectrumSample(wavelength_um=4.5, flux=0.002, err=1e-4, frame_id="b")],
                       quality=QualitySummary(n_frames=1, n_usable=1))
    bd = KnownBody(name="BD", ra_at_t=ra, dec_at_t=dec, t_ref=61000, separation_arcsec=0.5, mags={"G": 21.0})
    assert brightness_veto(bd, red) is None
