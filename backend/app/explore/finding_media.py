"""Attach real cached observations and conservative, reproducible summaries."""
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np

from PIL import Image, ImageDraw, ImageFont

from .community import DB, database, finding
from .common import LEVELS, SHOTS, grid_wcs, in_band, key, mjd_to_iso, aligned, _read_wavelength
from .sources import cutout_path
from .frames import frame_png


def image_path(identifier):
    root = Path(os.environ.get('PULSR_COMMUNITY_DB', str(DB))).parent / 'finding-images'
    return root / f'{hashlib.sha256(identifier.encode()).hexdigest()}.png'


def highlight_selection(image, ra, dec, box, level):
    """Mark the same sky selection on every aligned observation before resizing."""
    cosd = max(abs(math.cos(math.radians(box['dec']))), 1e-6)
    wcs = grid_wcs(ra, dec, level)
    px, py = wcs.all_world2pix(
        [box['ra']-box['width']/2/cosd, box['ra']+box['width']/2/cosd],
        [box['dec']-box['height']/2, box['dec']+box['height']/2], 0)
    if not all(math.isfinite(float(v)) for v in [*px, *py]):
        return image
    x0, x1 = sorted(float(v) for v in px)
    y0, y1 = sorted(image.height-1-float(v) for v in py)
    if x1 < 0 or y1 < 0 or x0 >= image.width or y0 >= image.height:
        return image
    draw = ImageDraw.Draw(image)
    draw.rectangle((x0, y0, x1, y1), outline='#ffad66', width=2)
    label_x = max(2, min(image.width-96, x1+5))
    label_y = max(2, min(image.height-15, y0-15))
    draw.rectangle((label_x-2, label_y-1, label_x+91, label_y+12), fill='#080d13')
    draw.text((label_x, label_y), 'Selected region', fill='#ffad66')
    return image


def point_marker(image, ra, dec, box, level):
    x, y = grid_wcs(ra, dec, level).all_world2pix(box['ra'], box['dec'], 0)
    x, y = float(x), image.height-1-float(y)
    if math.isfinite(x) and math.isfinite(y):
        draw = ImageDraw.Draw(image)
        draw.ellipse((x-2, y-2, x+2, y+2), outline='#ffad66', width=1)
    return image, x, y


def focused_frame(image, ra, dec, box, level, marker=None):
    """One fixed object crop, shared by still and blink, with a small display ring."""
    x, y = grid_wcs(ra, dec, level).all_world2pix(box['ra'], box['dec'], 0)
    x, y = float(x), image.height-1-float(y)
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError('Selected point cannot be projected')
    side = min(image.width, image.height, max(32, math.ceil(max(box['width'], box['height'])*3600/LEVELS[level]['pixelScaleArcsec']*2.5)))
    left = max(0, min(image.width-side, int(x-side/2)))
    top = max(0, min(image.height-side, int(y-side/2)))
    image = image.crop((left, top, left+side, top+side)).resize((512, 512), Image.Resampling.NEAREST)
    if marker:
        x, y = grid_wcs(ra, dec, level).all_world2pix(marker['ra'], marker['dec'], 0)
        x, y = float(x), LEVELS[level]['sizePx']-1-float(y)
    mx, my = (x-left+.5)*512/side-.5, (y-top+.5)*512/side-.5
    draw = ImageDraw.Draw(image)
    draw.ellipse((mx-21, my-21, mx+21, my+21), outline='#080d13', width=3)
    draw.ellipse((mx-20, my-20, mx+20, my+20), outline='#ffad66', width=2)
    return image, side*LEVELS[level]['pixelScaleArcsec']/3600


def visible_reference(shots, ra, dec):
    """Choose a central image peak supported by at least three observations."""
    from .analysis import detect_sources
    catalog = []
    for shot in shots:
        path = cutout_path(shot, ra, dec, 0, science=False)
        if not path.exists():
            continue
        peaks = [p for p in detect_sources(aligned(str(path), ra, dec, 0))
                 if math.hypot(p[0]-63.5, p[1]-63.5) <= 34]
        catalog.append((shot, peaks))
    choices = []
    for _, peaks in catalog:
        for x, y, _ in peaks:
            matched = []
            for shot, other in catalog:
                nearest = min(other, key=lambda p: math.hypot(p[0]-x, p[1]-y), default=None)
                if nearest and math.hypot(nearest[0]-x, nearest[1]-y) <= 2.5:
                    matched.append((shot, nearest))
            if len({s.epoch_id for s, _ in matched}) >= 3:
                choices.append((len(matched), -math.hypot(x-63.5,y-63.5), matched))
    if not choices:
        return None
    _, _, matched = max(choices, key=lambda c: (c[0], c[1]))
    wcs = grid_wcs(ra, dec, 0)
    positions = []
    for shot, peak in matched:
        r, d = wcs.all_pix2world(peak[0], peak[1], 0)
        positions.append({'epochId': shot.epoch_id, 'detector': shot.detector, 'ra': float(r)%360, 'dec': float(d)})
    x = float(np.median([p[0] for _, p in matched])); y = float(np.median([p[1] for _, p in matched]))
    r, d = wcs.all_pix2world(x, y, 0)
    return {'ra': float(r)%360, 'dec': float(d), 'positions': positions,
            'method': 'Compact image peak matched within 2.5 native pixels across at least three observations'}


