import pytest


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Never let tests read or write the real .cache/ directory."""
    monkeypatch.setattr("spherex_inspect.config.CACHE_DIR", tmp_path / "cache")
