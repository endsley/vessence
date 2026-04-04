@echo off
setlocal enabledelayedexpansion
title Vessence Installer for Windows
color 0F

echo.
echo  ====================================
echo    Vessence Installer for Windows
echo  ====================================
echo.

:: ── Check for Docker Desktop ──────────────────────────────────────────
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Docker is not installed or not in PATH.
    echo.
    echo      Vessence requires Docker Desktop to run.
    echo      Download it from: https://www.docker.com/products/docker-desktop/
    echo.
    echo      After installing Docker Desktop:
    echo        1. Launch Docker Desktop and wait for it to start
    echo        2. Run this installer again
    echo.
    pause
    exit /b 1
)

:: ── Check Docker is running ───────────────────────────────────────────
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Docker is installed but not running.
    echo.
    echo      Please start Docker Desktop and wait until it says "Docker Desktop is running",
    echo      then run this installer again.
    echo.
    pause
    exit /b 1
)

echo  [OK] Docker is installed and running.
echo.

:: ── Choose AI provider for Jane ─────────────────────────────────────
echo  ------------------------------------
echo    Choose Jane's AI provider
echo  ------------------------------------
echo.
echo    1. Gemini  (free — uses your Google API key)
echo    2. Claude  (best for coding — requires Anthropic API key)
echo    3. OpenAI  (GPT models — requires OpenAI API key)
echo.

set "JANE_BRAIN=gemini"
set "JANE_WEB_PERMISSIONS=0"
set /p PROVIDER_CHOICE="  Enter 1, 2, or 3 [default: 1]: "

if "%PROVIDER_CHOICE%"=="2" (
    set "JANE_BRAIN=claude"
    set "JANE_WEB_PERMISSIONS=1"
    echo.
    echo  [OK] Jane will use Claude Code. Web permission gating enabled.
) else if "%PROVIDER_CHOICE%"=="3" (
    set "JANE_BRAIN=openai"
    echo.
    echo  [OK] Jane will use OpenAI.
) else (
    echo.
    echo  [OK] Jane will use Gemini (default).
)
echo.

:: ── Set up directory ──────────────────────────────────────────────────
set "INSTALL_DIR=%USERPROFILE%\vessence"

echo  Install directory: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

:: ── Copy all files (source, Dockerfiles, configs) ───────────────────
echo  Copying files...
xcopy /s /e /y /q "%~dp0*" "%INSTALL_DIR%\" >nul

echo  [OK] Files copied to %INSTALL_DIR%
echo.

:: ── Create .env with provider selection ──────────────────────────────
if not exist "%INSTALL_DIR%\runtime" mkdir "%INSTALL_DIR%\runtime"
if not exist "%INSTALL_DIR%\vault" mkdir "%INSTALL_DIR%\vault"
if not exist "%INSTALL_DIR%\runtime\.env" (
    echo  Creating .env with your provider selection...
    (
        echo # Vessence runtime - created by installer
        echo JANE_BRAIN=!JANE_BRAIN!
        echo JANE_WEB_PERMISSIONS=!JANE_WEB_PERMISSIONS!
    ) > "%INSTALL_DIR%\runtime\.env"
    echo  [OK] .env created with JANE_BRAIN=!JANE_BRAIN!
) else (
    echo  [OK] Existing .env found, keeping it.
    echo      Provider selection will be available in the onboarding wizard.
)
echo.

:: ── Build and start ──────────────────────────────────────────────────
echo  Building and starting Vessence (this may take a few minutes on first run)...
echo.
cd /d "%INSTALL_DIR%"
docker compose build --no-cache
if %errorlevel% neq 0 (
    echo.
    echo  [!] Failed to build Vessence images. Check the error above.
    pause
    exit /b 1
)

docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo  [!] Failed to build/start Vessence. Check the error above.
    echo      Make sure Docker Desktop is running and you have internet access.
    pause
    exit /b 1
)

echo.
echo  ====================================
echo    Vessence is running!
echo  ====================================
echo.
echo    Jane's brain: !JANE_BRAIN!
echo.
echo    Onboarding:  http://localhost:3000
echo    Jane:        http://jane.localhost
echo    (Vault is accessible through Jane's interface)
echo.
echo    To stop:   docker compose down
echo    To start:  docker compose up -d
echo.

:: ── Open browser ──────────────────────────────────────────────────────
start http://localhost:3000

pause
