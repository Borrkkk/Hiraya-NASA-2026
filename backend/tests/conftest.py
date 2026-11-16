import pytest


@pytest.fixture(autouse=True)
def isolated_index(tmp_path, monkeypatch):
    """Tests must not use a developer's installed all-sky index."""
    from app.explore import static_index
    monkeypatch.setattr(static_index, 'INDEX_ROOT', tmp_path / 'exposure-index')

    monkeypatch.setattr(static_index, 'BUNDLED_INDEX', tmp_path / 'bundled-index')
