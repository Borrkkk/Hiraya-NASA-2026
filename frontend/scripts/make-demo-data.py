#!/usr/bin/env python3
"""Generate the prefetched Barnard's Star demo data for the Explore page.

    backend/.venv/bin/python frontend/scripts/make-demo-data.py

Writes frontend/public/demo/barnard/:
    manifest.json                     area, epochs, bands, sources, spectra templates
    frames/L<level>/<epoch>/<band>.png    greyscale + alpha, same contract as the real API

NOTHING HERE IS SPHEREx DATA. It is a deterministic simulation shaped like it:
  * Barnard's Star really moves: proper motion (-798.58, +10328.12) mas/yr, J = 5.24.
  * 18 observations spread over 17 months, each seeing only some wavelengths.
  * SPHEREx-like pixels (6.15"), three zoom levels, a stretch shared across epochs.
  * Field stars with realistic colours, cosmic-ray hits, hot pixels, a faint
    galaxy, and one invented faint, cold, fast-moving object (the "find").
Re-run to regenerate; output is byte-for-byte stable (fixed seeds).
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "public" / "demo" / "barnard"
D2R = math.pi / 180

# ---------------------------------------------------------------- geometry
LEVELS = [
    {"level": 0, "sizePx": 128, "pixelScaleArcsec": 6.15},
    {"level": 1, "sizePx": 256, "pixelScaleArcsec": 6.15},
    {"level": 2, "sizePx": 256, "pixelScaleArcsec": 14.0},
]
for l in LEVELS:
    l["extentDeg"] = l["sizePx"] * l["pixelScaleArcsec"] / 3600

# Barnard's Star, J2000 (ICRS) and proper motion. Centre the area on where it is
# in the middle of the data window so it sits in the middle of the picture.
RA2000, DEC2000 = 269.452075, 4.693369
PM_RA, PM_DEC = -798.58, 10328.12  # mas/yr (mu_alpha* , mu_delta)
T_MID = 2026.1
COS = math.cos(DEC2000 * D2R)


def pm_position(ra, dec, pm_ra, pm_dec, year):
    dt = year - 2000.0
    return (
        ra + (pm_ra / 3.6e6) * dt / math.cos(dec * D2R),
        dec + (pm_dec / 3.6e6) * dt,
    )


CENTER = pm_position(RA2000, DEC2000, PM_RA, PM_DEC, T_MID)
CENTER = (round(CENTER[0], 4), round(CENTER[1], 4))


def make_projection(ra0, dec0, size_px, extent_deg):
    """Same maths as frontend/src/lib/explore/projection.ts (gnomonic, east left)."""
    scale = size_px / 2 / math.tan(extent_deg * D2R / 2)
    s0, c0 = math.sin(dec0 * D2R), math.cos(dec0 * D2R)

    def to_xy(ra, dec):
        a = np.asarray(ra) * D2R - ra0 * D2R
        d = np.asarray(dec) * D2R
        cosc = s0 * np.sin(d) + c0 * np.cos(d) * np.cos(a)
        xi = np.cos(d) * np.sin(a) / cosc
        eta = (c0 * np.sin(d) - s0 * np.cos(d) * np.cos(a)) / cosc
        return size_px / 2 - scale * xi, size_px / 2 - scale * eta

    def to_sky(x, y):
        xi = (size_px / 2 - np.asarray(x)) / scale
        eta = (size_px / 2 - np.asarray(y)) / scale
        rho = np.hypot(xi, eta)
        c = np.arctan(rho)
        with np.errstate(invalid="ignore", divide="ignore"):
            dec = np.arcsin(np.cos(c) * s0 + np.where(rho == 0, 0, eta * np.sin(c) * c0 / rho))
            ra = ra0 * D2R + np.arctan2(xi * np.sin(c), rho * c0 * np.cos(c) - eta * s0 * np.sin(c))
        return (np.degrees(ra) % 360), np.degrees(dec)

    return to_xy, to_sky, scale


# ---------------------------------------------------------------- bands + epochs
BANDS = [
    "starlight", "hydrogen", "helium", "water-ice", "co2-ice",
    "co-ice", "organic-dust", "methane", "warm-glow",
]
# One wavelength is sampled per band per exposure. Line bands cycle through
# their lines; continuum bands wander inside their window.
WAVES = {
    "starlight": [0.78, 0.86, 0.95, 1.02, 1.10, 1.18, 1.25],
    "hydrogen": [1.28, 1.88, 4.05],
    "helium": [1.08],
    "water-ice": [3.0],
    "co2-ice": [4.27],
    "co-ice": [4.67],
    "organic-dust": [3.3],
    "methane": [1.7, 3.3],
    "warm-glow": [3.85, 4.0, 4.2, 4.4, 4.6, 4.8, 4.95],
}

N_EPOCHS = 18
DATE0 = np.datetime64("2025-06-14T06:20")
DATE1 = np.datetime64("2026-11-02T18:05")
rng_dates = np.random.default_rng(7)

epochs = []
span = (DATE1 - DATE0) / np.timedelta64(1, "m")
for i in range(N_EPOCHS):
    frac = i / (N_EPOCHS - 1)
    jitter = rng_dates.uniform(-0.18, 0.18) / (N_EPOCHS - 1) if 0 < i < N_EPOCHS - 1 else 0
    minutes = (frac + jitter) * span
    d = DATE0 + np.timedelta64(int(minutes), "m")
    epochs.append({"id": f"e{i + 1:02d}", "date": str(d) + ":00Z"})

# Which bands each observation has. starlight + warm-glow together in most;
# four "rich" observations carry nearly everything.
RICH = {3, 8, 12, 16}
rng_b = np.random.default_rng(11)
for i, e in enumerate(epochs):
    have = []
    for b in BANDS:
        if i in RICH:
            p = 0.93
        elif b in ("starlight", "warm-glow"):
            p = 0.8
        else:
            p = 0.38
        if rng_b.random() < p:
            have.append(b)
    # Guarantee at least starlight + one more so no epoch is empty.
    if "starlight" not in have:
        have.insert(0, "starlight")
    e["bands"] = [b for b in BANDS if b in have]
for b in BANDS:  # every band appears often enough to be useful
    while sum(b in e["bands"] for e in epochs) < 5:
        e = epochs[int(rng_b.integers(0, N_EPOCHS))]
        if b not in e["bands"]:
            e["bands"] = [x for x in BANDS if x in e["bands"] or x == b]
# Make sure starlight+warm-glow overlap is generous, but not total.
for i in (0, 5, 11):
    epochs[i]["bands"] = [b for b in epochs[i]["bands"] if b != "warm-glow"]

MASKED = {2: 0.04, 9: 0.06, 14: 0.03}  # fraction of the frame lost at one edge
rng_w = np.random.default_rng(23)
for i, e in enumerate(epochs):
    e["coverage"] = round(1 - MASKED.get(i, 0.0), 3)
    e["wavelengths"] = {b: float(rng_w.choice(WAVES[b])) for b in e["bands"]}
    e["year"] = 2000.0 + float((np.datetime64(e["date"][:-1]) - np.datetime64("2000-01-01T12:00")) / np.timedelta64(1, "D")) / 365.25

# ---------------------------------------------------------------- spectra
# Relative Fnu with J-band (1.25 um) = 1. Hand-built from blackbody shapes plus
# the main molecular features, good enough to read as the right kind of object.
GRID = np.round(np.linspace(0.75, 5.0, 96), 4)


def planck_nu(lam_um, T):
    x = 14387.77 / (lam_um * T)
    return (1 / lam_um) ** 3 / np.expm1(x)


def dip(l, c, w, depth):
    return 1 - depth * np.exp(-(((l - c) / w) ** 2))


def template(kind, l):
    l = np.asarray(l, float)
    if kind in ("M", "K", "G", "A"):
        T = {"M": 3300, "K": 4500, "G": 5800, "A": 8000}[kind]
        f = planck_nu(l, T) / planck_nu(1.25, T)
        if kind == "M":
            f = f * (l / 1.25) ** -0.32  # real cool stars fall faster than a blackbody
            f = f * dip(l, 1.40, 0.07, 0.20) * dip(l, 1.90, 0.10, 0.26) * dip(l, 2.70, 0.18, 0.22)
            f = f * dip(l, 4.65, 0.20, 0.12) * dip(l, 0.93, 0.05, 0.12)
        elif kind == "K":
            f = f * dip(l, 4.65, 0.2, 0.06)
        elif kind == "A":
            f = f * dip(l, 1.282, 0.015, 0.14) * dip(l, 1.875, 0.02, 0.16) * dip(l, 4.05, 0.04, 0.10)
        return f
    if kind == "T":  # a cold brown dwarf: methane, then a bright 4.5 um peak
        pts = [(0.75, 0.01), (0.90, 0.07), (1.00, 0.55), (1.10, 0.95), (1.25, 1.00), (1.40, 0.55),
               (1.55, 0.30), (1.70, 0.10), (1.85, 0.07), (2.10, 0.30), (2.40, 0.10), (2.8, 0.08),
               (3.0, 0.16), (3.3, 0.07), (3.6, 0.28), (3.9, 0.55), (4.2, 1.15), (4.5, 1.60),
               (4.8, 1.45), (5.0, 1.05)]
        xs, ys = zip(*pts)
        return np.interp(l, xs, ys)
    if kind == "galaxy":  # old stars (1.6 um bump) + PAH 3.3 + warm dust
        f = 0.7 + 0.5 * np.exp(-(((l - 1.6) / 0.5) ** 2)) + 0.25 * (l / 1.25) ** -0.2
        f = f * (1 + 0.28 * np.exp(-(((l - 3.3) / 0.07) ** 2))) * (1 + 0.5 * np.clip((l - 3.8) / 1.2, 0, 1))
        f = f * dip(l, 1.40, 0.15, 0.06)
        return f
    raise ValueError(kind)


SPECTRA = {k: [round(float(v), 5) for v in template(k, GRID)] for k in ("M", "K", "G", "A", "T", "galaxy")}

# ---------------------------------------------------------------- sources
rng_s = np.random.default_rng(2026)
center_xy, center_sky, _ = make_projection(*CENTER, LEVELS[2]["sizePx"], LEVELS[2]["extentDeg"])

sources = []  # everything that exists on the sky: stars, galaxy, the find, hot pixels
EXT2 = LEVELS[2]["extentDeg"]
N_FIELD = 3400
# Magnitudes: number counts rise steeply with faintness, cut at the detection limit.
u = rng_s.random(N_FIELD)
jmag = 8.2 + np.log10(1 + u * (10 ** (0.30 * (17.4 - 8.2)) - 1)) / 0.30
classes = rng_s.choice(["M", "K", "G", "A"], size=N_FIELD, p=[0.38, 0.27, 0.27, 0.08])
xs = rng_s.uniform(0, LEVELS[2]["sizePx"], N_FIELD)
ys = rng_s.uniform(0, LEVELS[2]["sizePx"], N_FIELD)
ras, decs = center_sky(xs, ys)
for i in range(N_FIELD):
    sources.append({"id": f"s{i}", "kind": "star", "cls": str(classes[i]), "j": round(float(jmag[i]), 2),
                    "ra": float(ras[i]), "dec": float(decs[i])})

# Barnard's Star itself.
sources.append({"id": "barnard", "kind": "star", "cls": "M", "j": 5.244, "ra": RA2000, "dec": DEC2000,
                "pmRa": PM_RA, "pmDec": PM_DEC, "name": "Barnard's Star", "ref": 2000.0})

# The invented find: faint, cold, moving fast enough to see in 17 months.
c0xy = make_projection(*CENTER, LEVELS[0]["sizePx"], LEVELS[0]["extentDeg"])
bd_ra, bd_dec = c0xy[1](44.0, 82.0)
bd_ra, bd_dec = float(bd_ra), float(bd_dec)
sources.append({"id": "find", "kind": "mover", "cls": "T", "j": 15.45, "ra": bd_ra, "dec": bd_dec,
                "pmRa": 5200.0, "pmDec": -4300.0, "ref": T_MID})

# A faint galaxy a little way off, extended.
gx, gy = c0xy[1](94.0, 41.0)
sources.append({"id": "gal1", "kind": "galaxy", "cls": "galaxy", "j": 12.9, "ra": float(gx), "dec": float(gy),
                "reff": 9.5, "ell": 0.55, "pa": 28.0})

# Two hot pixels: the same detector pixel every time.
HOT = [(30.5, 100.5), (109.5, 18.5)]
for k, (px, py) in enumerate(HOT):
    r, d = c0xy[1](px, py)
    sources.append({"id": f"hot{k + 1}", "kind": "hotpixel", "cls": "A", "j": 0, "ra": float(r), "dec": float(d)})


def source_position(s, year):
    if "pmRa" in s:
        return pm_position(s["ra"], s["dec"], s["pmRa"], s["pmDec"], year) if s["ref"] == 2000.0 else (
            s["ra"] + (s["pmRa"] / 3.6e6) * (year - s["ref"]) / math.cos(s["dec"] * D2R),
            s["dec"] + (s["pmDec"] / 3.6e6) * (year - s["ref"]),
        )
    return s["ra"], s["dec"]


# ---------------------------------------------------------------- rendering
FWHM_ARCSEC = 8.0     # SPHEREx blur is a bit under 1.5 pixels
SIGMA = 1.0           # pixel noise unit
FLUX0 = 4.0e7        # total counts for J = 0; tuned so J~16.5 is a ~4 sigma peak
# A star's total flux in a band: FLUX0 * 10^(-0.4 J) * template(lambda).


def moffat_stamp(dx, dy, fwhm_px, beta=2.6, ss=3):
    """Integrated Moffat on the pixel grid around (dx, dy) offsets, ss x ss subsampled."""
    alpha = fwhm_px / (2 * math.sqrt(2 ** (1 / beta) - 1))
    n = int(math.ceil(7 * max(fwhm_px, 1.0)))
    ax = np.arange(-n, n + 1)
    sub = (np.arange(ss) + 0.5) / ss - 0.5
    xx = ax[None, :, None, None] + sub[None, None, None, :] - dx
    yy = ax[:, None, None, None] + sub[None, None, :, None] - dy
    r2 = xx ** 2 + yy ** 2
    prof = (1 + r2 / alpha ** 2) ** -beta
    norm = (beta - 1) / (math.pi * alpha ** 2)
    return (prof * norm).mean(axis=(2, 3)), n


def smooth_noise(shape, rng, sigma_px):
    n = rng.normal(0, 1, shape)
    k = int(max(1, round(sigma_px * 2)))
    if k > 1:
        ker = np.hanning(2 * k + 1)
        ker /= ker.sum()
        n = np.apply_along_axis(lambda r: np.convolve(r, ker, "same"), 0, n)
        n = np.apply_along_axis(lambda r: np.convolve(r, ker, "same"), 1, n)
        n /= n.std()
    return n


def cirrus(size, rng):
    """Faint, smooth, fixed structure (interstellar dust and zodiacal gradient)."""
    f = np.zeros((size, size))
    for octave, amp in ((6, 1.0), (14, 0.5), (30, 0.22)):
        g = rng.normal(0, 1, (octave, octave))
        im = Image.fromarray(g.astype(np.float32), mode="F").resize((size, size), Image.BICUBIC)
        f += amp * np.asarray(im)
    return f / f.std()


def render(level, epoch, band, rng):
    L = LEVELS[level]
    n, scale = L["sizePx"], L["pixelScaleArcsec"]
    to_xy, _, _ = make_projection(*CENTER, n, L["extentDeg"])
    lam = epoch["wavelengths"][band]
    img = np.zeros((n, n))
    fwhm_px = FWHM_ARCSEC / scale
    for s in sources:
        ra, dec = source_position(s, epoch["year"])
        x, y = to_xy(ra, dec)
        x, y = float(x), float(y)
        if not (-12 < x < n + 12 and -12 < y < n + 12):
            continue
        if s["kind"] == "hotpixel":
            # One detector pixel, constant in detector coordinates (L0 pixel units).
            continue
        total = FLUX0 * 10 ** (-0.4 * s["j"]) * float(template(s["cls"], lam))
        if s["kind"] == "galaxy":
            reff = s["reff"] / scale
            yy, xx = np.mgrid[0:n, 0:n]
            ang = s["pa"] * D2R
            u = (xx + 0.5 - x) * math.cos(ang) + (yy + 0.5 - y) * math.sin(ang)
            v = -(xx + 0.5 - x) * math.sin(ang) + (yy + 0.5 - y) * math.cos(ang)
            r = np.sqrt(u ** 2 + (v / (1 - s["ell"])) ** 2) / max(reff, 0.4)
            prof = np.exp(-7.67 * (r ** 0.25 - 1))
            prof /= prof.sum()
            img += total * prof
            continue
        if total < 0.5:  # far below the noise: skip the work
            continue
        stamp, k = moffat_stamp(x - math.floor(x) - 0.5, y - math.floor(y) - 0.5, fwhm_px)
        ix, iy = int(math.floor(x)), int(math.floor(y))
        x0, y0 = ix - k, iy - k
        sx0, sy0 = max(0, -x0), max(0, -y0)
        ex, ey = min(2 * k + 1, n - x0), min(2 * k + 1, n - y0)
        if ex <= sx0 or ey <= sy0:
            continue
        img[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex] += total * stamp[sy0:ey, sx0:ex]

    # Fixed structure: dust + zodiacal gradient (band-dependent) and a small epoch offset.
    fixed = np.random.default_rng(900 + level)
    ci = cirrus(n, fixed)
    gx, gy = np.meshgrid(np.linspace(-1, 1, n), np.linspace(-1, 1, n))
    zodi = {"warm-glow": 1.4, "co-ice": 1.1, "co2-ice": 1.1, "organic-dust": 0.9, "water-ice": 0.9}.get(band, 0.6)
    img += 0.55 * zodi * ci + zodi * 0.8 * (0.5 * gx - 0.3 * gy) * (1 + 0.1 * math.sin(epoch["year"] * 6.28))
    # Noise: white + a little correlated.
    img += SIGMA * (0.8 * rng.normal(0, 1, (n, n)) + 0.6 * smooth_noise((n, n), rng, 0.9))
    # Hot pixels (same detector pixel each time) and cosmic-ray hits (different each time).
    for (px, py) in HOT:
        hx, hy = px * n / 128, py * n / 128
        img[int(hy) % n, int(hx) % n] += 11 * SIGMA * (scale / 6.15)
    for _ in range(int(rng.integers(2, 6))):
        cx, cy = int(rng.integers(2, n - 2)), int(rng.integers(2, n - 2))
        img[cy, cx] += rng.uniform(14, 60) * SIGMA
        if rng.random() < 0.5:
            img[cy, cx + int(rng.choice([-1, 1]))] += rng.uniform(4, 14) * SIGMA
    return img


# ---------------------------------------------------------------- stretch + write
def write_png(path, gray, alpha):
    rgba = np.stack([gray, gray, gray, alpha], axis=-1).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def main():
    for old in OUT.glob("frames"):
        for f in old.rglob("*.png"):
            f.unlink()
    stretches = {}
    count = 0
    for level in range(len(LEVELS)):
        n = LEVELS[level]["sizePx"]
        for band in BANDS:
            # One stretch per band and level, from the first observation that has the band.
            ref_ep = next(e for e in epochs if band in e["bands"])
            ref = render(level, ref_ep, band, np.random.default_rng(1000 + level * 7 + BANDS.index(band)))
            med = float(np.median(ref))
            mad = float(np.median(np.abs(ref - med))) * 1.4826
            stretches[(level, band)] = (med + 0.9 * mad, med + 22 * mad)
        for ei, e in enumerate(epochs):
            for band in e["bands"]:
                rng = np.random.default_rng(10_000 + level * 1000 + ei * 20 + BANDS.index(band))
                img = render(level, e, band, rng)
                lo, hi = stretches[(level, band)]
                norm = np.clip((img - lo) / (hi - lo), 0, 1)
                gray = 255 * np.arcsinh(10 * norm) / np.arcsinh(10)
                alpha = np.full((n, n), 255)
                lost = MASKED.get(ei, 0.0)
                if lost:
                    w = max(1, int(round(lost * n)))
                    if ei % 2:
                        alpha[:, :w] = 0
                    else:
                        alpha[:, n - w:] = 0
                    gray = gray * (alpha > 0)
                write_png(OUT / "frames" / f"L{level}" / e["id"] / f"{band}.png", gray, alpha)
                count += 1
    print(f"wrote {count} frames")

    # What the page can ask about: stars bright enough to measure, plus the special objects.
    keep = [s for s in sources if s["kind"] != "star" or s["j"] < 14.8 or s["id"] == "barnard"]
    manifest = {
        "area": {
            "id": "demo-barnard",
            "name": "Barnard's Star",
            "center": {"ra": CENTER[0], "dec": CENTER[1]},
            "extentDeg": LEVELS[0]["extentDeg"],
            "sizePx": LEVELS[0]["sizePx"],
            "pixelScaleArcsec": LEVELS[0]["pixelScaleArcsec"],
            "minFovDeg": round(0.3 * LEVELS[0]["extentDeg"], 4),
            "maxFovDeg": round(0.98 * LEVELS[2]["extentDeg"], 4),
            "levels": LEVELS,
        },
        "epochs": epochs,
        "wavelengths": WAVES,
        "grid": [float(g) for g in GRID],
        "spectra": SPECTRA,
        "sources": keep,
        "hotPixels": [{"x": x / 128, "y": y / 128} for x, y in HOT],
        "flux0": FLUX0,
        "sigma": SIGMA,
        "fwhmArcsec": FWHM_ARCSEC,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    print("sources kept:", len(keep), "centre:", CENTER)
    for e in epochs:
        print(e["id"], e["date"][:10], e["coverage"], len(e["bands"]), ",".join(b[:4] for b in e["bands"]))


if __name__ == "__main__":
    main()
