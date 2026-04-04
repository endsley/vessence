@echo off
setlocal enabledelayedexpansion
title Vessence Installer for Windows
color 0F
set "NONINTERACTIVE=%VESSENCE_NONINTERACTIVE%"
set "SKIP_BROWSER=%VESSENCE_SKIP_BROWSER%"
set "SKIP_COPY=%VESSENCE_SKIP_COPY%"
set "PROVIDER_CHOICE=%VESSENCE_PROVIDER_CHOICE%"

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
    if not "%NONINTERACTIVE%"=="1" pause
    exit /b 1
)

:: ── Check docker compose ──────────────────────────────────────────────
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Docker Compose plugin not found.
    echo.
    echo      Update Docker Desktop to a recent version and make sure
    echo      the Compose plugin is enabled, then run this installer again.
    echo.
    if not "%NONINTERACTIVE%"=="1" pause
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
if not defined PROVIDER_CHOICE set /p PROVIDER_CHOICE="  Enter 1, 2, or 3 [default: 1]: "

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
    echo  [OK] Jane will use Gemini ^(default^).
)
echo.

:: ── Set up directory ──────────────────────────────────────────────────
if defined VESSENCE_INSTALL_DIR (
    set "INSTALL_DIR=%VESSENCE_INSTALL_DIR%"
) else (
    set "INSTALL_DIR=%USERPROFILE%\vessence"
)

echo  Install directory: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

:: ── Copy all files (source, Dockerfiles, configs) ───────────────────
if "%SKIP_COPY%"=="1" (
    echo  [OK] Copy step skipped by VESSENCE_SKIP_COPY=1.
) else (
    if /i "%~dp0"=="%INSTALL_DIR%\\" (
        echo  [OK] Installer is already running from %INSTALL_DIR%, skipping file copy.
    ) else (
        echo  Copying files...
        xcopy /s /e /y /i /h /q "%~dp0*" "%INSTALL_DIR%\\" >nul
        if errorlevel 4 (
            echo.
            echo  [!] Failed to copy installer files into %INSTALL_DIR%.
            if not "%NONINTERACTIVE%"=="1" pause
            exit /b 1
        )
        if not exist "%INSTALL_DIR%\docker-compose.yml" (
            echo.
            echo  [!] Installer copy completed but docker-compose.yml is missing in %INSTALL_DIR%.
            if not "%NONINTERACTIVE%"=="1" pause
            exit /b 1
        )
        if not exist "%INSTALL_DIR%\.env.example" (
            echo.
            echo  [!] Installer copy completed but .env.example is missing in %INSTALL_DIR%.
            if not "%NONINTERACTIVE%"=="1" pause
            exit /b 1
        )
        echo  [OK] Files copied to %INSTALL_DIR%
    )
)
echo.

:: ── Install AI agent config files ────────────────────────────────────
echo  Installing AI agent configuration files...
if exist "%INSTALL_DIR%\agent_configs" (
    if exist "%INSTALL_DIR%\agent_configs\CLAUDE.md" (
        copy /y "%INSTALL_DIR%\agent_configs\CLAUDE.md" "%USERPROFILE%\CLAUDE.md" >nul
        echo    [OK] CLAUDE.md installed
    )
    if exist "%INSTALL_DIR%\agent_configs\AGENTS.md" (
        copy /y "%INSTALL_DIR%\agent_configs\AGENTS.md" "%USERPROFILE%\AGENTS.md" >nul
        echo    [OK] AGENTS.md installed
    )
    if exist "%INSTALL_DIR%\agent_configs\GEMINI.md" (
        if not exist "%USERPROFILE%\.gemini" mkdir "%USERPROFILE%\.gemini"
        copy /y "%INSTALL_DIR%\agent_configs\GEMINI.md" "%USERPROFILE%\.gemini\GEMINI.md" >nul
        echo    [OK] GEMINI.md installed
    )
    echo    [OK] Agent configs installed
) else (
    echo    [SKIP] No agent_configs directory found
)
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
    if not "%NONINTERACTIVE%"=="1" pause
    exit /b 1
)

docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo  [!] Failed to build/start Vessence. Check the error above.
    echo      Make sure Docker Desktop is running and you have internet access.
    if not "%NONINTERACTIVE%"=="1" pause
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
echo    Jane:        http://localhost:8081
echo    Vault:       http://localhost:8081/vault
echo    (Vault is accessible through Jane's interface)
echo.
echo    To stop:   docker compose down
echo    To start:  docker compose up -d
echo.

echo  Waiting for onboarding to become ready at http://localhost:3000 ...
set "ONBOARDING_READY="
:: Extend to 300 seconds (5 minutes) for first-boot image/CLI setup
for /L %%I in (1,1,300) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "try { $r = Invoke-WebRequest -UseBasicParsing http://localhost:3000/health -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "ONBOARDING_READY=1"
        goto :onboarding_ready
    )
    timeout /t 1 /nobreak >nul
)

if not defined ONBOARDING_READY (
    echo.
    echo  [!] Onboarding did not become ready within 120 seconds.
    echo      Recent onboarding/jane logs:
    docker compose ps onboarding jane
    docker compose logs --tail 60 onboarding jane
    if not "%NONINTERACTIVE%"=="1" pause
    exit /b 1
)

:onboarding_ready
echo  [OK] Onboarding is ready.

:: ── Open browser ──────────────────────────────────────────────────────
if not "%SKIP_BROWSER%"=="1" start "" "http://localhost:3000"

if not "%NONINTERACTIVE%"=="1" pause
