import pytest


@pytest.fixture(autouse=True)
def _isolated_cache(request, tmp_path, monkeypatch):
    """Offline tests never touch the real .cache/. Live tests use it on purpose, so repeat
    runs (and the demo) hit the cache instead of re-downloading from IRSA."""
    if request.node.get_closest_marker("live") is None:
        monkeypatch.setattr("spherex_inspect.config.CACHE_DIR", tmp_path / "cache")
