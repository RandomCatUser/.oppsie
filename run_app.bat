@echo off
title .oppsie TUI Dashboard
echo Converter/_init_.py...
echo app/main.py...
echo Checking for system dependencies...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/downloads/ and ensure it is added
    pause 
)
python "%~dp0app\main.py"
if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error (Code %errorlevel%^).
    echo Ensure Python is in your PATH and dependencies are installed:
    echo pip install -r requirements.txt
    pause
)
