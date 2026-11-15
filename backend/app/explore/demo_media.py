"""Snapshots, blink GIFs and spectra for discussions about the DEMO sky.

The demo (frontend/public/demo/barnard, made by frontend/scripts/make-demo-data.py)
has no real SPHEREx cutouts behind it, so the usual media builder in
finding_media.py finds nothing. When a post is about the demo patch, this
module builds the same three things from the prefetched demo frames instead:

    a tight still of the selection, a wider context image, a labelled blink GIF
    and a brightness-by-colour spectrum.

All of it is SIMULATED and is marked evidence["demo"] = True so the page can say so.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / 'frontend' / 'public' / 'demo' / 'barnard'
LEVEL = 1  # 256 px at 6.15 arcsec: sharp enough for a crop, wide enough for context
BAND_COLOURS = {  # frontend/src/lib/explore/bands.ts
    'starlight': '#ffe9c8', 'hydrogen': '#ff5d8f', 'helium': '#5fe0ff', 'water-ice': '#4f86ff',
    'co2-ice': '#a77bff', 'co-ice': '#5cf0b4', 'organic-dust': '#9dff5c', 'methane': '#ffd447',
    'warm-glow': '#e8453c',
}
FEATURES = {
    'M': [('Water vapour', 'Water vapour absorption (cool star atmosphere, 1.4 µm)', 1.4),
          ('Water vapour', 'Water vapour absorption (cool star atmosphere, 1.9 µm)', 1.9),
          ('Carbon monoxide', 'CO absorption (4.65 µm)', 4.65)],
    'K': [('Carbon monoxide', 'CO absorption (4.65 µm)', 4.65)],
    'G': [],
    'A': [('Hydrogen', 'Hydrogen line (Paschen β, 1.28 µm)', 1.28),
          ('Hydrogen', 'Hydrogen line (Paschen α, 1.88 µm)', 1.88)],
    'T': [('Methane', 'Methane absorption (1.7 µm)', 1.7), ('Methane', 'Methane absorption (3.3 µm)', 3.3)],
    'galaxy': [('Organic dust', 'PAH emission (3.3 µm)', 3.3)],
}

_manifest = None


def manifest():
    global _manifest
    if _manifest is None:
        path = DEMO / 'manifest.json'
        _manifest = json.loads(path.read_text()) if path.exists() else {}
    return _manifest


def in_demo(box):
    m = manifest()
    if not m:
        return False
    c = m['area']['center']
    d_ra = (box['ra'] - c['ra'] + 180) % 360 - 180
    return math.hypot(d_ra * math.cos(math.radians(c['dec'])), box['dec'] - c['dec']) < 1.2


def position(source, year):
    if 'pmRa' not in source:
        return source['ra'], source['dec']
    dt = year - source.get('ref', 2000.0)
    return (source['ra'] + source['pmRa'] / 3.6e6 * dt / math.cos(math.radians(source['dec'])),
            source['dec'] + source['pmDec'] / 3.6e6 * dt)


def total_flux(source, lam):
    m = manifest()
    return m['flux0'] * 10 ** (-0.4 * source['j']) * float(np.interp(lam, m['grid'], m['spectra'][source['cls']]))


def sources_in(box, year):
    out = []
    for s in manifest()['sources']:
        ra, dec = position(s, year)
        east = ((ra - box['ra'] + 180) % 360 - 180) * math.cos(math.radians(box['dec']))
        if abs(east) <= box['width'] / 2 and abs(dec - box['dec']) <= box['height'] / 2:
            fraction = 1.0
            if s['kind'] == 'galaxy':
                fraction = min(1.0, min(box['width'], box['height']) * 3600 / (6 * s.get('reff', 8)))
            out.append((s, fraction))
    return out


def projector(level=LEVEL):
    m = manifest()
    spec = m['area']['levels'][level]
    size, extent = spec['sizePx'], spec['extentDeg']
    c = m['area']['center']
    scale = size / 2 / math.tan(math.radians(extent) / 2)
    s0, c0 = math.sin(math.radians(c['dec'])), math.cos(math.radians(c['dec']))

    def to_xy(ra, dec):
        a, d = math.radians(ra - c['ra']), math.radians(dec)
        cosc = s0 * math.sin(d) + c0 * math.cos(d) * math.cos(a)
        xi = math.cos(d) * math.sin(a) / cosc
        eta = (c0 * math.sin(d) - s0 * math.cos(d) * math.cos(a)) / cosc
        return size / 2 - scale * xi, size / 2 - scale * eta

    return to_xy, size, spec['pixelScaleArcsec'], extent


def tinted(band, level, epoch_id):
    """The frame as an RGB image tinted with the band colour, 0 where there is no data."""
    path = DEMO / 'frames' / f'L{level}' / epoch_id / f'{band}.png'
    gray = np.asarray(Image.open(path).convert('RGBA'), dtype=float)
    g = gray[..., 0] / 255 * (gray[..., 3] / 255)
    base = np.array([int(BAND_COLOURS[band][i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    colour = 0.7 * base + 0.3 * 255  # a touch toward white so faint stars stay readable
    rgb = (g[..., None] ** 1.45) * colour[None, None, :]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')


def label_font(size):
    from PIL import ImageFont
    for name in ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc', '/Library/Fonts/Arial.ttf',
                 'DejaVuSans.ttf', 'C:/Windows/Fonts/segoeui.ttf'):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def detector_for(epoch_index):
    return 1 + (epoch_index * 5) % 6


def build(identifier, post):
    """Evidence additions (and media files on disk) for a post about the demo patch, or None."""
    box = post['box']
    if not in_demo(box):
        return None
    from .finding_media import image_path
    m = manifest()
    evidence = post['evidence']
    by_id = {e['id']: (i, e) for i, e in enumerate(m['epochs'])}
    chosen = sorted((by_id[e] for e in set(evidence['epochs']) if e in by_id), key=lambda t: t[1]['year'])
    if len(chosen) < 2:
        return None
    wanted = [b for b in evidence.get('bands', []) if b in BAND_COLOURS] or ['starlight']
    track = {t['epochId']: t for t in evidence.get('track', [])}
    # Most observations win; for something that moves, prefer the warm 4-5 um frames where cold objects shine.
    band = max(wanted, key=lambda b: (sum(b in e['bands'] for _, e in chosen), b == 'warm-glow' and bool(track)))
    with_band = [(i, e) for i, e in chosen if band in e['bands']]
    if len(with_band) < 2:
        band = 'starlight'
        with_band = [(i, e) for i, e in chosen if band in e['bands']] or chosen

    to_xy, size, pixel_scale, extent = projector()
    # One fixed crop around the selection (and the whole track, if there is one).
    pts = [to_xy(t['ra'], t['dec']) for t in track.values()] or [to_xy(box['ra'], box['dec'])]
    cx, cy = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    spread = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
    box_px = max(box['width'], box['height']) * 3600 / pixel_scale
    side = int(min(size, max(40, math.ceil(box_px * 2.6), math.ceil(spread + 26))))
    left = int(max(0, min(size - side, cx - side / 2)))
    top = int(max(0, min(size - side, cy - side / 2)))
    OUT = 512

    def ring(draw, x, y):
        draw.ellipse((x - 25, y - 25, x + 25, y + 25), outline='#080d13', width=4)
        draw.ellipse((x - 23, y - 23, x + 23, y + 23), outline='#ffad66', width=3)

    def marker_for(epoch_id):
        t = track.get(epoch_id)
        x, y = to_xy(t['ra'], t['dec']) if t else to_xy(box['ra'], box['dec'])
        return (x - left + .5) * OUT / side, (y - top + .5) * OUT / side

    frames, labels = [], []
    pick = with_band if len(with_band) <= 10 else [with_band[round(k * (len(with_band) - 1) / 9)] for k in range(10)]
    for i, e in pick:
        crop = tinted(band, LEVEL, e['id']).crop((left, top, left + side, top + side)).resize((OUT, OUT), Image.Resampling.BICUBIC)
        canvas = Image.new('RGB', (OUT, OUT + 100), '#080d13')
        canvas.paste(crop, (0, 0))
        draw = ImageDraw.Draw(canvas)
        ring(draw, *marker_for(e['id']))
        lam = e['wavelengths'].get(band, 0)
        draw.text((18, OUT + 6), e['date'][:10], font=label_font(30), fill='#ffffff')
        draw.text((18, OUT + 50), f'Detector {detector_for(i)}  |  {lam:.3f} µm', font=label_font(25), fill='#eeeeee')
        frames.append(canvas)
        labels.append({'epochId': e['id'], 'date': e['date'], 'wavelengthUm': lam})

    base = image_path(identifier)
    base.parent.mkdir(parents=True, exist_ok=True)
    # Still: the latest frame of the blink, without the caption strip.
    last_i, last = pick[-1]
    still = frames[-1].crop((0, 0, OUT, OUT))
    still.save(base, format='PNG')
    # Context: the whole frame with the selection outlined.
    ctx = tinted(band, LEVEL, last['id']).resize((size * 2, size * 2), Image.Resampling.BICUBIC)
    d = ImageDraw.Draw(ctx)
    bx, by = to_xy(box['ra'], box['dec'])
    hw, hh = box_px / 2 * 2, box_px / 2 * 2
    d.rectangle((bx * 2 - hw, by * 2 - hh, bx * 2 + hw, by * 2 + hh), outline='#ffad66', width=3)
    d.text((min(size * 2 - 120, bx * 2 + hw + 6), max(2, by * 2 - hh - 16)), 'Selected region', fill='#ffad66', font=label_font(14))
    ctx.save(base.with_suffix('.context.png'), format='PNG')
    # Blink.
    quantized = [f.quantize(colors=160, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE) for f in frames]
    quantized[0].save(base.with_suffix('.gif'), save_all=True, append_images=quantized[1:], duration=900, loop=0, optimize=False)

    # Spectrum: what the selection measured in every colour of every chosen observation.
    rng = np.random.default_rng(int.from_bytes(hashlib.sha1(identifier.encode()).digest()[:4], 'little'))
    npix = min(25, max(4, box['width'] * 3600 / pixel_scale * box['height'] * 3600 / pixel_scale))
    sigma = m['sigma'] * math.sqrt(npix) * 1.1
    points, dominant = [], None
    for i, e in chosen:
        hits = sources_in(box, e['year'])
        if hits and dominant is None:
            dominant = max(hits, key=lambda h: (h[0]['kind'] != 'hotpixel') * total_flux(h[0], 1.25) * h[1])[0]
        for b, lam in e['wavelengths'].items():
            flux = sum((60.0 if s['kind'] == 'hotpixel' else total_flux(s, lam)) * f for s, f in hits)
            measured = flux + rng.normal(0, math.hypot(sigma, flux * 0.015))
            points.append({'wavelengthUm': lam, 'flux': float(measured), 'epochId': e['id'], 'date': e['date'], 'detector': detector_for(i)})
    peak = max([p['flux'] for p in points] + [1e-9])
    for p in points:
        p['flux'] = round(p['flux'] / peak, 5)
    points.sort(key=lambda p: p['wavelengthUm'])
    features = [{'label': a, 'realName': b, 'wavelengthUm': c} for a, b, c in FEATURES.get(dominant['cls'], [])] if dominant else []

    return {
        'demo': True,
        'spectrum': {'points': points, 'fluxLabel': 'Brightness (relative)', 'features': features},
        'observationFacts': {'firstDate': chosen[0][1]['date'], 'lastDate': chosen[-1][1]['date'],
                             'detectors': sorted({detector_for(i) for i, _ in chosen}),
                             'measurementCount': len(points), 'epochCount': len(chosen)},
        'image': {'url': f'/explore/findings/{identifier}/image', 'epoch': last['id'], 'date': last['date'],
                  'detector': detector_for(last_i), 'wavelengthUm': last['wavelengths'].get(band, 0), 'band': band,
                  'extentDeg': side * pixel_scale / 3600, 'contextUrl': f'/explore/findings/{identifier}/image?context=true',
                  'caption': 'Simulated demo frame. The ring marks the discussed position' + (', following the track from date to date.' if track else '.')},
        'animation': {'url': f'/explore/findings/{identifier}/animation', 'frameCount': len(frames), 'frames': labels,
                      'extentDeg': side * pixel_scale / 3600,
                      'caption': 'Simulated demo frames. The crop stays fixed and the ring follows the discussed position; dates and wavelengths are shown below.'},
    }


def summary(evidence):
    count = len(set(evidence['epochs']))
    image = evidence.get('image')
    text = f'This post compares {count} selected observations in {len(evidence["bands"])} wavelength window(s). '
    if image:
        text += f'The attached frame was taken on {image["date"][:10]} near {image["wavelengthUm"]:.2f} micrometres. '
    if evidence.get('track'):
        text += f'The submitted track has {len(evidence["track"])} positions; a track alone does not establish reliable motion. '
    facts = evidence.get('observationFacts')
    if facts:
        text += f'The brightness plot has {facts["measurementCount"]} samples. '
    text += 'All images and measurements here are simulated for the demo. Compare the same crop across dates, read the wavelength on each frame, and use nearby stars to check alignment.'
    return text
