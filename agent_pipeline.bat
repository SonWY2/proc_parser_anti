@echo off
REM [overview]
REM Prompt Manager Windows deploy script (PyInstaller)

chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "VENV_ACTIVATE=venv\Scripts\activate.bat"
set "ENTRY_SCRIPT=run.py"
set "SPEC_FILE=PromptManager.spec"
set "APP_NAME=PromptManager"
set "DIST_DIR=dist"
set "BUILD_DIR=build"
set "QT_BINDING_EXCLUDES=--exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2"

echo ========================================
echo Prompt Manager Windows EXE Deploy
echo ========================================
echo.

if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
) else (
    echo [WARN] Virtual environment not found. Continuing with system Python.
)

python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

if exist "requirements.txt" (
    echo [INFO] Installing dependencies...
    python -m pip install -r requirements.txt >nul
)

pyinstaller --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing PyInstaller...
    python -m pip install pyinstaller >nul
)

if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

if exist "%SPEC_FILE%" (
    echo [INFO] Building with spec file: %SPEC_FILE%
    pyinstaller --noconfirm --clean "%SPEC_FILE%"
) else (
    if not exist "%ENTRY_SCRIPT%" (
        echo [ERROR] Entry script not found: %ENTRY_SCRIPT%
        exit /b 1
    )
    echo [INFO] Building from entry script: %ENTRY_SCRIPT%
    pyinstaller --noconfirm --clean %QT_BINDING_EXCLUDES% --onefile --windowed --name "%APP_NAME%" "%ENTRY_SCRIPT%"
)

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

set "OUTPUT_EXE=%DIST_DIR%\%APP_NAME%.exe"
set "OUTPUT_EXE_ONEDIR=%DIST_DIR%\%APP_NAME%\%APP_NAME%.exe"

if exist "%OUTPUT_EXE%" (
    echo [SUCCESS] Build completed: %OUTPUT_EXE%
    exit /b 0
)

if exist "%OUTPUT_EXE_ONEDIR%" (
    echo [SUCCESS] Build completed: %OUTPUT_EXE_ONEDIR%
    exit /b 0
)

echo [ERROR] Build finished but executable was not found.
exit /b 1
