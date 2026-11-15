import numpy as np

from app.explore import analysis
from app.explore.common import Shot


def test_spectrum_uses_selected_position_not_area_centre(monkeypatch, tmp_path):
    shot = Shot('epoch1', 1, 61000, tmp_path / 'image.fits', 1.2)
    box = {'ra': 10.01, 'dec': 20.01, 'width': .02, 'height': .02}
    monkeypatch.setattr(analysis, 'aligned', lambda *args: np.ones((128, 128)))
    positions = []
    def wavelength(path, ra, dec):
        positions.append((ra, dec))
        return .987
    monkeypatch.setattr(analysis, '_read_wavelength', wavelength)
    result = analysis.inspect(10, 20, {'box': box, 'kind': 'box'}, 'all', shots=[shot])
    assert positions == [(box['ra'], box['dec'])]
    assert result['spectrum']['points'][0]['wavelengthUm'] == .987
    assert shot.wavelength == 1.2  # Area metadata remains unchanged.
