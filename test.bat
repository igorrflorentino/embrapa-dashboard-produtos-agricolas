@echo off
REM Quick test script for development environment

setlocal enabledelayedexpansion

REM Get script directory
for %%I in ("%~dp0.") do set SCRIPT_DIR=%%~fI

echo 🧪 Running environment tests...
echo.

python "%SCRIPT_DIR%\scripts\test_setup.py" %*
