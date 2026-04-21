#!/usr/bin/env python3
"""
build_windows_exe.py — Build a Windows .exe installer from the latest
vessence-windows-installer-*.zip using NSIS (makensis).

Strategy: embed the ZIP as a single blob inside the .exe. On install,
PowerShell extracts it so NSIS never has to enumerate 32K source files.

Outputs:  marketing_site/downloads/vessence-windows-installer-v<VER>.exe
          marketing_site/downloads/vessence-windows-installer.exe  (alias)
Updates:  marketing_site/index.html and install.html download links
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VESSENCE_HOME = os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parent.parent))
DOWNLOADS_DIR = Path(VESSENCE_HOME) / "marketing_site" / "downloads"

# NSIS script — includes the ZIP as one blob and extracts via PowerShell
NSIS_SCRIPT_TEMPLATE = r"""
!define PRODUCT_NAME "Vessence"
!define PRODUCT_VERSION "{version}"
!define PRODUCT_PUBLISHER "Vessences"
!define PRODUCT_URL "https://vessences.com"
!define INST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vessence"

Name "${{PRODUCT_NAME}} ${{PRODUCT_VERSION}}"
OutFile "{outfile}"
InstallDir "$LOCALAPPDATA\Vessence"
InstallDirRegKey HKCU "${{INST_KEY}}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ── Pages ────────────────────────────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to Vessence ${{PRODUCT_VERSION}} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will install Vessence on your computer.$\r$\n$\r$\nVessence requires Docker Desktop to run. If you don$\'t have it yet, the installer will guide you to download it.$\r$\n$\r$\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TEXT "Vessence ${{PRODUCT_VERSION}} has been installed.$\r$\n$\r$\nClick Finish to launch the setup wizard.$\r$\n$\r$\nMake sure Docker Desktop is running before clicking Finish."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchSetup
!define MUI_FINISHPAGE_RUN_TEXT "Launch Vessence setup wizard now"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

; ── Install section ──────────────────────────────────────────────────────────
Section "Vessence" SecMain
    SetOutPath "$INSTDIR"

    ; Drop the bundled ZIP
    File "{zip_path}"

    ; Extract it with PowerShell (avoids NSIS having to handle 32K source files)
    DetailPrint "Extracting Vessence files..."
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command \
        "Expand-Archive -Path \"$INSTDIR\{zip_filename}\" -DestinationPath \"$INSTDIR\" -Force; \
         $inner = Join-Path \"$INSTDIR\" \"vessence\"; \
         if (Test-Path $inner) {{ \
           Get-ChildItem $inner | Move-Item -Destination \"$INSTDIR\" -Force; \
           Remove-Item $inner -Recurse -Force \
         }}"'
    Pop $0
    ${{If}} $0 != 0
        MessageBox MB_OK|MB_ICONEXCLAMATION "Extraction failed (code $0). Try running as Administrator."
        Abort
    ${{EndIf}}

    ; Clean up the ZIP
    Delete "$INSTDIR\{zip_filename}"

    ; Desktop shortcut — launches Install Vessence.bat
    CreateShortCut "$DESKTOP\Vessence.lnk" \
        "cmd.exe" '/c "cd /d \"$INSTDIR\" && \"Install Vessence.bat\""' \
        "" 0 SW_SHOWMINIMIZED

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\Vessence"
    CreateShortCut "$SMPROGRAMS\Vessence\Start Vessence.lnk" \
        "cmd.exe" '/c "cd /d \"$INSTDIR\" && \"Install Vessence.bat\""' \
        "" 0 SW_SHOWMINIMIZED
    CreateShortCut "$SMPROGRAMS\Vessence\Uninstall Vessence.lnk" "$INSTDIR\uninstall.exe"

    ; Register uninstaller in Programs & Features
    WriteUninstaller "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "${{INST_KEY}}" "DisplayName"     "Vessence ${{PRODUCT_VERSION}}"
    WriteRegStr HKCU "${{INST_KEY}}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "${{INST_KEY}}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${{INST_KEY}}" "Publisher"       "${{PRODUCT_PUBLISHER}}"
    WriteRegStr HKCU "${{INST_KEY}}" "URLInfoAbout"    "${{PRODUCT_URL}}"
    WriteRegStr HKCU "${{INST_KEY}}" "DisplayVersion"  "${{PRODUCT_VERSION}}"
