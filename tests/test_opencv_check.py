import sys
import types

import pytest


def _fake_cv2(monkeypatch, aruco_attrs=None, version="4.12.0"):
    """Install a stand-in cv2 module; aruco_attrs=None means no cv2.aruco at all."""
    cv2 = types.ModuleType("cv2")
    cv2.__version__ = version
    if aruco_attrs is not None:
        aruco = types.SimpleNamespace(**{name: object() for name in aruco_attrs})
        cv2.aruco = aruco
    monkeypatch.setitem(sys.modules, "cv2", cv2)


def test_installed_opencv_is_usable_by_naps():
    """The real environment: fails if plain opencv-python overwrote the contrib build."""
    from opencv_check import fix_instructions, opencv_problem

    problem = opencv_problem()
    assert problem is None, problem + "\n" + fix_instructions()


def test_plain_opencv_without_aruco_is_reported(monkeypatch):
    from opencv_check import opencv_problem

    _fake_cv2(monkeypatch, aruco_attrs=None, version="4.6.0")
    problem = opencv_problem()
    assert problem and "no cv2.aruco" in problem and "4.6.0" in problem


def test_new_opencv_without_legacy_aruco_api_is_reported(monkeypatch):
    from opencv_check import opencv_problem

    _fake_cv2(monkeypatch, aruco_attrs=["detectMarkers"], version="4.12.0")
    problem = opencv_problem()
    assert problem and "Dictionary_get" in problem and "DetectorParameters_create" in problem


def test_contrib_46_api_passes(monkeypatch):
    from opencv_check import opencv_problem

    _fake_cv2(monkeypatch,
              aruco_attrs=["Dictionary_get", "DetectorParameters_create", "detectMarkers"],
              version="4.6.0")
    assert opencv_problem() is None


def test_pipeline_stops_before_sleap_when_opencv_is_wrong(tmp_path, monkeypatch, capsys):
    import video_to_csv

    video = tmp_path / "v.mp4"
    video.touch()
    model = tmp_path / "model"
    model.mkdir()
    monkeypatch.setattr(video_to_csv, "opencv_problem", lambda: "OpenCV 4.6.0 has no cv2.aruco module")
    ran = []
    monkeypatch.setattr(video_to_csv, "run", lambda *a, **k: ran.append(a))

    with pytest.raises(SystemExit) as exc:
        video_to_csv.main(input_video=str(video), output_dir=str(tmp_path / "out"), model=str(model))

    assert "no cv2.aruco" in str(exc.value)
    assert "install_requirements.py" in str(exc.value)
    assert ran == []   # SLEAP / NAPS never started
