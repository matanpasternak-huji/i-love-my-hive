#!/bin/bash
# Starts Bee Interaction Detector (same as the Desktop icon).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Bee Interaction Detector is not installed yet."
  echo "Double-click Install-Mac.command first."
  read -r -p "Press Enter to close this window..." _
  exit 1
fi
mkdir -p .tools
nohup .venv/bin/python gui.py >>.tools/gui.log 2>&1 &
echo "Bee Interaction Detector is starting - you can close this window."
