@echo off
rem Bee Interaction Detector - installer for Windows.
rem Double-click this file. Everything is installed inside this folder.
setlocal EnableExtensions
title Bee Interaction Detector - Installer
cd /d "%~dp0"
set "APP_DIR=%CD%"
set "TOOLS=%APP_DIR%\.tools"

rem Keep uv, Python and caches inside the program folder: nothing is installed
rem system-wide, and deleting the folder removes everything.
set "UV_INSTALL_DIR=%TOOLS%\uv"
set "UV_PYTHON_INSTALL_DIR=%TOOLS%\python"
set "UV_CACHE_DIR=%TOOLS%\uv-cache"
set "UV_NO_MODIFY_PATH=1"
set "UV_PYTHON_PREFERENCE=only-managed"
rem Trust the system's certificates (needed on university/corporate networks
rem that inspect HTTPS; uv otherwise only trusts its built-in list).
set "UV_NATIVE_TLS=1"

echo Bee Interaction Detector - installing into:
echo   %APP_DIR%
echo The first install downloads about 3 GB and takes 10-20 minutes.
echo Please keep this window open until it says "Installation complete".

call :find_uv
if defined UV goto have_uv
echo.
echo === Downloading the installer tool (uv)
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
call :find_uv
if defined UV goto have_uv
set "MSG=could not download uv - check the internet connection."
goto fail

:have_uv
set "PY=%APP_DIR%\.venv\Scripts\python.exe"
"%PY%" -c "import sys; sys.exit(sys.version_info[:2] != (3, 10))" >nul 2>&1
if not errorlevel 1 goto have_venv
echo.
echo === Setting up Python 3.10
if exist "%APP_DIR%\.venv" rmdir /s /q "%APP_DIR%\.venv"
"%UV%" venv --python 3.10 --seed "%APP_DIR%\.venv"
if not errorlevel 1 goto have_venv
set "MSG=could not create the Python environment."
goto fail

:have_venv
"%PY%" "%APP_DIR%\installer\setup_app.py"
if not errorlevel 1 goto done
set "MSG=see the messages above."
goto fail

:done
echo.
pause
exit /b 0

:find_uv
set "UV="
if exist "%UV_INSTALL_DIR%\uv.exe" set "UV=%UV_INSTALL_DIR%\uv.exe"
if not defined UV if exist "%UV_INSTALL_DIR%\bin\uv.exe" set "UV=%UV_INSTALL_DIR%\bin\uv.exe"
exit /b 0

:fail
echo.
echo INSTALLATION FAILED: %MSG%
echo Please send a screenshot of this window to the person who gave you the program.
echo.
pause
exit /b 1
