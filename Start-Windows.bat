@echo off
rem Starts Bee Interaction Detector (same as the Desktop icon).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto not_installed
start "" ".venv\Scripts\pythonw.exe" "%~dp0gui.py"
exit /b 0

:not_installed
echo Bee Interaction Detector is not installed yet.
echo Double-click Install-Windows.bat first.
pause
exit /b 1
