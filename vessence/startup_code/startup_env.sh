#!/usr/bin/env bash
# Shared runtime bootstrap for startup scripts.
#
# This keeps path resolution (vessense paths + python interpreter) consistent
# across all startup entrypoints.

startup_bootstrap_env() {
    local home_fallback
    local fallback_user_root="/home/chieh"

    home_fallback="$(getent passwd "$(id -u)" | cut -d: -f6 2>/dev/null || true)"
    HOME_DIR="${HOME_DIR:-${HOME:-$home_fallback}}"
    HOME_DIR="${HOME_DIR:-/home/$(id -un)}"
    fallback_user_root="${fallback_user_root%/}"

    AMBIENT_BASE="${AMBIENT_BASE:-$HOME_DIR/ambient}"

    local default_vessence_home="$AMBIENT_BASE/vessence"
    if [ ! -d "$default_vessence_home" ] && [ -d "$fallback_user_root/vessence" ]; then
        default_vessence_home="$fallback_user_root/vessence"
    fi
    VESSENCE_HOME="${VESSENCE_HOME:-$default_vessence_home}"

    local default_vessence_data_home="$AMBIENT_BASE/vessence-data"
    if [ ! -d "$default_vessence_data_home" ] && [ -d "$fallback_user_root/vessence-data" ]; then
        default_vessence_data_home="$fallback_user_root/vessence-data"
    fi
    VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$default_vessence_data_home}"

    local default_vault_home="$AMBIENT_BASE/vault"
    if [ ! -d "$default_vault_home" ] && [ -d "$fallback_user_root/vault" ]; then
        default_vault_home="$fallback_user_root/vault"
    fi
    VAULT_HOME="${VAULT_HOME:-$default_vault_home}"

    export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
    export AMBIENT_HOME="${AMBIENT_HOME:-$VESSENCE_DATA_HOME}"

    VENV_BIN="${VENV_BIN:-$HOME_DIR/google-adk-env/adk-venv/bin}"
    if [ ! -x "$VENV_BIN/python" ] && [ -x "$fallback_user_root/google-adk-env/adk-venv/bin/python" ]; then
        VENV_BIN="$fallback_user_root/google-adk-env/adk-venv/bin"
    fi
    PYTHON_BIN="${PYTHON_BIN:-$VENV_BIN/python}"

    export VENV_BIN PYTHON_BIN HOME_DIR AMBIENT_BASE
}
