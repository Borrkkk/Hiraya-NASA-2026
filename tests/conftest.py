import pytest


@pytest.fixture(autouse=True)
def _isolated_cache(request, tmp_path, monkeypatch):
    """Offline tests never touch the real .cache/ and never wait on retry backoff. Live tests
    use the real cache on purpose, so repeat runs (and the demo) hit it instead of IRSA."""
    if request.node.get_closest_marker("live") is None:
        monkeypatch.setattr("spherex_inspect.config.CACHE_DIR", tmp_path / "cache")
        monkeypatch.setattr("spherex_inspect.config.SIA_BACKOFF_S", 0.0)
        monkeypatch.setattr("spherex_inspect.config.CUTOUT_BACKOFF_S", 0.0)
