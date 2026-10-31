"""
Check that the installed OpenCV is the build NAPS needs.

NAPS (naps-track 1.0.2) uses the legacy cv2.aruco API (Dictionary_get,
DetectorParameters_create, detectMarkers). That API only exists in the
*contrib* build of OpenCV 4.6. Several dependencies install other OpenCV
packages (opencv-python, opencv-python-headless) into the same `cv2` folder,
and whichever is installed last wins — so a plain pip install can silently
leave a cv2 without aruco. `install_requirements.py` fixes that.
"""

from typing import Optional

REQUIRED_OPENCV = "opencv-contrib-python==4.6.0.66"
FIX_COMMAND = "python install_requirements.py"
_ARUCO_API = ("Dictionary_get", "DetectorParameters_create", "detectMarkers")


def opencv_problem() -> Optional[str]:
    """Return a description of what's wrong with cv2, or None if NAPS can use it."""
    try:
        import cv2
    except Exception as exc:  # broken/partial install raises various errors
        return f"OpenCV (cv2) failed to import: {exc}"

    version = getattr(cv2, "__version__", "?")
    aruco = getattr(cv2, "aruco", None)
    if aruco is None:
        return (f"OpenCV {version} has no cv2.aruco module "
                f"(a plain opencv-python build is installed over the contrib build).")
    missing = [name for name in _ARUCO_API if not hasattr(aruco, name)]
    if missing:
        return (f"OpenCV {version} lacks cv2.aruco.{', '.join(missing)} "
                f"(NAPS needs the OpenCV 4.6 aruco API).")
    return None


def fix_instructions() -> str:
    return (f"NAPS needs {REQUIRED_OPENCV}. Fix it from the project folder with:\n"
            f"    {FIX_COMMAND}")


if __name__ == "__main__":
    import sys

    problem = opencv_problem()
    if problem:
        print(f"[ERROR] {problem}\n{fix_instructions()}")
        sys.exit(1)
    import cv2
    print(f"[OK] OpenCV {cv2.__version__} with the aruco API NAPS needs.")
