from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.explore.community import record_identification
import httpx


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('PULSR_COMMUNITY_DB', str(tmp_path / 'community.sqlite3'))
    with TestClient(app) as client:
        yield client


def payload(ra=10, dec=20):
    return {'box': {'ra': ra, 'dec': dec, 'width': .005, 'height': .005},
            'title': 'Possible moving source', 'body': 'A source appears to move between these two observations.',
            'bands': ['starlight'], 'epochs': ['first', 'second']}


def test_shared_post_comments_and_duplicate_lookup(client):
    first = client.post('/explore/findings', json=payload())
    assert first.status_code == 200, first.text
    post = first.json()['finding']
    assert first.json()['created']
    assert post['status'] == 'suspected-motion'
    duplicate = client.post('/explore/findings', json=payload(10.001))
    assert duplicate.json()['created'] is False
    assert duplicate.json()['finding']['id'] == post['id']
    match = client.get('/explore/findings/match', params=payload()['box']).json()
    assert match['finding']['id'] == post['id']
    assert post['author'] == 'Alex Rivera'
    assert client.post(f"/explore/findings/{post['id']}/comments", json={'body': 'Check the background stars for an alignment error.'}).status_code == 200
    # New database connections and another browser/client see the same discussion.
    with TestClient(app) as other:
        discussion = other.get(f"/explore/findings/{post['id']}").json()
        assert discussion['comments'][0]['author'] == 'Alex Rivera'
    markers = client.get('/explore/markers', params={'ra': 10, 'dec': 20}).json()['markers']
    assert markers[0]['id'] == post['id'] and markers[0]['kind'] == 'finding'


def test_deduplication_is_atomic_across_concurrent_submissions(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post('/explore/findings', json=payload()).json(), range(8)))
    assert len({r['finding']['id'] for r in responses}) == 1
    assert sum(r['created'] for r in responses) == 1


def test_wraparound_and_separate_regions(client):
    first = client.post('/explore/findings', json=payload(359.999)).json()
    duplicate = client.post('/explore/findings', json=payload(.001)).json()
    assert first['finding']['id'] == duplicate['finding']['id']
    separate = client.post('/explore/findings', json=payload(1)).json()
    assert separate['created']


def test_validation_and_missing_posts(client):
    body = payload()
    body['epochs'] = ['same', 'same']
    assert client.post('/explore/findings', json=body).status_code == 422
    body = payload(); body['box']['ra'] = -1
    assert client.post('/explore/findings', json=body).status_code == 422
    assert client.get('/explore/findings/missing').status_code == 404
    assert client.post('/explore/findings/missing/comments', json={'body': 'hello'}).status_code == 404


def test_account_cannot_be_replaced_by_client_and_summary_is_honest(client, monkeypatch):
    forged = payload(); forged['author'] = 'Someone else'
    assert client.post('/explore/findings', json=forged).status_code == 422
    assert client.get('/explore/session').json()['account']['id'] == 'alex-rivera'
    saved = client.post('/explore/findings', json=payload()).json()['finding']
    assert saved['evidence']['summaryMethod'] == 'data'
    assert 'No locally cached observation image' in saved['evidence']['summary']
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    summary = client.post(f"/explore/findings/{saved['id']}/summary").json()
    assert summary['method'] == 'data'
    assert client.get(f"/explore/findings/{saved['id']}/image").status_code == 404


def test_verified_marker_distinguishes_catalog_position_from_selection(client):
    result = {'outcome': 'explained', 'source': 'SIMBAD', 'name': 'Known star', 'position': {'ra': 10.001, 'dec': 20}}
    record_identification(result, payload()['box'], 'first')
    result2 = {'outcome': 'explained', 'source': 'SkyBoT', 'name': 'Known asteroid'}
    record_identification(result2, payload()['box'], 'second')
    markers = client.get('/explore/markers', params={'ra': 10, 'dec': 20}).json()['markers']
    assert {m['basis'] for m in markers} == {'selection', 'catalog'}


def test_optional_ai_summary_uses_facts_without_post_text(client, monkeypatch):
    post = client.post('/explore/findings', json=payload()).json()['finding']
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-key')
    monkeypatch.setenv('PULSR_AI_MODEL', 'test-model')
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'output': [{'content': [{'type': 'output_text', 'text': 'Two observations are selected. Compare background sources before interpreting apparent motion.'}]}]})
    original = app.state.client
    mock = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    app.state.client = mock
    try:
        result = client.post(f"/explore/findings/{post['id']}/summary")
        assert result.status_code == 200, result.text
        assert result.json()['method'] == 'ai'
        assert payload()['body'] not in requests[0].content.decode()
        assert 'Alex Rivera' not in requests[0].content.decode()
        assert client.get(f"/explore/findings/{post['id']}").json()['finding']['evidence']['summaryMethod'] == 'ai'
    finally:
        app.state.client = original
        client.portal.call(mock.aclose)
