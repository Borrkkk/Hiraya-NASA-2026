"""Real cached FITS -> science pipeline -> existing Explore HTTP contract, offline."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import spherex_inspect
from api.app import app
from backend.app.explore import sources
from backend.app.explore import router as explore_routes
from backend.app.explore.common import SHOTS, Shot, key
from spherex_inspect.context import FieldContextService

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def client(monkeypatch):
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    source = manifest['barnard_first_d1']
    coord = source['target']
    ra, dec = key(coord['ra'], coord['dec'])
    shots = []
    for name in ['barnard_first_d1', 'barnard_latest_d1', 'barnard_latest_d6']:
        item = manifest[name]
        frame = item['frame']
        shots.append(Shot(frame['obs_id'], frame['detector'], frame['t_min'],
                          FIXTURES / item['file'], 0.85 if frame['detector'] == 1 else 4.7))
    async def saved_only(http, x, y):
        SHOTS[key(x, y)] = tuple(shots)
    monkeypatch.setattr(sources, 'ensure_shots', saved_only)
    monkeypatch.setattr(explore_routes, 'ensure_shots', saved_only)
    monkeypatch.setattr(spherex_inspect, 'get_context', lambda: FieldContextService([]))
    with TestClient(app) as http:
        yield http, ra, dec, shots
    SHOTS.clear()


def body(ra, dec, epoch='all'):
    return {'areaId': f'{ra:.5f}_{dec:.5f}', 'target': {'kind': 'box', 'box': {
        'ra': ra, 'dec': dec, 'width': .02, 'height': .02}}, 'epoch': epoch, 'bands': ['starlight']}


def test_unified_api_serves_area_and_png(client):
    http, ra, dec, shots = client
    area = http.get('/explore/area', params={'ra': ra, 'dec': dec}).json()
    assert area['epochs'] and area['bands'] and area['levels']
    response = http.get(f"/explore/areas/{area['id']}/frames/{shots[0].epoch_id}/starlight")
    assert response.status_code == 200
    assert response.content.startswith(b'\x89PNG')


def test_selected_point_uses_science_and_all_epochs(client):
    http, ra, dec, shots = client
    payload = body(ra, dec)
    response = http.post(f"/explore/areas/{payload['areaId']}/inspect", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['evidence']['engine'] == 'spherex_inspect'
    assert result['evidence']['nFrames'] == len(shots)
    assert result['science']['query']['coord'] == {'ra': ra, 'dec': dec}
    assert len(result['science']['frames']) == len(shots)
    assert result['spectrum']['fluxLabel'] == 'Point-source flux (Jy)'
    assert result['candidates'] == []  # no manufactured probability scores
    assert all('err' in point for point in result['spectrum']['points'])


def test_epoch_selection_is_preserved(client):
    http, ra, dec, shots = client
    payload = body(ra, dec, shots[0].epoch_id)
    result = http.post(f"/explore/areas/{payload['areaId']}/inspect", json=payload).json()
    assert {frame['obs_id'] for frame in result['science']['frames']} == {shots[0].epoch_id}


def test_verify_without_catalog_match_does_not_claim_discovery(client):
    http, ra, dec, _ = client
    payload = body(ra, dec)
    response = http.post(f"/explore/areas/{payload['areaId']}/verify", json=payload)
    assert response.status_code == 200
    for _ in range(100):
        job = http.get('/explore/jobs/' + response.json()['jobId']).json()
        if job['status'] != 'running':
            break
        time.sleep(.05)
    assert job['status'] == 'done', job
    result = job['result']
    assert result['outcome'] == 'unexplained'
    assert result['evidence']['engine'] == 'spherex_inspect'
    assert result['science']['context']['verdict'] == 'no_known_match'


def test_legacy_endpoints_remain_available(client):
    http, _, _, _ = client
    paths = http.get('/openapi.json').json()['paths']
    assert all(path in paths for path in ['/inspect', '/inspect/frames', '/context', '/explore/area'])


@pytest.mark.asyncio
@pytest.mark.parametrize('matched,catalog_down', [(True, False), (False, True)])
async def test_verify_reports_match_or_unavailable_catalog(monkeypatch, matched, catalog_down):
    from api import explore_analysis
    from spherex_inspect.intake import to_target
    from spherex_inspect.models import (BestMatch, FieldContext, InspectRequest,
                                       InspectResponse, PointSummary, QualitySummary)
    context = FieldContext(
        verdict='matched' if matched else 'no_known_match',
        status_by_source={'gaia_dr3': 'error: timeout' if catalog_down else 'ok (1 rows)'},
        best_match=BestMatch(name="Barnard's Star", object_class='star', source_catalogs=['gaia_dr3'],
                             ra_at_t=269.4, dec_at_t=4.7, t_ref=61000, match_score=.95) if matched else None)
    result = InspectResponse(query=to_target(InspectRequest(ra=269.4, dec=4.7)), frames=[], context=context,
                             summary=PointSummary(quality=QualitySummary(n_frames=2, n_usable=2, n_detected=2)))
    async def fake(*args, **kwargs):
        return result
    monkeypatch.setattr(explore_analysis, 'analyze', fake)
    outcome = await explore_analysis.verify(269.4, 4.7, {}, 'all', lambda step: None, 0, [])
    assert outcome['outcome'] == ('explained' if matched else 'unexplained')
    if matched:
        assert outcome['name'] == "Barnard's Star" and outcome['source'] == 'gaia_dr3'
    else:
        assert 'unavailable' in outcome['nearMatch']['note']


def test_missing_cached_file_is_reported_as_failed(tmp_path):
    from api.explore_analysis import load_cutouts
    shot = Shot('missing', 1, 61000., tmp_path / 'missing.fits', .8)
    cuts = load_cutouts([shot], 0, 0, 0)
    assert len(cuts) == 1 and cuts[0].status == 'failed' and cuts[0].error
