"""Regression tests for false-positive motion in the Explore detector."""
import numpy as np

from app.explore.analysis import (
    link_motion_candidates,
    motion_shots,
    _track_candidate,
)
from app.explore.common import Shot


def observations(points, dates=(61000.0, 61001.0, 61002.0)):
    return [(f"epoch{i}", t, [(x, y, 10.0)])
            for i, ((x, y), t) in enumerate(zip(points, dates))]


def test_two_detections_do_not_make_a_moving_object():
    assert link_motion_candidates(observations([(10, 10), (15, 10)], (61000.0, 61001.0))) == []


def test_stationary_source_with_centroid_jitter_not_moving():
    assert link_motion_candidates(observations([(10.0, 10), (11.0, 10.4), (9.6, 9.8)])) == []


def test_three_collinear_shifts_are_a_candidate():
    tracks = link_motion_candidates(observations([(10, 10), (13, 10), (16, 10)]))
    assert len(tracks) == 1
    assert len(tracks[0]) == 3
    assert _track_candidate(tracks[0]) is not None


def test_spurious_middle_position_does_not_prove_motion():
    assert link_motion_candidates(observations([(10, 10), (14, 13), (16, 10)])) == []


def test_closest_neighbour_cannot_jump_to_far_source():
    frames = [
        ("a", 61000.0, [(10, 10, 1.0)]),
        ("b", 61001.0, [(13, 10, 1.0)]),
        ("c", 61002.0, [(30, 10, 1.0)]),
    ]
    assert link_motion_candidates(frames) == []


def test_motion_requires_a_real_time_baseline():
    assert link_motion_candidates(observations(
        [(10, 10), (13, 10), (16, 10)],
        (61000.0, 61000.0001, 61000.0002),
    )) == []


def test_wavelength_and_detector_must_be_comparable(monkeypatch, tmp_path):
    from app.explore import analysis
    shots = (
        Shot("a", 1, 61000.0, tmp_path / "a.fits", 0.80),
        Shot("b", 2, 61001.0, tmp_path / "b.fits", 0.80),
        Shot("c", 1, 61002.0, tmp_path / "c.fits", 1.50),
        Shot("d", 1, 61003.0, tmp_path / "d.fits", 0.81),
        Shot("e", 1, 61004.0, tmp_path / "e.fits", 0.79),
    )
    monkeypatch.setattr(analysis, "shots_at", lambda ra, dec: shots)
    chosen = motion_shots(0, 0, [s.epoch_id for s in shots], [])
    assert [s.epoch_id for s in chosen] == ["a", "d", "e"]
    assert len({s.detector for s in chosen}) == 1
    assert max(s.wavelength for s in chosen) - min(s.wavelength for s in chosen) <= 0.025 * 2


def test_selected_band_does_not_fall_back_to_other_wavelength(monkeypatch, tmp_path):
    from app.explore import analysis
    shots = (
        Shot("a", 1, 61000.0, tmp_path / "a.fits", 0.80),
        Shot("b", 1, 61001.0, tmp_path / "b.fits", 4.20),
        Shot("c", 1, 61002.0, tmp_path / "c.fits", 0.81),
    )
    monkeypatch.setattr(analysis, "shots_at", lambda ra, dec: shots)
    chosen = motion_shots(0, 0, ["a", "b", "c"], ["starlight"])
    assert [s.epoch_id for s in chosen] == ["a", "c"]