SectionEnd

; ── Finish page launcher ─────────────────────────────────────────────────────
Function LaunchSetup
    ExecShell "open" "cmd.exe" '/c "cd /d \"$INSTDIR\" && \"Install Vessence.bat\""' SW_SHOW
FunctionEnd

; ── Uninstall section ────────────────────────────────────────────────────────
Section "Uninstall"
    ExecWait 'cmd /c "cd /d \"$INSTDIR\" && docker compose down --rmi all --volumes"'
    Delete "$DESKTOP\Vessence.lnk"
    RMDir /r "$SMPROGRAMS\Vessence"
    RMDir /r "$INSTDIR"
    DeleteRegKey HKCU "${{INST_KEY}}"
SectionEnd
"""


def find_latest_zip() -> Path:
    zips = sorted(DOWNLOADS_DIR.glob("vessence-windows-installer-v*.zip"), reverse=True)
    if not zips:
        sys.exit("ERROR: No vessence-windows-installer-v*.zip found in downloads/")
    return zips[0]


def extract_version(zip_path: Path) -> str:
    m = re.search(r"v(\d+\.\d+\.\d+)", zip_path.name)
    return m.group(1) if m else "0.0.0"


def update_download_links(exe_name: str):
    for html_file in ["index.html", "install.html"]:
        path = Path(VESSENCE_HOME) / "marketing_site" / html_file
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        updated = re.sub(r"vessence-windows-installer-v[\d.]+\.exe", exe_name, content)
        if updated != content:
            path.write_text(updated, encoding="utf-8")
            print(f"  Updated link in {html_file}")


def add_windows_download_if_missing(exe_name: str):
    """Add a Windows download button to install.html if one doesn't exist yet."""
    path = Path(VESSENCE_HOME) / "marketing_site" / "install.html"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if "windows" in content.lower() and ".exe" in content:
        return  # already there

    android_btn = 'href="https://jane.vessences.com/downloads/vessences-android'
    if android_btn not in content:
        return

    windows_btn = (
        f'\n          <a class="button button-secondary" '
        f'href="https://jane.vessences.com/downloads/{exe_name}" '
        f'data-vault-download="windows-latest">Download Windows .exe</a>'
    )
    updated = content.replace(
        android_btn,
        windows_btn + "\n          " + 'href="https://jane.vessences.com/downloads/vessences-android',
    )
    path.write_text(updated, encoding="utf-8")
    print("  Added Windows download button to install.html")


def build_exe(zip_path: Path, version: str) -> Path:
    exe_name = f"vessence-windows-installer-v{version}.exe"
    out_exe = DOWNLOADS_DIR / exe_name
    alias = DOWNLOADS_DIR / "vessence-windows-installer.exe"

    with tempfile.TemporaryDirectory() as tmpdir:
        nsis_script = NSIS_SCRIPT_TEMPLATE.format(
            version=version,
            outfile=str(out_exe),
            zip_path=str(zip_path),
            zip_filename=zip_path.name,
        )

        nsis_file = Path(tmpdir) / "installer.nsi"
        nsis_file.write_text(nsis_script, encoding="utf-8")

        print("  Running makensis (this may take a minute — LZMA compressing the ZIP)...")
        result = subprocess.run(
            ["makensis", str(nsis_file)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print("NSIS stderr:", result.stderr[-3000:])
            print("NSIS stdout:", result.stdout[-3000:])
            sys.exit(f"ERROR: makensis failed (exit {result.returncode})")

    # Alias for stable download URL
    if alias.exists():
        alias.unlink()
    shutil.copy2(str(out_exe), str(alias))

    return out_exe


def main():
    zip_path = find_latest_zip()
    version = extract_version(zip_path)
    zip_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Building Windows .exe installer v{version} from {zip_path.name} ({zip_mb:.0f} MB)...")

    out_exe = build_exe(zip_path, version)
    size_mb = out_exe.stat().st_size / (1024 * 1024)
    print(f"  Built: {out_exe.name} ({size_mb:.1f} MB)")

    update_download_links(out_exe.name)
    add_windows_download_if_missing(out_exe.name)

    print(f"\n  ✓ {out_exe.name} ready in marketing_site/downloads/")
    print(f"  ✓ Alias: vessence-windows-installer.exe")


if __name__ == "__main__":
    main()
