#!/bin/bash
# Bee Interaction Detector - installer for macOS.
# Double-click this file in Finder. Everything is installed inside this folder.

cd "$(dirname "$0")" || exit 1
APP_DIR="$(pwd)"
TOOLS="$APP_DIR/.tools"

# Keep uv, Python and caches inside the program folder: nothing is installed
# system-wide, and deleting the folder removes everything.
export UV_INSTALL_DIR="$TOOLS/uv"
export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
export UV_CACHE_DIR="$TOOLS/uv-cache"
export UV_NO_MODIFY_PATH=1
export UV_PYTHON_PREFERENCE=only-managed

pause_exit() {
  if [ -t 0 ]; then echo; read -r -p "Press Enter to close this window..." _; fi
  exit "$1"
}
fail() {
  echo
  echo "INSTALLATION FAILED: $1"
  echo "Please send a screenshot of this window to the person who gave you the program."
  pause_exit 1
}
find_uv() {
  for c in "$UV_INSTALL_DIR/uv" "$UV_INSTALL_DIR/bin/uv"; do
    if [ -x "$c" ]; then echo "$c"; return 0; fi
  done
  return 1
}

echo "Bee Interaction Detector - installing into:"
echo "  $APP_DIR"
echo "The first install downloads about 3 GB and takes 10-20 minutes."
echo "Please keep this window open until it says 'Installation complete'."

UV="$(find_uv)" || {
  echo
  echo "=== Downloading the installer tool (uv)"
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail "could not download uv - check the internet connection."
  UV="$(find_uv)" || fail "uv was not installed."
}

PY="$APP_DIR/.venv/bin/python"
if ! "$PY" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 10))' >/dev/null 2>&1; then
  echo
  echo "=== Setting up Python 3.10"
  rm -rf "$APP_DIR/.venv"
  "$UV" venv --python 3.10 --seed "$APP_DIR/.venv" || fail "could not create the Python environment."
fi

"$PY" "$APP_DIR/installer/setup_app.py" || fail "see the messages above."
pause_exit 0
