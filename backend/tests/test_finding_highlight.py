import numpy as np
from PIL import Image

from app.explore.finding_media import highlight_selection, focused_frame, visible_reference
from app.explore.common import LEVELS
from app.explore.common import Shot, grid_wcs
from app.explore import analysis, finding_media


def test_selected_sky_coordinates_are_highlighted_on_every_frame():
    box = {'ra': 10, 'dec': 20, 'width': .025, 'height': .025}
    masks = []
    for background in (0, 80, 150):
        image = Image.new('RGB', (128, 128), (background,)*3)
        highlight_selection(image, 10, 20, box, 0)
        pixels = np.array(image)
        orange = (pixels[..., 0] > 200) & (pixels[..., 1] > 80) & (pixels[..., 1] < 210) & (pixels[..., 2] < 160)
        assert orange[54:74, 54:74].sum() > 20
        masks.append(orange)
    assert np.array_equal(masks[0], masks[1])
    assert np.array_equal(masks[1], masks[2])


def test_blink_crop_is_tight_and_marker_stays_small_after_display_resize():
    box = {'ra': 10, 'dec': 20, 'width': .025, 'height': .025}
    image, extent = focused_frame(Image.new('RGB', (128, 128), 'black'), 10, 20, box, 0)
    assert image.size == (512, 512)
    assert extent < LEVELS[0]['extentDeg']/2
    pixels = np.array(image)
    y, x = np.where((pixels[..., 0] == 255) & (pixels[..., 1] == 173) & (pixels[..., 2] == 102))
    assert 38 <= x.max()-x.min() <= 42 and 38 <= y.max()-y.min() <= 42


def test_reference_uses_a_repeated_image_peak_not_the_empty_field_centre(monkeypatch, tmp_path):
    shots = [Shot(str(i), 1, 61000+i, tmp_path / f'{i}.fits', 1.0) for i in range(3)]
    for shot in shots: shot.path.touch()
    monkeypatch.setattr(finding_media, 'cutout_path', lambda shot, *args, **kwargs: shot.path)
    monkeypatch.setattr(finding_media, 'aligned', lambda *args: np.zeros((128, 128)))
    monkeypatch.setattr(analysis, 'detect_sources', lambda *args: [(72., 70., 20.)])
    reference = visible_reference(shots, 10, 20)
    assert len(reference['positions']) == 3
    x, y = grid_wcs(10, 20, 0).all_world2pix(reference['ra'], reference['dec'], 0)
    assert abs(float(x)-72) < .001 and abs(float(y)-70) < .001
    assert visible_reference(shots[:1], 10, 20) is None