def label_font(size):
    for name in ('C:/Windows/Fonts/segoeui.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def enrich_observations(identifier, evidence, shots, ra, dec, box):
    """Build plots and a labelled blink from existing cache files only."""
    from .analysis import box_geometry
    points, available = [], []
    for shot in sorted(shots, key=lambda s: s.mjd):
        for level in range(len(LEVELS)):
            path = cutout_path(shot, ra, dec, level, science=False)
            if not path.exists():
                continue
            try:
                values = aligned(str(path), ra, dec, level)
                mask, *_ = box_geometry(ra, dec, box, level)
                measured = values[mask]
                good = measured[np.isfinite(measured)]
                if good.size >= 4 and good.size >= .5 * max(1, measured.size):
                    wave = _read_wavelength(str(path), box['ra'], box['dec'])
                    if math.isfinite(wave):
                        points.append({'wavelengthUm': wave, 'flux': float(good.mean()),
                                       'epochId': shot.epoch_id, 'date': mjd_to_iso(shot.mjd), 'detector': shot.detector})
                available.append(shot)
            except (ValueError, OSError, KeyError):
                pass
            break
    evidence['spectrum'] = {'points': sorted(points, key=lambda p: p['wavelengthUm']),
                            'fluxLabel': 'Average brightness above frame background (MJy/sr)', 'features': []}
    if available:
        evidence['observationFacts'] = {'firstDate': mjd_to_iso(min(s.mjd for s in available)),
            'lastDate': mjd_to_iso(max(s.mjd for s in available)), 'detectors': sorted({s.detector for s in available}),
            'measurementCount': len(points), 'epochCount': len({s.epoch_id for s in available})}
    band = evidence.get('image', {}).get('band')
    if not band:
        return
    animation_shots = [s for s in available if in_band(band, s.wavelength)]
    marker_positions = evidence.get('sourceReference', {}).get('positions', [])
    if marker_positions:
        animation_shots = [s for s in animation_shots if any(p['epochId'] == s.epoch_id and p['detector'] == s.detector for p in marker_positions)]
    if len(animation_shots) > 8:
        animation_shots = [animation_shots[round(i*(len(animation_shots)-1)/7)] for i in range(8)]
    common_level = next((level for level in range(len(LEVELS)) if animation_shots and
        all(cutout_path(s, ra, dec, level, science=False).exists() for s in animation_shots)), None)
    if common_level is None:
        return
    frames, labels = [], []
    for shot in animation_shots:
        for level in [common_level]:
            path = cutout_path(shot, ra, dec, level, science=False)
            if not path.exists():
                continue
            try:
                image = Image.open(BytesIO(frame_png(ra, dec, shot.epoch_id, band, level, path))).convert('RGB')
                marker = next((p for p in marker_positions if p['epochId'] == shot.epoch_id and p['detector'] == shot.detector), None)
                image, extent = focused_frame(image, ra, dec, box, level, marker)
                canvas = Image.new('RGB', (512, 612), '#080d13')
                canvas.paste(image, (0, 0))
                draw = ImageDraw.Draw(canvas)
                draw.text((18, 520), mjd_to_iso(shot.mjd)[:10], font=label_font(30), fill='#ffffff')
                draw.text((18, 563), f'Detector {shot.detector}  |  {shot.wavelength:.3f} µm', font=label_font(25), fill='#eeeeee')
                frames.append(canvas)
                labels.append({'epochId': shot.epoch_id, 'date': mjd_to_iso(shot.mjd), 'wavelengthUm': shot.wavelength})
            except (ValueError, OSError, KeyError):
                pass
            break
    if len(frames) >= 2:
        destination = image_path(identifier).with_suffix('.gif')
        # Reserve the ring colour so GIF quantization cannot discard a thin
        # marker when a detailed grayscale crop uses the other palette slots.
        palette = Image.new('P', (1, 1))
        palette.putpalette([v for i in range(255) for v in (i, i, i)] + [255, 173, 102])
        frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
        frames[0].save(destination, save_all=True, append_images=frames[1:], duration=1100, loop=0, optimize=False)
        evidence['animation'] = {'url': f'/explore/findings/{identifier}/animation', 'frameCount': len(frames),
            'frames': labels, 'extentDeg': extent,
            'caption': 'The ring surrounds the measured source position in each frame. The crop stays fixed; dates and wavelengths are shown below.' if marker_positions else 'The ring surrounds the selected position in each fixed crop. Dates and wavelengths are shown below.'}


def attach_media(identifier):
    with database() as connection:
        row = connection.execute('SELECT * FROM findings WHERE id=?', (identifier,)).fetchone()
        if not row:
            return
        post = finding(row)
    evidence = post['evidence']
    # A post about the demo patch gets simulated media from the prefetched demo frames.
    from . import demo_media
    built = demo_media.build(identifier, post)
    if built:
        evidence.update(built)
        evidence.update(summary=demo_media.summary(evidence), summaryMethod='data')
        with database() as connection:
            connection.execute('UPDATE findings SET evidence=? WHERE id=?', (json.dumps(evidence), identifier))
        return
    view = evidence.get('view') or post['box']
    ra, dec = key(view['ra'], view['dec'])
    shots = [s for s in SHOTS.get((ra, dec), ()) if s.epoch_id in evidence['epochs']]
    candidates = sorted(shots, key=lambda s: s.mjd, reverse=True)
    source_positions = evidence.get('sourceReference', {}).get('positions', [])
    if source_positions:
        candidates = [s for s in candidates if any(p['epochId'] == s.epoch_id and p['detector'] == s.detector for p in source_positions)]
    selected = None
    for shot in candidates:
        band = next((b for b in evidence['bands'] if in_band(b, shot.wavelength)), None)
        if not band:
            continue
        for level in range(len(LEVELS)):
            path = cutout_path(shot, ra, dec, level, science=False)
            if path.exists():
                x, y = grid_wcs(ra, dec, level).all_world2pix(post['box']['ra'], post['box']['dec'], 0)
                size = LEVELS[level]['sizePx']
                if not (0 <= x < size and 0 <= y < size):
                    continue
                selected = (shot, band, level, path)
                break
        if selected:
            break
    if selected:
        shot, band, level, path = selected
        try:
            png = frame_png(ra, dec, shot.epoch_id, band, level, path)
            image = Image.open(BytesIO(png)).convert('RGBA')
            destination = image_path(identifier)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination.with_suffix('.context.png'), format='PNG')
            marker = next((p for p in source_positions if p['epochId'] == shot.epoch_id and p['detector'] == shot.detector), None)
            image, extent = focused_frame(image, ra, dec, post['box'], level, marker)
            destination = image_path(identifier)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, format='PNG')
            evidence['image'] = {'url': f'/explore/findings/{identifier}/image', 'epoch': shot.epoch_id,
                'date': mjd_to_iso(shot.mjd), 'detector': shot.detector, 'wavelengthUm': shot.wavelength,
                'band': band, 'extentDeg': extent,
                'contextUrl': f'/explore/findings/{identifier}/image?context=true',
                'caption': 'The ring surrounds a detected image peak at its measured position.' if source_positions else 'The ring surrounds the submitted sky position in this cropped observation.'}
        except (OSError, ValueError, KeyError):
            pass
    enrich_observations(identifier, evidence, shots, ra, dec, post['box'])
    count = len(set(evidence['epochs']))
    summary = f'This post compares {count} selected observations in {len(evidence["bands"])} wavelength window(s). '
    if evidence.get('image'):
        image = evidence['image']
        summary += f'The attached SPHEREx image was taken on {image["date"][:10]} using detector {image["detector"]}, near {image["wavelengthUm"]:.2f} micrometres at the field centre. '
    else:
        summary += 'No locally cached observation image was available when this post was saved. '
    if evidence.get('track'):
        summary += f'The submitted candidate track contains {len(evidence["track"])} positions; this alone does not establish reliable motion. '
    if evidence.get('sourceReference'):
        summary += f'The highlighted image peak was matched in {len(evidence["sourceReference"]["positions"])} observations; its measured position places the ring in each shown frame. '
    summary += 'Compare the same crop across dates, read the wavelength label on each frame, and use nearby background sources to check alignment.'
    evidence.update(summary=summary, summaryMethod='data')
    with database() as connection:
        connection.execute('UPDATE findings SET evidence=? WHERE id=?', (json.dumps(evidence), identifier))
