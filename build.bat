@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ===================================================
echo   WeChat Emoji -^> Feishu  Build Script
echo ===================================================
echo.

:: Step 1: Stage Playwright runtime
echo [1/4] Staging Playwright Chromium runtime...
python stage_playwright_runtime.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Playwright staging failed.
    echo         Run 'python -m playwright install chromium' first.
    pause
    exit /b 1
)
echo.

:: Step 2: Kill running instances
echo [2/4] Checking for running instances...
taskkill /F /IM wechatemoji.exe >nul 2>&1
echo.

:: Step 3: Build with PyInstaller
echo [3/4] Building with PyInstaller...
pyinstaller wechatemoji.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)
echo.

:: Step 4: Verify output
echo [4/4] Verifying output...
set "DIST_DIR=dist\wechatemoji"

if exist "%DIST_DIR%\wechatemoji.exe" (
    echo   [OK] wechatemoji.exe found
) else (
    echo   [FAIL] wechatemoji.exe not found
)

if exist "%DIST_DIR%\_internal\web\index.html" (
    echo   [OK] Web assets bundled
) else (
    echo   [FAIL] Web assets missing
)

if exist "%DIST_DIR%\_internal\runtime\ms-playwright" (
    echo   [OK] Chromium runtime bundled
) else (
    echo   [WARN] Chromium runtime not bundled — upload to Feishu will not work
)

echo.
echo ===================================================
echo   Build complete: %DIST_DIR%\wechatemoji.exe
echo ===================================================
pause
