@echo off
REM Bootstrap script for Windows Command Prompt
REM This script runs the PowerShell setup script

setlocal enabledelayedexpansion

REM Get script directory
for %%I in ("%~dp0.") do set SCRIPT_DIR=%%~fI

echo 🚀 Starting development environment setup...
echo OS: Windows
echo.

REM Run PowerShell script
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\setup.ps1" %*

exit /b %errorlevel%
