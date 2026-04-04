@echo off
setlocal enabledelayedexpansion
title Vessence Uninstaller for Windows
color 0F

echo.
echo  ====================================
echo    Vessence Uninstaller for Windows
echo  ====================================
echo.
echo  This will:
echo    - Stop all Vessence containers
echo    - Remove Docker images and volumes
echo    - Delete the Vessence install folder
echo.

set "INSTALL_DIR=%USERPROFILE%\vessence"

:: ── Confirm ─────────────────────────────────────────────────────────
set /p CONFIRM="  Are you sure you want to uninstall Vessence? (Y/n): "
if "%CONFIRM%"=="" set "CONFIRM=y"
if /i not "%CONFIRM%"=="y" (
    echo  Cancelled.
    pause
    exit /b 0
)

echo.

:: ── Stop and remove containers ──────────────────────────────────────
if exist "%INSTALL_DIR%\docker-compose.yml" (
    echo  Stopping Vessence containers...
    cd /d "%INSTALL_DIR%"
    docker compose down --rmi all --volumes 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] Containers stopped, images and volumes removed.
    ) else (
        echo  [!] Some containers may not have been removed. Continuing cleanup...
    )
) else (
    echo  No docker-compose.yml found. Skipping container cleanup.
)
echo.

:: ── Remove install directory ────────────────────────────────────────
if exist "%INSTALL_DIR%" (
    echo  Removing %INSTALL_DIR%...
    cd /d "%USERPROFILE%"
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    if not exist "%INSTALL_DIR%" (
        echo  [OK] Install directory removed.
    ) else (
        echo  [!] Could not fully remove %INSTALL_DIR%. Some files may be in use.
        echo      Try closing any open files and delete the folder manually.
    )
) else (
    echo  Install directory not found. Nothing to remove.
)

echo.
echo  ====================================
echo    Vessence has been uninstalled.
echo  ====================================
echo.
pause
