@echo off
REM Mech Simulator Launcher
REM Uses the 'mech' conda environment

echo Starting Mech Simulator...
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Run Python from the mech conda environment
"%USERPROFILE%\.conda\envs\mech\python.exe" mech.py

REM Pause if there was an error (but not on normal exit)
if errorlevel 1 (
    echo.
    echo.
    echo =====================================
    echo An error occurred during execution!
    echo =====================================
    echo.
    pause
)
