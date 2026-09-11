@echo off
REM PhotoMotion desktop — photos in, 1080p MP4s out.
cd /d "%~dp0"
set PYTHONPATH=%CD%\src

where python >nul 2>&1
if errorlevel 1 (
  echo python is required (3.10+).
  exit /b 1
)

python -c "import numpy, PIL" >nul 2>&1
if errorlevel 1 (
  echo Installing numpy and pillow...
  python -m pip install -r requirements.txt
)

python -m photomotion check
echo.
echo Opening the local desk. Drop 5+ JPEGs. Ken Burns is offline.
echo X / Imagine: python -m photomotion auth --login
echo.
python -m photomotion serve --host 127.0.0.1 --port 8765
