#!/usr/bin/env python3
"""main.py — Jane web UI (chat with Jane / Claude Code). Runs on port 8081.
Shares all templates and static assets with vault_web so UI changes propagate to both.
"""
import os

# Force HuggingFace Hub and Transformers to fully offline mode BEFORE any
# library that might import them (sentence_transformers, transformers,
# huggingface_hub). Our local embedding model cache at
# ~/.cache/huggingface/hub is authoritative — we do NOT want the Stage 1
# classifier warmup phoning home to HuggingFace on every cold start to
# check if the cached revision is stale. That added ~6s of HTTP HEAD
# latency to every warmup. Override by unsetting these env vars if you
# need to upgrade the embedding model and pull a fresh snapshot.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Point Playwright at the Vessence-scoped browser install so
# agent_skills.web_automation can launch Chromium without relying on
# ~/.cache/ms-playwright. See configs/project_specs/web_automation_skill.md
# section 9.1 — install location is deliberate so venv rebuilds don't
# evict the 180 MB browser binaries.
_vess_data_home = os.environ.get(
    "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"),
)
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(_vess_data_home, "playwright_browsers"),
)

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, Cookie, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import asyncio
import aiofiles
import hashlib
import json
import logging
import re
import subprocess
import tempfile
import time
import html
try:
    import chromadb
except ImportError:
    chromadb = None

CODE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_ROOT))
sys.path.insert(0, str(CODE_ROOT / "vault_web"))  # share vault_web modules

# ── Logging setup ─────────────────────────────────────────────────────────────
_DATA_HOME = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
_LOG_DIR = Path(_DATA_HOME) / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

from logging.handlers import RotatingFileHandler as _RotatingFileHandler
_file_handler = _RotatingFileHandler(
    _LOG_DIR / "jane_web.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_root_logger = logging.getLogger()
_root_logger.addHandler(_file_handler)
_root_logger.setLevel(logging.INFO)
# Ensure jane.proxy logger also writes here
logging.getLogger("jane.proxy").setLevel(logging.DEBUG)

_logger = logging.getLogger("jane.web")
_logger.info("=== Jane Web starting (PID %d) ===", os.getpid())

JANE_RESPONSE_WAIT_SECONDS = int(os.environ.get("JANE_RESPONSE_WAIT_SECONDS", "7200"))


# Note: port cleanup was previously done here at import time via a hardcoded
# _clear_port_if_occupied(8081). That was removed 2026-04-16 because it
# unconditionally killed whatever process held port 8081 — including the
# legitimate systemd-managed jane-web server — whenever ANY uvicorn instance
# started (e.g. the ping-pong server on 8084 during graceful_restart.sh).
# Port cleanup is handled by two proper owners now:
#   - systemd unit ExecStartPre runs `fuser -k 8081/tcp` before a managed start
#   - graceful_restart.sh kills stragglers on its own target port (8081/8084)
# uvicorn's own bind-or-fail behavior is sufficient beyond those two hooks.


from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH, VAULT_DIR, TOOLS_DIR, ESSENCES_DIR, VESSENCE_DATA_HOME, ADD_FACT_SCRIPT, ADK_VENV_PYTHON, LOGS_DIR, PROMPT_LIST_PATH, get_chroma_client, normalize_frontier_provider, VAULT_ENC_PATH, CHALLENGE_PATH
from agent_skills.secret_store import SecretStore


load_dotenv(ENV_FILE_PATH)

from vault_web.database import init_db, get_db
from vault_web.auth import (
    create_session, validate_session,
    is_device_trusted, register_trusted_device,
    get_trusted_device_by_id, get_trusted_device_by_fingerprint,
    get_session_user, verify_otp,
    get_trusted_devices, revoke_device,
    device_fingerprint_from_request,
)
from vault_web.oauth import oauth, allowed_email, build_external_url, google_oauth_configured
from vault_web.files import (
    list_directory, get_file_metadata, update_description,
    generate_thumbnail, get_last_change_timestamp, safe_vault_path, is_text, TEXT_SIZE_LIMIT, get_mime,
    make_descriptive_filename, upsert_file_index_entry, delete_vault_file,
)
from vault_web.share import create_share, validate_share, list_shares, revoke_share
from vault_web.playlists import list_playlists, get_playlist, create_playlist, update_playlist, delete_playlist
try:
    from .announcements import AnnouncementsLog
    from .app_settings import JsonSettingsStore
    from .auth_cookies import apply_auth_cookie_spec, auth_cookie_specs
    from .auth_devices import trusted_device_id_for_fingerprint
    from .auth_sessions import (
        bootstrap_session_for_request as _bootstrap_session_for_request,
        chat_stream_session_for_request as _chat_stream_session_for_request,
        request_has_share_or_auth as _request_has_share_or_auth,
        required_session_id_for_request as _required_session_id_for_request,
    )
    from .cache_control import cache_control_header
    from .canonical_docs import (
        CANONICAL_DOCS_WHITELIST as _DOCS_WHITELIST,
        read_doc_body as _read_doc_body,
        read_doc_meta as _read_doc_meta,
    )
    from .briefing_articles import build_briefing_articles_response
    from .briefing_media import (
        briefing_archive_path,
        briefing_image_candidates,
        daily_briefing_audio_dir,
        daily_briefing_image_dir,
        is_archive_date,
        is_briefing_identifier,
        select_briefing_audio,
    )
    from .briefing_requests import (
        briefing_submit_values,
        briefing_text_summary_values,
        briefing_url_value,
        is_http_url,
    )
    from .briefing_saved import (
        daily_briefing_article_path,
        saved_article_list,
        saved_article_record,
        saved_articles_index_path,
        saved_category_names,
        vault_saved_article_path,
    )
    from .cli_login_helpers import (
        clean_cli_output as _clean_cli_output,
        cli_output_lines as _cli_output_lines,
        apply_claude_refresh_tokens as _apply_claude_refresh_tokens,
        base64url_no_padding as _base64url_no_padding,
        claude_oauth_authorization_url as _claude_oauth_authorization_url,
        claude_oauth_refresh_request_spec as _claude_oauth_refresh_request_spec,
        claude_refresh_token_from_credentials as _claude_refresh_token_from_credentials,
        cli_binary_for_provider as _cli_binary_for_provider,
        cli_credentials_path as _cli_credentials_path,
        write_cli_credentials as _write_cli_credentials,
        cli_login_candidates as _cli_login_candidates,
        cli_login_debug_payload as _cli_login_debug_payload,
        cli_login_output_update as _cli_login_output_update,
        CLI_LOGIN_IGNORED_PORTS as _CLI_LOGIN_IGNORED_PORTS,
        extract_claude_auth_url as _extract_claude_auth_url,
        extract_oauth_state as _extract_oauth_state,
        gemini_oauth_authorization_url as _gemini_oauth_authorization_url,
        mask_email as _mask_email,
        oauth_login_credentials_for_code as _oauth_login_credentials_for_code,
        pkce_code_challenge as _pkce_code_challenge,
        process_tree_socket_port as _process_tree_socket_port,
        proc_net_listen_socket_candidates as _proc_net_listen_socket_candidates,
        provider_auth_status_details as _provider_auth_status_details_impl,
        read_cli_transcript_lines as _read_cli_transcript_lines,
        ss_login_callback_port as _ss_login_callback_port,
        submit_cli_login_code_to_stdin as _submit_cli_login_code_to_stdin,
    )
    from .conversation_keys import (
        resolve_conversation_key_payload as _resolve_conversation_key_payload,
        scoped_conversation_session_id as _resolve_scoped_conversation_session_id,
    )
    from .contact_search import aggregate_contact_rows
    from .device_commands import DeviceCommandQueue
    from .device_diagnostics import DeviceDiagnosticsLog
    from .env_settings import EnvFileSettings
    from .essence_helpers import (
        essence_list_item,
        essence_search_dirs,
        essence_tool_command,
        essence_tool_error_payload,
        essence_tool_success_payload,
        find_essence_by_name,
        find_essence_match,
        find_essence_page_target,
        find_essence_tools_path,
        read_active_essences,
        read_essence_detail_manifest,
        read_essence_manifest_summary,
        loaded_essence_payload,
        remove_active_essence,
        write_active_essences,
    )
    from .file_browser_helpers import (
        FILE_TYPE_EXTENSIONS as _FILE_TYPE_EXTENSIONS,
        MIME_TO_SUBDIR as _MIME_TO_SUBDIR,
        detect_file_type as _detect_file_type,
        paginate_listing as _paginate_listing,
        range_response as _range_response,
        route_subdir as _route_subdir,
    )
    from .file_search_helpers import (
        filename_search_results as _filename_search_results,
        merge_index_search_results as _merge_index_search_results,
    )
    from .instant_commands import instant_command_response
    from .chat_stream_dedupe import (
        begin_turn_dedupe,
        iter_replay_ndjson,
    )
    from .chat_stream_events import (
        done_stream_chunk as _done_stream_chunk,
        instant_command_stream_chunks as _instant_command_stream_chunks,
        offloaded_task_stream_chunks as _offloaded_task_stream_chunks,
        status_stream_chunk as _status_stream_chunk,
    )
    from .chat_stream_limits import stream_limit_exceeded
    from .chat_stream_runner import normal_chat_stream_chunks as _normal_chat_stream_chunks
    from .marketplace_helpers import (
        is_safe_listing_key,
        is_safe_marketplace_name,
        is_safe_photo_name,
        marketplace_create_search_payload,
        marketplace_refresh_command,
        marketplace_refresh_env,
        marketplace_refresh_log_header,
        marketplace_refresh_log_path,
    )
    from .permission_helpers import (
        permission_pending_entry,
        permission_request_args,
        permission_response_args,
        permission_wait_payload,
    )
    from .pipeline_selection import (
        should_use_v2_pipeline as _should_use_v2_pipeline,
        should_use_v3_pipeline as _should_use_v3_pipeline,
    )
    from .model_settings import (
        build_model_settings_payload,
        current_provider_payload,
        model_save_target,
    )
    from .music_playlists import (
        cleanup_temporary_playlists as _cleanup_temporary_playlists_impl,
        find_matching_playlist,
        music_playlist_from_query as _music_playlist_from_query,
        normalize_music_query,
        playlist_name_for_query,
        playlist_tracks,
        real_user_playlists,
        select_music_files,
        should_delete_temporary_playlist,
    )
    from .ollama_warmup import (
        heartbeat_poll_seconds as _heartbeat_poll_seconds,
        local_llm_prewarm_payload as _local_llm_prewarm_payload,
        ollama_generate_endpoint as _ollama_generate_endpoint,
        ollama_heartbeat_payload as _ollama_heartbeat_payload,
        should_skip_heartbeat as _should_skip_heartbeat,
    )
    from .user_access import (
        is_user_admin as _resolve_is_user_admin,
        clean_seed_memories as _clean_seed_memories,
        managed_user_display_name as _managed_user_display_name,
        normalize_managed_user_email as _normalize_managed_user_email,
        public_user_config as _public_user_config,
        request_vault_root as _resolve_request_vault_root,
        require_capability as _resolve_require_capability,
        user_memory_path as _resolve_user_memory_path,
        user_vault_context as _resolve_user_vault_context,
    )
    from .user_identity import (
        configured_admin_variants as _configured_admin_variants,
        default_user_id as _default_user_id,
        identity_variants as _identity_variants,
    )
    from .jane_proxy import send_message, stream_message, get_tunnel_url, prewarm_session, end_session, run_prefetch_memory
    from .ra_reports import RA_REPORT_GRANT_SECONDS, RA_REPORT_ID_RE, RA_REPORT_TOKEN_SECONDS, RaReportAccess
    from .rate_limit import (
        RATE_LIMIT_AUTH_PATHS as _RATE_LIMIT_AUTH_PATHS,
        RATE_LIMIT_CHAT_PATHS as _RATE_LIMIT_CHAT_PATHS,
        RATE_LIMIT_EXEMPT_PATHS as _RATE_LIMIT_EXEMPT_PATHS,
        RATE_LIMIT_UPLOAD_PATHS as _RATE_LIMIT_UPLOAD_PATHS,
        RateLimiter,
        rate_limit_category as _rate_limit_category,
    )
    from .release_downloads import ReleaseDownloads
    from .request_helpers import (
        client_ip as _client_ip,
        cookie_secure_flag as _cookie_secure_flag,
        is_android_webview_request,
        is_local_control_ip as _is_local_control_ip,
        is_local_browser_access as _is_local_browser_access,
        is_local_request as _is_local_request,
        is_single_user_no_auth_mode as _is_single_user_no_auth_mode,
        session_log_id as _session_log_id,
    )
    from .request_logging import (
        idle_state_record as _idle_state_record,
        is_polling_path as _is_polling_path,
        request_error_context as _request_error_context,
        should_touch_idle_state as _should_touch_idle_state,
    )
    from .session_init import session_init_stream_chunks as _session_init_stream_chunks
    from .self_healing_reports import (
        normalize_self_healing_report,
        self_healing_report_authorized,
    )
    from .sms_classification import classify_synced_message
    from .sync_payloads import contact_alias_values, contact_insert_values, message_insert_values
    from .tax_helpers import (
        is_safe_tax_form_name,
        latest_tax_form_file,
        tax_interview_answer_args,
        tax_output_dir,
        tax_result_path,
        tax_tool_command,
        tax_tool_result_payload,
        tax_upload_document_args,
        tax_upload_path,
        tax_uploads_dir,
    )
    from .tts_chunks import split_tts_chunks
    from .tts_generation import (
        concatenate_wav_chunks as _concatenate_wav_chunks,
        tts_cached_media,
        tts_cache_paths,
        tts_chunk_wav_path,
        tts_combined_wav_path,
        tts_docker_command,
        tts_ffmpeg_command,
        tts_gpu_flags,
    )
    from .upload_helpers import (
        duplicate_upload_result,
        hash_index_entry,
        load_upload_hash_index,
        next_available_path,
        parse_upload_descriptions,
        upload_description,
        upload_memory_fact_command,
        upload_memory_fact_text,
        upload_safe_name,
        upload_subdir,
        upload_success_result,
        upload_work_activity_message,
        write_upload_hash_index,
    )
    from .web_automation_helpers import (
        automation_result_payload,
        web_plan_headless,
        web_plan_label,
        web_plan_profile_id,
        web_plan_raw_steps,
        web_plan_record_trace,
        web_plan_storage_state_path,
        web_plan_step_specs,
        web_profile_capture_values,
        web_profile_create_values,
        web_secret_create_values,
        web_secret_public_entry,
    )
except ImportError:
    from announcements import AnnouncementsLog
    from app_settings import JsonSettingsStore
    from auth_cookies import apply_auth_cookie_spec, auth_cookie_specs
    from auth_devices import trusted_device_id_for_fingerprint
    from auth_sessions import (
        bootstrap_session_for_request as _bootstrap_session_for_request,
        chat_stream_session_for_request as _chat_stream_session_for_request,
        request_has_share_or_auth as _request_has_share_or_auth,
        required_session_id_for_request as _required_session_id_for_request,
    )
    from cache_control import cache_control_header
    from canonical_docs import (
        CANONICAL_DOCS_WHITELIST as _DOCS_WHITELIST,
        read_doc_body as _read_doc_body,
        read_doc_meta as _read_doc_meta,
    )
    from briefing_articles import build_briefing_articles_response
    from briefing_media import (
        briefing_archive_path,
        briefing_image_candidates,
        daily_briefing_audio_dir,
        daily_briefing_image_dir,
        is_archive_date,
        is_briefing_identifier,
        select_briefing_audio,
    )
    from briefing_requests import (
        briefing_submit_values,
        briefing_text_summary_values,
        briefing_url_value,
        is_http_url,
    )
    from briefing_saved import (
        daily_briefing_article_path,
        saved_article_list,
        saved_article_record,
        saved_articles_index_path,
        saved_category_names,
        vault_saved_article_path,
    )
    from cli_login_helpers import (
        clean_cli_output as _clean_cli_output,
        cli_output_lines as _cli_output_lines,
        apply_claude_refresh_tokens as _apply_claude_refresh_tokens,
        base64url_no_padding as _base64url_no_padding,
        claude_oauth_authorization_url as _claude_oauth_authorization_url,
        claude_oauth_refresh_request_spec as _claude_oauth_refresh_request_spec,
        claude_refresh_token_from_credentials as _claude_refresh_token_from_credentials,
        cli_binary_for_provider as _cli_binary_for_provider,
        cli_credentials_path as _cli_credentials_path,
        write_cli_credentials as _write_cli_credentials,
        cli_login_candidates as _cli_login_candidates,
        cli_login_debug_payload as _cli_login_debug_payload,
        cli_login_output_update as _cli_login_output_update,
        CLI_LOGIN_IGNORED_PORTS as _CLI_LOGIN_IGNORED_PORTS,
        extract_claude_auth_url as _extract_claude_auth_url,
        extract_oauth_state as _extract_oauth_state,
        gemini_oauth_authorization_url as _gemini_oauth_authorization_url,
        mask_email as _mask_email,
        oauth_login_credentials_for_code as _oauth_login_credentials_for_code,
        pkce_code_challenge as _pkce_code_challenge,
        process_tree_socket_port as _process_tree_socket_port,
        proc_net_listen_socket_candidates as _proc_net_listen_socket_candidates,
        provider_auth_status_details as _provider_auth_status_details_impl,
        read_cli_transcript_lines as _read_cli_transcript_lines,
        ss_login_callback_port as _ss_login_callback_port,
        submit_cli_login_code_to_stdin as _submit_cli_login_code_to_stdin,
    )
    from conversation_keys import (
        resolve_conversation_key_payload as _resolve_conversation_key_payload,
        scoped_conversation_session_id as _resolve_scoped_conversation_session_id,
    )
    from contact_search import aggregate_contact_rows
    from device_commands import DeviceCommandQueue
    from device_diagnostics import DeviceDiagnosticsLog
    from env_settings import EnvFileSettings
    from essence_helpers import (
        essence_list_item,
        essence_search_dirs,
        essence_tool_command,
        essence_tool_error_payload,
        essence_tool_success_payload,
        find_essence_by_name,
        find_essence_match,
        find_essence_page_target,
        find_essence_tools_path,
        read_active_essences,
        read_essence_detail_manifest,
        read_essence_manifest_summary,
        loaded_essence_payload,
        remove_active_essence,
        write_active_essences,
    )
    from file_browser_helpers import (
        FILE_TYPE_EXTENSIONS as _FILE_TYPE_EXTENSIONS,
        MIME_TO_SUBDIR as _MIME_TO_SUBDIR,
        detect_file_type as _detect_file_type,
        paginate_listing as _paginate_listing,
        range_response as _range_response,
        route_subdir as _route_subdir,
    )
    from file_search_helpers import (
        filename_search_results as _filename_search_results,
        merge_index_search_results as _merge_index_search_results,
    )
    from instant_commands import instant_command_response
    from chat_stream_dedupe import (
        begin_turn_dedupe,
        iter_replay_ndjson,
    )
    from chat_stream_events import (
        done_stream_chunk as _done_stream_chunk,
        instant_command_stream_chunks as _instant_command_stream_chunks,
        offloaded_task_stream_chunks as _offloaded_task_stream_chunks,
        status_stream_chunk as _status_stream_chunk,
    )
    from chat_stream_limits import stream_limit_exceeded
    from chat_stream_runner import normal_chat_stream_chunks as _normal_chat_stream_chunks
    from marketplace_helpers import (
        is_safe_listing_key,
        is_safe_marketplace_name,
        is_safe_photo_name,
        marketplace_create_search_payload,
        marketplace_refresh_command,
        marketplace_refresh_env,
        marketplace_refresh_log_header,
        marketplace_refresh_log_path,
    )
    from permission_helpers import (
        permission_pending_entry,
        permission_request_args,
        permission_response_args,
        permission_wait_payload,
    )
    from pipeline_selection import (
        should_use_v2_pipeline as _should_use_v2_pipeline,
        should_use_v3_pipeline as _should_use_v3_pipeline,
    )
    from model_settings import (
        build_model_settings_payload,
        current_provider_payload,
        model_save_target,
    )
    from music_playlists import (
        cleanup_temporary_playlists as _cleanup_temporary_playlists_impl,
        find_matching_playlist,
        music_playlist_from_query as _music_playlist_from_query,
        normalize_music_query,
        playlist_name_for_query,
        playlist_tracks,
        real_user_playlists,
        select_music_files,
        should_delete_temporary_playlist,
    )
    from ollama_warmup import (
        heartbeat_poll_seconds as _heartbeat_poll_seconds,
        local_llm_prewarm_payload as _local_llm_prewarm_payload,
        ollama_generate_endpoint as _ollama_generate_endpoint,
        ollama_heartbeat_payload as _ollama_heartbeat_payload,
        should_skip_heartbeat as _should_skip_heartbeat,
    )
    from user_access import (
        is_user_admin as _resolve_is_user_admin,
        clean_seed_memories as _clean_seed_memories,
        managed_user_display_name as _managed_user_display_name,
        normalize_managed_user_email as _normalize_managed_user_email,
        public_user_config as _public_user_config,
        request_vault_root as _resolve_request_vault_root,
        require_capability as _resolve_require_capability,
        user_memory_path as _resolve_user_memory_path,
        user_vault_context as _resolve_user_vault_context,
    )
    from user_identity import (
        configured_admin_variants as _configured_admin_variants,
        default_user_id as _default_user_id,
        identity_variants as _identity_variants,
    )
    from jane_proxy import send_message, stream_message, get_tunnel_url, prewarm_session, end_session, run_prefetch_memory
    from ra_reports import RA_REPORT_GRANT_SECONDS, RA_REPORT_ID_RE, RA_REPORT_TOKEN_SECONDS, RaReportAccess
    from rate_limit import (
        RATE_LIMIT_AUTH_PATHS as _RATE_LIMIT_AUTH_PATHS,
        RATE_LIMIT_CHAT_PATHS as _RATE_LIMIT_CHAT_PATHS,
        RATE_LIMIT_EXEMPT_PATHS as _RATE_LIMIT_EXEMPT_PATHS,
        RATE_LIMIT_UPLOAD_PATHS as _RATE_LIMIT_UPLOAD_PATHS,
        RateLimiter,
        rate_limit_category as _rate_limit_category,
    )
    from release_downloads import ReleaseDownloads
    from request_helpers import (
        client_ip as _client_ip,
        cookie_secure_flag as _cookie_secure_flag,
        is_android_webview_request,
        is_local_control_ip as _is_local_control_ip,
        is_local_browser_access as _is_local_browser_access,
        is_local_request as _is_local_request,
        is_single_user_no_auth_mode as _is_single_user_no_auth_mode,
        session_log_id as _session_log_id,
    )
    from request_logging import (
        idle_state_record as _idle_state_record,
        is_polling_path as _is_polling_path,
        request_error_context as _request_error_context,
        should_touch_idle_state as _should_touch_idle_state,
    )
    from session_init import session_init_stream_chunks as _session_init_stream_chunks
    from self_healing_reports import (
        normalize_self_healing_report,
        self_healing_report_authorized,
    )
    from sms_classification import classify_synced_message
    from sync_payloads import contact_alias_values, contact_insert_values, message_insert_values
    from tax_helpers import (
        is_safe_tax_form_name,
        latest_tax_form_file,
        tax_interview_answer_args,
        tax_output_dir,
        tax_result_path,
        tax_tool_command,
        tax_tool_result_payload,
        tax_upload_document_args,
        tax_upload_path,
        tax_uploads_dir,
    )
    from tts_chunks import split_tts_chunks
    from tts_generation import (
        concatenate_wav_chunks as _concatenate_wav_chunks,
        tts_cached_media,
        tts_cache_paths,
        tts_chunk_wav_path,
        tts_combined_wav_path,
        tts_docker_command,
        tts_ffmpeg_command,
        tts_gpu_flags,
    )
    from upload_helpers import (
        duplicate_upload_result,
        hash_index_entry,
        load_upload_hash_index,
        next_available_path,
        parse_upload_descriptions,
        upload_description,
        upload_memory_fact_command,
        upload_memory_fact_text,
        upload_safe_name,
        upload_subdir,
        upload_success_result,
        upload_work_activity_message,
        write_upload_hash_index,
    )
    from web_automation_helpers import (
        automation_result_payload,
        web_plan_headless,
        web_plan_label,
        web_plan_profile_id,
        web_plan_raw_steps,
        web_plan_record_trace,
        web_plan_storage_state_path,
        web_plan_step_specs,
        web_profile_capture_values,
        web_profile_create_values,
        web_secret_create_values,
        web_secret_public_entry,
    )

# ── Shared UI: point directly at vault_web's static + templates ──────────────
VAULT_WEB_DIR = CODE_ROOT / "vault_web"
BASE_DIR = Path(__file__).parent
@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    await startup()
    try:
        yield
    finally:
        await shutdown()


_release_downloads = ReleaseDownloads(CODE_ROOT)
MARKETING_DIR = _release_downloads.marketing_dir
MARKETING_DOWNLOADS_DIR = _release_downloads.downloads_dir
ANDROID_VERSION, _ANDROID_VERSION_CODE = _release_downloads.read_android_version()
_release_downloads.log_startup_apk_status(_logger)
_find_latest = _release_downloads.find_latest
PUBLIC_RELEASE_DOWNLOADS = _release_downloads.public_release_downloads
_INSTALLER_GLOBS = _release_downloads.installer_globs
_resolve_android_apk_path = _release_downloads.resolve_android_apk_path

app = FastAPI(title="Jane", lifespan=_app_lifespan)
_session_secret = os.getenv("SESSION_SECRET_KEY", "")
if not _session_secret or _session_secret in ("changeme", "changeme-generate-a-real-secret"):
    import secrets as _secrets
    _session_secret = _secrets.token_hex(32)
    _logger.warning("SESSION_SECRET_KEY not set — using auto-generated key (sessions won't persist across restarts)")
app.add_middleware(SessionMiddleware, secret_key=_session_secret)
app.mount("/static", StaticFiles(directory=VAULT_WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=VAULT_WEB_DIR / "templates")
_rate_limiter = RateLimiter()


# ── Request logging middleware ────────────────────────────────────────────────
def _touch_idle_state():
    """Update idle_state.json so the prompt queue runner knows user is active."""
    try:
        import json as _j
        from jane.config import IDLE_STATE_PATH
        Path(IDLE_STATE_PATH).write_text(_j.dumps(_idle_state_record(time.time())))
    except Exception:
        pass

# ── Rate-limiting middleware ──────────────────────────────────────────────────
# Applied per-IP with different limits depending on the endpoint category.
# Localhost (prompt queue runner, internal tools) is always exempt.


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = _client_ip(request)
    # Exempt localhost (internal services like prompt queue runner)
    if _is_local_control_ip(ip):
        return await call_next(request)
    path = request.url.path
    category, max_req, window = _rate_limit_category(path)
    if category and max_req > 0:
        key = f"rl:{category}:{ip}"
        if not _rate_limiter.check(key, max_req, window):
            _logger.warning("Rate limited %s on %s (%s)", ip, path, category)
            return JSONResponse(
                {"error": "Rate limit exceeded. Please slow down."},
                status_code=429,
            )
    return await call_next(request)


@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = cache_control_header(request.url.path)
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    path = request.url.path
    method = request.method
    # Update idle state for non-polling requests (so queue runner knows user is active)
    is_poll = _is_polling_path(path)
    if _should_touch_idle_state(path, method):
        _touch_idle_state()
    try:
        response = await call_next(request)
        if not is_poll:
            elapsed_ms = int((time.time() - start) * 1000)
            _logger.info("%s %s → %d (%dms)", method, path, response.status_code, elapsed_ms)
        return response
    except Exception as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        _logger.exception("Unhandled error in %s %s after %dms: %s", method, path, elapsed_ms, exc)
        _dispatch_self_healing_exception(
            source="jane_web",
            exc=exc,
            request=request,
            context=_request_error_context(elapsed_ms=elapsed_ms, method=method, path=path),
        )
        raise


def _dispatch_self_healing_exception(
    *,
    source: str,
    exc: BaseException,
    request: Request,
    context: dict | None = None,
):
    """Fire-and-forget self-healing capture for request exceptions."""
    try:
        from agent_skills.self_healing import capture_exception
        task = asyncio.create_task(asyncio.to_thread(
            capture_exception,
            source=source,
            exc=exc,
            request=request,
            project_root=str(CODE_ROOT),
            context=context or {},
            tags=["fastapi", "server"],
        ))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception as heal_exc:
        _logger.warning("self-healing exception dispatch failed: %s", heal_exc)


def _dispatch_self_healing_report(
    *,
    source: str,
    category: str,
    message: str,
    payload: dict,
    request: Request,
    project_root: str | None = None,
    tags: list[str] | None = None,
):
    """Fire-and-forget self-healing capture for diagnostic reports."""
    try:
        from agent_skills.self_healing import capture_report
        task = asyncio.create_task(asyncio.to_thread(
            capture_report,
            source=source,
            category=category,
            message=message,
            payload=payload,
            request=request,
            project_root=project_root or str(CODE_ROOT),
            tags=tags or [],
        ))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception as heal_exc:
        _logger.warning("self-healing report dispatch failed: %s", heal_exc)

SESSION_COOKIE = "jane_session"
TRUSTED_DEVICE_COOKIE = "jane_trusted_device"
STATIC_DIR = VAULT_WEB_DIR / "static"
ANNOUNCEMENTS_PATH = Path(ENV_FILE_PATH).parent / "data" / "jane_announcements.jsonl"
RA_REPORTS_ROOT = Path(VAULT_DIR) / "research" / "rheumatoid_arthritis_remission" / "reports"
RA_HTML_REPORTS_DIR = RA_REPORTS_ROOT / "html"
_device_diagnostics_log = DeviceDiagnosticsLog(Path(LOGS_DIR) / "android_diagnostics.jsonl")
_announcements_log = AnnouncementsLog(ANNOUNCEMENTS_PATH)
_read_announcements = _announcements_log.read
_env_settings = EnvFileSettings(ENV_FILE_PATH)
_write_env_var = _env_settings.write_var
_add_allowed_google_email = _env_settings.add_allowed_google_email
_remove_allowed_google_email = _env_settings.remove_allowed_google_email


def _login_context(request: Request, **extra):
    ctx = {
        "request": request,
        "app_title": "Jane",
        "app_icon": "🧠",
        "app_subtitle": "Your long-lived technical partner",
        "footer_label": "Jane · Project Ambient",
        "google_oauth_enabled": google_oauth_configured(),
    }
    ctx.update(extra)
    return ctx


# ─── Init ─────────────────────────────────────────────────────────────────────

_background_tasks: set[asyncio.Task] = set()  # prevent GC of fire-and-forget tasks


async def startup():
    # Initialize and auto-unlock SecretStore
    store = SecretStore()
    if store.is_unlocked():
        # Inject SESSION_SECRET_KEY back into env for middleware if it was migrated
        s_secret = store.get("SESSION_SECRET_KEY")
        if s_secret:
            os.environ["SESSION_SECRET_KEY"] = s_secret
            _logger.info("SESSION_SECRET_KEY re-injected from SecretStore")

    init_db()
    _auto_load_essences()
    # Idempotency dedupe table for Android streaming chat retries (job_076).
    try:
        from jane_web import turn_dedupe
        turn_dedupe.init_schema()
    except Exception as _td_exc:
        _logger.warning("turn_dedupe init_schema failed: %s", _td_exc)
    # Start periodic reaper for stale Claude/Gemini sessions (prevents memory leaks)
    reaper = asyncio.create_task(_reap_stale_sessions_loop())
    _background_tasks.add(reaper)
    reaper.add_done_callback(_background_tasks.discard)
    _logger.info("Jane Web startup complete — database initialized, essences loaded, ready to serve")
    # Resume processing any unprocessed shared articles left from before a restart
    asyncio.create_task(_resume_shared_queue_if_needed())
    # Pre-warm the local LLM (qwen2.5:7b) — used by every Stage 2
    # handler + gate check + Stage 3 ack generator
    prewarm = asyncio.create_task(_prewarm_local_llm())
    _background_tasks.add(prewarm)
    prewarm.add_done_callback(_background_tasks.discard)
    # Heartbeat the local LLM every ~15s to keep the GPU power state +
    # Ollama runner pipeline hot. Evidence (2026-04-18): idle calls
    # after >30s pay a 5-20s cold-path penalty even with keep_alive=-1.
    # Disable by setting JANE_OLLAMA_HEARTBEAT_S=0.
    heartbeat = asyncio.create_task(_ollama_heartbeat_loop())
    _background_tasks.add(heartbeat)
    heartbeat.add_done_callback(_background_tasks.discard)
    # Keep the Stage 1 embedding model + memory_retrieval singleton hot
    # in GPU/RAM forever. Belt-and-suspenders against GPU idle-eviction
    # and a cheap liveness check.
    keepalive = asyncio.create_task(_embedding_keepalive_loop())
    _background_tasks.add(keepalive)
    keepalive.add_done_callback(_background_tasks.discard)
    # Start Standing Brain processes (3 tiers: light/medium/heavy)
    standing_brain_task = asyncio.create_task(_start_standing_brains())
    _background_tasks.add(standing_brain_task)
    standing_brain_task.add_done_callback(_background_tasks.discard)


async def _start_standing_brains():
    """Start the standing brain CLI process at service startup."""
    try:
        brain_name = normalize_frontier_provider(os.environ.get("JANE_BRAIN", "gemini"))
        if brain_name == "openai" and os.environ.get("JANE_WEB_STANDING_CODEX", "1") != "0":
            from llm_brain.v1.standing_codex import get_codex_app_server_manager
            manager = get_codex_app_server_manager()
            await manager.start()
            health = await manager.health_check()
            if health.get("alive"):
                _logger.info(
                    "Standing Codex alive: model=%s pid=%s sessions=%d roots=%s",
                    health.get("model"),
                    health.get("pid"),
                    health.get("sessions", 0),
                    health.get("roots"),
                )
            else:
                _logger.warning("Standing Codex not alive after startup: %s", health)
            return

        from llm_brain.v1.standing_brain import get_standing_brain_manager
        manager = get_standing_brain_manager()
        await manager.start()
        health = await manager.health_check()
        if health.get("alive"):
            _logger.info("Standing Brain alive: model=%s pid=%s turns=%d",
                          health["model"], health.get("pid"), health.get("turns", 0))
        else:
            _logger.warning("Standing Brain not alive after startup: %s", health)
    except Exception as exc:
        _logger.error("Standing Brain startup failed: %s", exc)


async def _embedding_keepalive_loop():
    """Periodically touch both embedding singletons so they stay hot.

    Python doesn't evict module-level globals, so strictly speaking the
    models never leave RAM once loaded. But GPUs can throttle/clock-down
    after long idle, and occasionally a competing CUDA process can evict
    weights. This loop sends a microscopic encode every few minutes to
    keep the model pinned on the device and serves as a liveness check —
    if either singleton silently goes missing, the warning will surface.
    """
    from intent_classifier.v2.classifier import stage1_classify
    from memory.v1.memory_retrieval import _embed_query_text
    interval_s = int(os.environ.get("JANE_EMBED_KEEPALIVE_SEC", "300"))  # 5 min
    # First tick happens after the interval — startup warmup already
    # touched both singletons once.
    while True:
        await asyncio.sleep(interval_s)
        try:
            await stage1_classify(".")
        except Exception as e:
            _logger.warning("embedding keepalive: stage1 failed: %s", e)
        try:
            await asyncio.to_thread(_embed_query_text, ".")
        except Exception as e:
            _logger.warning("embedding keepalive: memory_retrieval failed: %s", e)


async def _prewarm_stage1_classifier():
    """Warm Jane v2's Stage 1 ChromaDB embedding classifier at startup.

    The classifier's SentenceTransformer (BAAI/bge-small-en-v1.5) is
    loaded lazily on the first stage1_classify() call — which can take
    60–90 seconds including HuggingFace metadata checks. When the first
    real user request pays that cost, Android's streaming socket often
    times out. Warming here shifts the load to server startup so every
    user request hits a warm classifier.

    Also warms memory_retrieval._query_embedding_fn, which is a separate
    singleton using the same model — needed so the first memory lookup
    (librarian retrieval, Jane CLI memory hits) doesn't pay a second
    load. Both singletons live in the jane_web process for its lifetime;
    nothing evicts them until the process restarts.
    """
    import time as _time
    try:
        from intent_classifier.v2.classifier import stage1_classify
        _t = _time.perf_counter()
        _logger.info("Pre-warming Stage 1 embedding classifier…")
        await stage1_classify("warmup probe")
        _logger.info("Stage 1 classifier pre-warmed (%.1fs)",
                     _time.perf_counter() - _t)
    except Exception as e:
        _logger.warning("Stage 1 prewarm failed: %s", e)

    # Memory retrieval uses its own SentenceTransformer singleton — warm
    # it too so the first librarian query / Jane CLI memory call doesn't
    # pay an additional load cost (mostly fast now that CUDA is hot, but
    # still a few seconds on a fresh process).
    try:
        from memory.v1.memory_retrieval import _embed_query_text
        _t = _time.perf_counter()
        _logger.info("Pre-warming memory_retrieval embedding fn…")
        await asyncio.to_thread(_embed_query_text, "warmup probe")
        _logger.info("memory_retrieval embedding fn warm (%.1fs)",
                     _time.perf_counter() - _t)
    except Exception as e:
        _logger.warning("memory_retrieval prewarm failed: %s", e)


async def _prewarm_local_llm():
    """Pre-warm Jane's local LLM (qwen2.5:7b) via Ollama with keep_alive=-1.

    Pins the model in Ollama's memory at server startup so the very
    first user request doesn't pay a ~60-second cold-load. Tag comes
    from `jane_web.jane_v2.models.LOCAL_LLM`.

    Also kicks off the Stage 1 classifier warmup in parallel — Stage 1
    has its own separate cold-start penalty (sentence-transformers +
    Chroma) that we need to eat up front.
    """
    # Warm Stage 1 classifier in parallel — independent CPU/GPU work.
    asyncio.create_task(_prewarm_stage1_classifier())

    # v3 pipeline: classifier calls qwen2.5:7b via Ollama, which is
    # already prewarmed as part of the local-LLM prewarm block below.
    # No separate v3 warmup needed.
    try:
        from jane_web.jane_v2.models import LOCAL_LLM as model, OLLAMA_KEEP_ALIVE
    except Exception:
        # Fallback if the models module can't be imported for some reason.
        from jane_web.jane_v2.models import STAGE2_MODEL
        model = STAGE2_MODEL
        OLLAMA_KEEP_ALIVE = -1
    if ":" not in model:
        return
    _logger.info("Pre-warming local LLM: %s", model)
    try:
        import aiohttp
        # Prewarm MUST use the same num_ctx as every live caller, otherwise
        # the first real request triggers a runner reload (same bug we're
        # trying to prevent).
        try:
            from jane_web.jane_v2.models import LOCAL_LLM_NUM_CTX as _NUM_CTX
        except Exception:
            _NUM_CTX = int(os.environ.get("JANE_LOCAL_LLM_NUM_CTX", "8192"))
        endpoint = _ollama_generate_endpoint(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.post(
                endpoint,
                json=_local_llm_prewarm_payload(model, _NUM_CTX, OLLAMA_KEEP_ALIVE),
            ) as resp:
                await resp.read()
        _logger.info("Local LLM %s pre-warmed (keep_alive=%s)", model, OLLAMA_KEEP_ALIVE)
    except Exception as e:
        _logger.warning("Local LLM prewarm failed: %s", e)


async def _ollama_heartbeat_loop():
    """Keep the local LLM hot by firing a tiny inference every N seconds.

    `keep_alive=-1` pins the model weights in Ollama's VRAM but does NOT
    prevent GPU power-state transitions (P0 → P2) or Ollama's runner
    pipeline from going cold. Evidence (2026-04-18): idle calls after
    >30 s take 5–20 s of unexplained latency, back-to-back calls run
    in ~1 s. A periodic 1-token request keeps the GPU context and the
    Ollama runner pipeline in the hot path so every real user turn
    sees warm-path latency.

    Interval is deliberately short (≤20 s) — our idle-cold threshold
    starts biting around 30 s. Power cost of the extra inference is
    ~0.01 Wh per ping, << $1/mo.
    """
    interval_s = int(os.environ.get("JANE_OLLAMA_HEARTBEAT_S", "15"))
    if interval_s <= 0:
        _logger.info("Ollama heartbeat disabled (JANE_OLLAMA_HEARTBEAT_S=%s)", interval_s)
        return
    try:
        from jane_web.jane_v2.models import (
            LOCAL_LLM as model,
            LOCAL_LLM_NUM_CTX as num_ctx,
            OLLAMA_KEEP_ALIVE as keep_alive,
            record_ollama_activity,
            seconds_since_last_ollama_activity,
        )
    except Exception as e:
        _logger.warning("heartbeat: cannot import models.py (%s) — aborting", e)
        return

    endpoint = _ollama_generate_endpoint(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))

    _logger.info(
        "Ollama heartbeat started: model=%s interval=%ds endpoint=%s",
        model, interval_s, endpoint,
    )

    import aiohttp
    consecutive_failures = 0
    # Check more often than we ping so we catch idle windows promptly
    # without over-pinging when real traffic is flowing.
    poll_s = _heartbeat_poll_seconds(interval_s)
    while True:
        await asyncio.sleep(poll_s)
        # Skip if real traffic already kept the runner warm — every
        # production Ollama caller records activity via
        # `record_ollama_activity()` in models.py, so heartbeat only
        # fires during true idle.
        try:
            if _should_skip_heartbeat(seconds_since_last_ollama_activity(), interval_s):
                continue
        except Exception:
            pass
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(
                    endpoint,
                    # Tiny prompt; single-token reply is enough to keep the
                    # inference pipeline resident.
                    json=_ollama_heartbeat_payload(model, num_ctx, keep_alive),
                ) as resp:
                    await resp.read()
            record_ollama_activity()
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            # Log only every 10 consecutive failures to avoid spam. One-off
            # blips happen when jane-web is in the middle of its own
            # restart or when Ollama is transiently busy.
            if consecutive_failures % 10 == 1:
                _logger.warning(
                    "heartbeat ping failed (%d in a row): %s",
                    consecutive_failures, e,
                )


async def _reap_stale_sessions_loop():
    """Periodically reap stale Claude and Gemini persistent sessions to prevent memory leaks."""
    while True:
        await asyncio.sleep(600)  # every 10 minutes
        try:
            from llm_brain.v1.persistent_claude import get_claude_persistent_manager
            manager = get_claude_persistent_manager()
            reaped = await manager.reap_stale_sessions()
            if reaped:
                _logger.info("Reaped %d stale Claude sessions", reaped)
        except Exception as e:
            _logger.warning("Claude session reaper error (non-fatal): %s", e)
        # Also reap stale Gemini persistent sessions
        try:
            from llm_brain.v1.persistent_gemini import get_gemini_persistent_manager
            gm = get_gemini_persistent_manager(os.environ.get("VESSENCE_HOME", ""))
            gemini_reaped = await gm.reap_stale_sessions()
            if gemini_reaped:
                _logger.info("Reaped %d stale Gemini sessions", gemini_reaped)
        except Exception as e:
            _logger.warning("Gemini session reaper error (non-fatal): %s", e)
        # Also prune in-memory Jane proxy sessions
        try:
            from jane_web.jane_proxy import _prune_stale_sessions
            _prune_stale_sessions()
        except Exception as e:
            _logger.warning("Jane proxy session pruner error (non-fatal): %s", e)


async def shutdown():
    """Clean up persistent workers to prevent zombie processes on restart.

    Uses force_shutdown_all() for Claude sessions to avoid deadlocking on
    the session lock (which may be held by an in-progress turn). Uses killpg()
    to kill entire process trees (Bun workers, tokio runtimes, etc.) instead
    of just the parent process.
    """
    _logger.info("Jane Web shutting down — cleaning up persistent workers...")

    # Claude: force-kill all subprocesses without acquiring locks
    try:
        from llm_brain.v1.persistent_claude import get_claude_persistent_manager
        killed = get_claude_persistent_manager().force_shutdown_all()
        _logger.info("Claude cleanup: killed %d processes", killed)
    except Exception as e:
        _logger.warning(f"Claude cleanup error (non-fatal): {e}")

    # Gemini: shutdown PTY sessions
    try:
        from llm_brain.v1.persistent_gemini import get_gemini_persistent_manager
        manager = get_gemini_persistent_manager(os.environ.get("VESSENCE_HOME", ""))
        for sid in list(getattr(manager, '_sessions', {}).keys()):
            try:
                await manager.end(sid)
            except Exception:
                pass
    except Exception as e:
        _logger.warning(f"Gemini cleanup error (non-fatal): {e}")

    # Standing Brain: kill all tiers in parallel
    try:
        from llm_brain.v1.standing_brain import get_standing_brain_manager
        await get_standing_brain_manager().shutdown()
    except Exception as e:
        _logger.warning(f"Standing Brain cleanup error (non-fatal): {e}")

    # Standing Codex app-server
    try:
        from llm_brain.v1.standing_codex import get_codex_app_server_manager
        await get_codex_app_server_manager().shutdown()
    except Exception as e:
        _logger.warning(f"Standing Codex cleanup error (non-fatal): {e}")

    # Cancel background tasks (session reaper, etc.)
    for task in list(_background_tasks):
        task.cancel()
    _logger.info("Jane Web shutdown complete.")


def _auto_load_essences():
    """Scan ESSENCES_DIR and auto-load all valid essences on startup."""
    from agent_skills.essence_runtime import EssenceRuntime, CapabilityRegistry
    global _capability_registry
    _capability_registry = CapabilityRegistry()

    runtime = _get_essence_runtime()
    available = list_available_essences()
    loaded_names = []
    for e in available:
        try:
            state = load_essence(e["path"])
            _essence_states[e["name"]] = state
            # Also load into the runtime for orchestration
            try:
                runtime.load_essence(e["name"])
            except Exception:
                pass  # runtime may fail on chromadb import; non-fatal
            # Register capabilities
            caps = state.capabilities.get("provides", [])
            if caps:
                _capability_registry.register(e["name"], caps)
            loaded_names.append(e["name"])
            _logger.info("Auto-loaded essence '%s' (%s) — capabilities: %s",
                         e["name"], state.role_title, caps)
        except Exception as exc:
            _logger.warning("Failed to auto-load essence '%s': %s", e["name"], exc)
    _logger.info("Auto-loaded %d essences: %s", len(loaded_names), loaded_names)


def _get_essence_runtime():
    """Get or create the singleton EssenceRuntime."""
    try:
        from agent_skills.essence_runtime import EssenceRuntime
        return EssenceRuntime(TOOLS_DIR)
    except Exception as exc:
        _logger.warning("Could not initialize EssenceRuntime: %s", exc)
        return None


@app.get("/health")
async def health():
    brain = normalize_frontier_provider(os.getenv("JANE_BRAIN", "gemini"))
    return {"status": "ok", "service": "jane", "brain": brain}


@app.get("/healthz")
async def healthz():
    """Richer health endpoint for Android client retry-probe.

    Returns the brain warm/cold status so the client can decide whether
    retrying a TransientServerError is worth the round-trip. Replies fast
    (no LLM calls) so it's safe to poll during rolling restarts.
    """
    brain = normalize_frontier_provider(os.getenv("JANE_BRAIN", "gemini"))
    warm = "unknown"
    model = ""
    try:
        from llm_brain.v1.standing_brain import get_standing_brain_manager
        mgr = get_standing_brain_manager()
        h = await mgr.health_check()
        warm = h.get("status", "unknown")
        model = h.get("model", "")
    except Exception:
        pass
    return {
        "status": "ok",
        "brain": brain,
        "brain_status": warm,      # "warm" | "cold" | "unknown"
        "brain_model": model,
    }


@app.post("/api/admin/reset-gate")
async def reset_session_gate(request: Request):
    """Force-release a stuck request_gate for a session. Localhost only.

    Used when a mid-stream disconnect left the gate locked, blocking all
    subsequent requests with 'Jane is busy'. Avoids needing a full restart.

    Body: {"session_id": "jane_android"}
    """
    client_ip = _client_ip(request)
    if not _is_local_control_ip(client_ip):
        return JSONResponse({"error": "localhost only"}, status_code=403)
    try:
        body = await request.json()
        session_id = body.get("session_id", "").strip()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not session_id:
        return JSONResponse({"error": "session_id required"}, status_code=400)

    from jane_web.jane_proxy import _sessions
    state = _sessions.get(session_id)
    if state is None:
        return JSONResponse({"status": "not_found", "session_id": session_id})

    gate = state.request_gate
    locked = gate._value == 0  # Semaphore(1): 0 = locked, 1 = free
    if locked:
        gate.release()
        _logger.warning("Admin reset gate for session=%s", session_id[:12])
        return JSONResponse({"status": "released", "session_id": session_id})
    return JSONResponse({"status": "already_free", "session_id": session_id})


@app.post("/api/admin/rotate-brain")
async def rotate_brain_session(request: Request):
    """Force-rotate the standing brain's Claude session to clear stale context.

    Discards the current persistent Claude CLI session so the next message
    starts a fresh one. Useful when context compression has accumulated
    stale/incorrect summaries (e.g. wrong handler status).

    Body: {"session_id": "jane_android"} or {} to rotate ALL sessions.
    Localhost only.
    """
    client_ip = _client_ip(request)
    if not _is_local_control_ip(client_ip):
        return JSONResponse({"error": "localhost only"}, status_code=403)
    try:
        body = await request.json()
        session_id = body.get("session_id", "").strip()
    except Exception:
        session_id = ""

    from llm_brain.v1.persistent_claude import get_claude_persistent_manager
    manager = get_claude_persistent_manager()

    if session_id:
        user_id = get_session_user(session_id) or _default_user_id()
        await manager.end(user_id, session_id)
        _logger.info("Admin rotated brain session: user=%s session=%s", user_id, session_id[:12])
        return JSONResponse({"status": "rotated", "session_id": session_id})

    killed = manager.force_shutdown_all()
    _logger.info("Admin rotated ALL brain sessions: killed=%d", killed)
    return JSONResponse({"status": "rotated_all", "killed": killed})


@app.post("/api/jane/warmup")
async def warmup_brain(request: Request):
    """Warm up the standing brain CLI process. Called by graceful_restart.sh
    before switching the proxy upstream. Read-only — no ChromaDB writes."""
    client_ip = _client_ip(request) if hasattr(request, 'headers') else ""
    if not _is_local_control_ip(client_ip, allow_unknown=True):
        return JSONResponse({"error": "localhost only"}, status_code=403)
    try:
        from llm_brain.v1.standing_brain import get_standing_brain_manager
        manager = get_standing_brain_manager()
        if not manager._started:
            manager.start()
        # Wait for the brain to be alive (up to 30s)
        for _ in range(30):
            if manager.brain and manager.brain.alive:
                break
            await asyncio.sleep(1)
        if manager.brain and manager.brain.alive:
            return JSONResponse({"status": "warm", "model": manager.brain.model})
        return JSONResponse({"status": "starting"}, status_code=202)
    except Exception as e:
        _logger.warning("Warmup failed: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.get("/sw.js")
async def service_worker():
    return FileResponse(str(STATIC_DIR / "chat-sw.js"), media_type="application/javascript")


@app.get("/manifest.webmanifest")
async def web_manifest():
    return FileResponse(str(STATIC_DIR / "jane.webmanifest"), media_type="application/manifest+json")


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def get_session_id(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE)


_trusted_device_session_cache: dict[str, str] = {}  # trusted_device_id → session_id

def require_auth(request: Request):
    session_id = _required_session_id_for_request(
        request,
        trusted_device_session_cache=_trusted_device_session_cache,
        get_session_id_fn=get_session_id,
        get_trusted_device_cookie_id_fn=get_trusted_device_cookie_id,
        device_fingerprint_fn=device_fingerprint_from_request,
        validate_session_fn=validate_session,
        get_trusted_device_by_id_fn=get_trusted_device_by_id,
        create_session_fn=create_session,
        default_user_id_fn=_default_user_id,
        is_single_user_no_auth_mode_fn=_is_single_user_no_auth_mode,
        is_local_request_fn=_is_local_request,
    )
    if session_id:
        return session_id
    raise HTTPException(status_code=401, detail="Not authenticated")


_ra_reports = RaReportAccess(
    html_reports_dir=RA_HTML_REPORTS_DIR,
    session_secret_provider=lambda: _session_secret or os.getenv("SESSION_SECRET_KEY", ""),
    client_ip=_client_ip,
    require_auth=require_auth,
)
_ra_report_html_path = _ra_reports.html_path
_latest_ra_report_html_path = _ra_reports.latest_html_path
report_id_from_ra_html_path = _ra_reports.report_id_from_html_path
_prune_ra_report_grants = _ra_reports.prune_grants
_grant_ra_report_access = _ra_reports.grant_access
_has_recent_ra_report_grant = _ra_reports.has_recent_grant
_sign_ra_report_token = _ra_reports.sign_token
_issue_ra_report_token = _ra_reports.issue_token
_valid_ra_report_token = _ra_reports.valid_token
_valid_ra_report_share_token = _ra_reports.valid_share_token
_require_ra_report_access = _ra_reports.require_access
_tokenize_ra_report_item = _ra_reports.tokenize_report_item
_ra_report_metadata = _ra_reports.metadata
_ra_report_share_path = _ra_reports.share_path
_ra_report_id_from_html_path = _ra_reports.report_id_from_html_path


def _is_user_admin(user_id: str | None) -> bool:
    return _resolve_is_user_admin(
        user_id,
        identity_variants_fn=_identity_variants,
        configured_admin_variants_fn=_configured_admin_variants,
        logger=_logger,
    )


def _require_admin_session(session_id: str) -> str:
    user_id = get_session_user(session_id) or _default_user_id()
    if not _is_user_admin(user_id):
        raise HTTPException(status_code=403, detail="User administration is not enabled for this account.")
    return user_id


def _scoped_conversation_session_id(user_id: str | None, session_id: str | None) -> str:
    return _resolve_scoped_conversation_session_id(user_id, session_id)


# ── Per-user vault + capability resolution ──────────────────────────────────
#
# Unmanaged accounts (Chieh's primary account, admin-only installs) keep the
# legacy behavior: global VAULT_DIR, all capabilities. Managed accounts created
# through /api/admin/users carry a private vault root plus an explicit
# capability list stored in config.json; every vault/tool endpoint must resolve
# the per-request vault root and deny tool access missing from the list.

def _user_vault_context(session_id: str | None) -> tuple[str, list[str], bool, str]:
    """Return (vault_root, capabilities, is_managed, user_id) for a session."""
    return _resolve_user_vault_context(
        session_id,
        vault_dir=VAULT_DIR,
        get_session_user_fn=get_session_user,
        default_user_id_fn=_default_user_id,
    )


def _require_capability(session_id: str | None, cap: str) -> tuple[str, list[str], bool, str]:
    """Ensure the session's user holds `cap`. Returns the vault context tuple.

    Unmanaged accounts are not gated — they have implicit full access.
    Managed accounts must list `cap` in their config.json capabilities.
    """
    return _resolve_require_capability(session_id, cap, context_resolver=_user_vault_context)


def _request_vault_root(request: Request) -> str:
    """Determine the vault root for a request.

    For an authenticated managed user, returns their private vault root.
    For host/unmanaged or share-code requests, returns the global VAULT_DIR.
    Never raises — suitable for handlers that have already auth-checked.
    """
    return _resolve_request_vault_root(
        request,
        vault_dir=VAULT_DIR,
        get_session_id_fn=get_session_id,
        context_resolver=_user_vault_context,
    )


def _user_memory_path(user_id: str | None) -> str:
    """Return the ChromaDB path a managed user should write facts into.

    Returns an empty string for unmanaged accounts so add_fact.py falls
    through to the global shared path (legacy behavior).
    """
    return _resolve_user_memory_path(user_id)


def resolve_conversation_key(request: Request, body) -> dict:
    """Produce the canonical conversation key for a chat request.

    Single source of truth per Job #77 Section 5.1. All chat entry points
    should call this helper and thread the returned `conversation_key`
    through any downstream state lookup (ConversationManager, FIFO, pending
    action resolver, standing brain manager, etc).

    Shape of the canonical key:
        <sanitized_user_id>__<device_id>__<client_session_id>

    Unmanaged (Chieh) accounts preserve their legacy `body.session_id`
    verbatim to avoid breaking in-flight conversations.
    """
    return _resolve_conversation_key_payload(
        request,
        body,
        get_session_id_fn=get_session_id,
        get_session_user_fn=get_session_user,
        default_user_id_fn=_default_user_id,
        get_trusted_device_cookie_id_fn=get_trusted_device_cookie_id,
        device_fingerprint_fn=device_fingerprint_from_request,
    )


def get_trusted_device_cookie_id(request: Request) -> Optional[str]:
    return request.cookies.get(TRUSTED_DEVICE_COOKIE)


def _attach_auth_cookies(
    response: Response,
    request: Request,
    session_id: Optional[str],
    trusted_device_id: Optional[str],
) -> Response:
    for spec in auth_cookie_specs(
        existing_session_id=get_session_id(request),
        session_id=session_id,
        existing_trusted_device_id=get_trusted_device_cookie_id(request),
        trusted_device_id=trusted_device_id,
        session_cookie_name=SESSION_COOKIE,
        trusted_device_cookie_name=TRUSTED_DEVICE_COOKIE,
    ):
        apply_auth_cookie_spec(response, spec, secure=_cookie_secure_flag(request))
    return response


def get_or_bootstrap_session(request: Request) -> tuple[Optional[str], Optional[str]]:
    return _bootstrap_session_for_request(
        request,
        get_session_id_fn=get_session_id,
        get_trusted_device_cookie_id_fn=get_trusted_device_cookie_id,
        device_fingerprint_fn=device_fingerprint_from_request,
        validate_session_fn=validate_session,
        create_session_fn=create_session,
        get_session_user_fn=get_session_user,
        default_user_id_fn=_default_user_id,
        get_trusted_device_by_id_fn=get_trusted_device_by_id,
        get_trusted_device_by_fingerprint_fn=get_trusted_device_by_fingerprint,
        is_single_user_no_auth_mode_fn=_is_single_user_no_auth_mode,
        is_local_request_fn=_is_local_request,
        is_local_browser_access_fn=_is_local_browser_access,
        client_ip_fn=_client_ip,
        session_log_id_fn=_session_log_id,
        prewarm_session_fn=prewarm_session,
        logger=_logger,
    )


def check_share_or_auth(request: Request, path: str):
    if _request_has_share_or_auth(
        request,
        path,
        get_session_id_fn=get_session_id,
        get_trusted_device_cookie_id_fn=get_trusted_device_cookie_id,
        device_fingerprint_fn=device_fingerprint_from_request,
        validate_session_fn=validate_session,
        get_trusted_device_by_id_fn=get_trusted_device_by_id,
        validate_share_fn=validate_share,
        is_single_user_no_auth_mode_fn=_is_single_user_no_auth_mode,
        is_local_request_fn=_is_local_request,
    ):
        return True
    raise HTTPException(status_code=401, detail="Not authenticated")


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    
    # Check if vault is locked
    store = SecretStore()
    if not store.is_unlocked():
        return RedirectResponse(url="/challenge")

    if session_id:
        try:
            from .jane_proxy import get_active_brain
        except ImportError:
            from jane_proxy import get_active_brain
        response = templates.TemplateResponse(
            "jane.html",
            {
                "request": request,
                "brain_label": get_active_brain(),
                "initial_session_id": session_id,
            },
        )
        _attach_auth_cookies(response, request, session_id, trusted_device_id)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/share", response_class=HTMLResponse)
async def share_page(request: Request):
    return templates.TemplateResponse("login.html", _login_context(request, share_mode=True))


@app.get("/vault", response_class=HTMLResponse)
async def vault_page(request: Request):
    """Serve the vault file browser (previously at vault_web port 8080)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        response = templates.TemplateResponse(
            "app.html",
            {
                "request": request,
                "initial_tab": "vault",
                "android_webview": is_android_webview_request(request),
            },
        )
        _attach_auth_cookies(response, request, session_id, trusted_device_id)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """Serve the Jane User Guide page."""
    return templates.TemplateResponse("guide.html", {"request": request})


@app.get("/architecture", response_class=HTMLResponse)
async def architecture_page(request: Request):
    """Serve the Jane Architecture deep-dive page."""
    return templates.TemplateResponse("architecture.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the Amber chat tab (previously at vault_web)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if session_id:
        response = templates.TemplateResponse(
            "app.html",
            {
                "request": request,
                "initial_tab": "chat",
                "android_webview": is_android_webview_request(request),
            },
        )
        _attach_auth_cookies(response, request, session_id, trusted_device_id)
        return response
    return templates.TemplateResponse("login.html", _login_context(request))


@app.get("/essences", response_class=HTMLResponse)
async def essences_page(request: Request, _=Depends(require_auth)):
    return FileResponse(str(STATIC_DIR / "essences.html"), media_type="text/html")

@app.get("/worklog", response_class=HTMLResponse)
async def worklog_page(request: Request, _=Depends(require_auth)):
    return FileResponse(str(STATIC_DIR / "worklog.html"), media_type="text/html")

@app.get("/api/job-queue")
async def get_job_queue(_=Depends(require_auth)):
    """Return job queue as structured JSON for client-side rendering."""
    try:
        from agent_skills.show_job_queue import get_job_queue_data
        return get_job_queue_data()
    except Exception:
        return {"columns": [], "jobs": [], "count": 0}


@app.get("/api/job-queue/completed")
async def get_completed_jobs(_=Depends(require_auth)):
    """Return completed jobs as structured JSON for client-side rendering."""
    try:
        from agent_skills.show_job_queue import get_completed_jobs_data
        return get_completed_jobs_data()
    except Exception:
        return {"columns": [], "jobs": [], "count": 0}


@app.get("/briefing", response_class=HTMLResponse)
async def briefing_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse("briefing.html", {"request": request})


@app.post("/api/crash-report")
async def receive_crash_report(request: Request):
    """Receive Android crash reports.

    This intentionally accepts unauthenticated writes like device diagnostics:
    crash uploads often happen during app startup before the normal authenticated
    client stack has restored cookies/trusted-device state.
    """
    body = (await request.body())[:10000]
    report = body.decode("utf-8", errors="replace")
    crash_file = Path(LOGS_DIR) / "android_crashes.log"
    with open(crash_file, "a") as f:
        f.write(f"\n{'='*60}\n{report}\n")
    _logger.error("Android crash report received:\n%s", report[:500])
    _dispatch_self_healing_report(
        source="android_crash_report",
        category="android_crash",
        message=report[:500],
        payload={"report": report},
        request=request,
        project_root=str(CODE_ROOT),
        tags=["android", "crash"],
    )
    return {"status": "received"}


def _self_healing_report_authorized(request: Request) -> bool:
    """Authorize external project error reports that can trigger repair work."""
    return self_healing_report_authorized(
        request,
        expected_token=os.environ.get("JANE_SELF_HEAL_TOKEN", ""),
        is_local_request_fn=_is_local_request,
    )


@app.post("/api/self-healing/report")
async def receive_self_healing_report(request: Request):
    """Receive structured error reports from sibling apps such as chieh_class_v2."""
    if not _self_healing_report_authorized(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "expected object"}, status_code=400)

    report = normalize_self_healing_report(body, default_project_root=str(CODE_ROOT))
    _dispatch_self_healing_report(
        source=report["source"],
        category=report["category"],
        message=report["message"],
        payload=report["payload"],
        request=request,
        project_root=report["project_root"],
        tags=report["tags"],
    )
    return {"status": "received"}


# ── Contacts sync ─────────────────────────────────────────────────────────────

@app.post("/api/contacts/sync")
async def sync_contacts(request: Request, session_id: str = Depends(require_auth)):
    """Full-replace sync: delete all existing contacts and insert fresh from Android."""
    _require_capability(session_id, "phone")
    try:
        contacts = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(contacts, list):
        raise HTTPException(status_code=400, detail="Expected a JSON array")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        # Full replace — delete all existing, insert fresh
        conn.execute("DELETE FROM contacts")
        for c in contacts:
            values = contact_insert_values(c, now)
            if values is None:
                continue
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO contacts
                       (display_name, phone_number, email, is_primary, contact_id, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    values,
                )
            except Exception as e:
                _logger.warning("contacts sync row error: %s", e)

    _logger.info("Contacts sync: %d contacts received (full replace)", len(contacts))
    return {"status": "ok", "received": len(contacts)}


@app.get("/api/contacts/search")
async def search_contacts(q: str = "", session_id: str = Depends(require_auth)):
    """Search contacts by name, return aggregated per person (phones + emails merged)."""
    _require_capability(session_id, "phone")
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    query = f"%{q.strip()}%"
    with get_db() as conn:
        rows = conn.execute(
            "SELECT display_name, phone_number, email, is_primary, contact_id FROM contacts WHERE display_name LIKE ? ORDER BY display_name, is_primary DESC LIMIT 100",
            (query,),
        ).fetchall()
    return aggregate_contact_rows(rows)


@app.get("/api/contacts")
async def list_contacts(request: Request, session_id: str = Depends(require_auth)):
    """List all synced contacts."""
    _require_capability(session_id, "phone")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT display_name, phone_number, email, is_primary, contact_id, synced_at FROM contacts ORDER BY display_name"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/contacts/alias")
async def add_contact_alias(request: Request, session_id: str = Depends(require_auth)):
    _require_capability(session_id, "phone")
    """Write a relational alias → phone number mapping.

    Used by Opus when it resolves an unknown relational name (e.g. "my wife")
    via memory so that future SEND_MESSAGE fast-path requests resolve without
    an Opus round-trip.

    Body: {"alias": "wife", "phone_number": "+15551234567", "display_name": "Kathia"}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    values = contact_alias_values(body)
    if values is None:
        raise HTTPException(status_code=400, detail="alias and phone_number are required")
    alias, phone, display_name = values
    from agent_skills.sms_helpers import add_alias
    ok = add_alias(alias=alias, phone_number=phone, display_name=display_name)
    return {"ok": ok}


# ── SMS message sync ──────────────────────────────────────────────────────────

@app.post("/api/messages/sync")
async def sync_messages(request: Request, session_id: str = Depends(require_auth)):
    _require_capability(session_id, "phone")
    """Full-replace sync for recent SMS messages from Android.

    Accepts a JSON array of message objects with keys:
      sender (str), body (str), timestamp_ms (int), is_read (bool)

    Deletes messages older than 7 days, then upserts incoming messages
    using the UNIQUE(sender, timestamp_ms, body) constraint.
    """
    try:
        messages = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="Expected a JSON array")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    attempted = 0
    inserted = 0
    with get_db() as conn:
        # Prune messages older than 14 days
        fourteen_days_ago_ms = int((time.time() - 14 * 86400) * 1000)
        conn.execute("DELETE FROM synced_messages WHERE timestamp_ms < ?", (fourteen_days_ago_ms,))

        for m in messages:
            values = message_insert_values(
                m,
                now,
                classify_message=lambda body, is_contact: classify_synced_message(
                    body,
                    is_contact=is_contact,
                ),
            )
            if values is None:
                continue

            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO synced_messages
                       (sender, body, timestamp_ms, is_read, is_contact, msg_type, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
                attempted += 1
                # cursor.rowcount is 1 when the row was newly inserted, 0 when
                # the UNIQUE(sender, timestamp_ms, body) constraint silently
                # de-duped (INSERT OR IGNORE no-op).
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                _logger.warning("messages sync row error: %s", e)

    _logger.info(
        "Messages sync: %d new / %d attempted / %d received",
        inserted, attempted, len(messages),
    )
    return {
        "status": "ok",
        "received": len(messages),
        "attempted": attempted,
        "inserted": inserted,
    }


@app.get("/api/messages/search")
async def search_messages(q: str = "", days: int = 5, _=Depends(require_auth)):
    """Search synced SMS messages by sender name or body text.

    Query params:
      q    — search term (matches sender or body, case-insensitive)
      days — how far back to look (default 5)
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    since_ms = int((time.time() - days * 86400) * 1000)
    query = f"%{q.strip()}%"
    with get_db() as conn:
        rows = conn.execute(
            """SELECT sender, body, timestamp_ms, is_read, synced_at
               FROM synced_messages
               WHERE timestamp_ms > ? AND (sender LIKE ? OR body LIKE ?)
               ORDER BY timestamp_ms DESC LIMIT 100""",
            (since_ms, query, query),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/messages/recent")
async def recent_messages(days: int = 5, limit: int = 50, _=Depends(require_auth)):
    """Return all recent synced messages (no search filter)."""
    since_ms = int((time.time() - days * 86400) * 1000)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT sender, body, timestamp_ms, is_read, synced_at
               FROM synced_messages
               WHERE timestamp_ms > ?
               ORDER BY timestamp_ms DESC LIMIT ?""",
            (since_ms, min(limit, 200)),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/device-diagnostics")
async def receive_device_diagnostics(request: Request):
    """Receive diagnostic data from Android: wake word status, mic state, errors, scores, etc.

    This endpoint intentionally accepts unauthenticated writes because the
    most important diagnostics happen before login has succeeded.
    Reading diagnostics remains authenticated.

    When a `chat_error` category lands, automatically file an audit job
    into configs/job_queue/ so the next `run job queue:` reviews the
    code path that crashed (agent_skills/chat_error_audit.py).
    """
    body = await request.json()
    _device_diagnostics_log.append(body)
    category = body.get("category", "unknown")
    message = body.get("message", "")
    _logger.info("Android diagnostic [%s]: %s", category, message[:200])

    # chat_error/error → self-healing incident + optional autonomous repair.
    if category in {"chat_error", "error"}:
        _dispatch_self_healing_report(
            source=f"android_{category}",
            category=category,
            message=message,
            payload=body,
            request=request,
            project_root=str(CODE_ROOT),
            tags=["android", category],
        )

    return {"status": "received"}


@app.get("/api/device-diagnostics")
async def get_device_diagnostics(request: Request, _=Depends(require_auth), lines: int = 50):
    """Read recent diagnostics (most recent first)."""
    return {"diagnostics": _device_diagnostics_log.read_recent(lines)}


@app.get("/settings/devices", response_class=HTMLResponse)
async def devices_page(request: Request, _=Depends(require_auth)):
    return templates.TemplateResponse("app.html", {"request": request, "initial_tab": "settings",
                                                    "android_webview": is_android_webview_request(request)})


@app.get("/downloads/{filename}")
async def download_release_artifact(filename: str):
    """Serve public release downloads (APK, docker packages, etc.)."""
    target = _release_downloads.resolve_download(filename)
    if not target or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        str(target),
        media_type=_release_downloads.media_type(target),
        filename=filename,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ─── App Update API ───────────────────────────────────────────────────────────

# ─── App Settings API (synced between server and Android) ────────────────────

_APP_SETTINGS_PATH = os.path.join(VESSENCE_DATA_HOME, "data", "app_settings.json")
_app_settings_store = JsonSettingsStore(_APP_SETTINGS_PATH)
_load_app_settings = _app_settings_store.load
_save_app_settings = _app_settings_store.save


# ─── Chat TTS API — XTTS-v2 audio for Jane's chat responses ─────────────────

_split_tts_chunks = split_tts_chunks


# ─── XTTS-v2 TTS proxy — forwards to standalone tts_server on port 8095 ───────
# These proxy endpoints let Android reach the TTS server through the existing
# Cloudflare tunnel (jane.vessences.com) instead of requiring local network access.
import httpx

_tts_proxy_client = httpx.AsyncClient(base_url="http://127.0.0.1:8095", timeout=60.0)

@app.get("/api/tts-server/health")
async def tts_proxy_health(_=Depends(require_auth)):
    resp = await _tts_proxy_client.get("/tts/health")
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"))

@app.post("/api/tts-server/generate")
async def tts_proxy_generate(request: Request, _=Depends(require_auth)):
    body = await request.body()
    resp = await _tts_proxy_client.post("/tts/generate", content=body,
                                        headers={"Content-Type": "application/json"})
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "audio/wav"))

@app.post("/api/tts-server/stream")
async def tts_proxy_stream(request: Request, _=Depends(require_auth)):
    body = await request.body()
    resp = await _tts_proxy_client.post("/tts/stream", content=body,
                                        headers={"Content-Type": "application/json"})
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/octet-stream"))


# Limit TTS to 1 concurrent Docker container to prevent RAM/CPU exhaustion
_tts_semaphore = asyncio.Semaphore(1)

@app.post("/api/tts/generate")
async def generate_tts(request: Request, _=Depends(require_auth)):
    """Generate XTTS-v2 audio for text. Chunks by sentence, compresses to Opus/OGG.
    Body: {"text": "...", "speaker": "Barbora MacLean"}
    """
    body = await request.json()
    text = body.get("text", "").strip()
    speaker = body.get("speaker", "Barbora MacLean")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    import tempfile, shutil
    cache_paths = tts_cache_paths(VESSENCE_DATA_HOME, text)
    os.makedirs(cache_paths.cache_dir, exist_ok=True)

    # Check cache (both ogg and legacy wav)
    cached_media = tts_cached_media(cache_paths)
    if cached_media:
        cached_path, media_type = cached_media
        return FileResponse(cached_path, media_type=media_type)

    gpu_flag = tts_gpu_flags()
    chunks = _split_tts_chunks(text[:1000])
    tmp_dir = tempfile.mkdtemp(prefix="tts_web_")

    try:
        chunk_wavs = []
        for i, chunk in enumerate(chunks):
            chunk_wav = tts_chunk_wav_path(tmp_dir, i)
            cmd = tts_docker_command(
                tmp_dir=tmp_dir,
                chunk=chunk,
                speaker=speaker,
                index=i,
                gpu_flags=gpu_flag,
            )
            async with _tts_semaphore:
                result = await asyncio.to_thread(
                    subprocess.run, cmd,
                    capture_output=True, text=True, timeout=120,
                )
            if result.returncode == 0 and os.path.exists(chunk_wav):
                chunk_wavs.append(chunk_wav)

        if not chunk_wavs:
            raise HTTPException(status_code=500, detail="TTS generation failed")

        # Concatenate WAV chunks
        combined_wav = tts_combined_wav_path(tmp_dir)
        _concatenate_wav_chunks(chunk_wavs, combined_wav)

        # Compress to Opus/OGG
        compress_result = await asyncio.to_thread(
            subprocess.run,
            tts_ffmpeg_command(combined_wav, cache_paths.ogg_path),
            capture_output=True, text=True, timeout=60,
        )
        if compress_result.returncode == 0 and os.path.exists(cache_paths.ogg_path):
            return FileResponse(cache_paths.ogg_path, media_type="audio/ogg")

        # Fall back to serving uncompressed WAV if ffmpeg fails
        shutil.copy2(combined_wav, cache_paths.legacy_wav_path)
        return FileResponse(cache_paths.legacy_wav_path, media_type="audio/wav")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TTS generation timed out")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/app/settings")
async def get_app_settings(_=Depends(require_auth)):
    """Get synced app settings. Android polls this on startup."""
    return JSONResponse(_load_app_settings())


@app.put("/api/app/settings")
async def update_app_settings(request: Request, _=Depends(require_auth)):
    """Update app settings. Jane can call this to change user preferences remotely."""
    body = await request.json()
    current = _load_app_settings()
    current.update(body)
    _save_app_settings(current)
    return JSONResponse({"ok": True, "settings": current})


@app.post("/api/app/installed")
async def report_app_installed(request: Request, _=Depends(require_auth)):
    """Called by the Android app after installing a new version. Logs to work log."""
    try:
        body = await request.json()
        version = body.get("version_name", "unknown")
        _log_work_activity(f"Android app updated to v{version}", category="release")
    except Exception:
        pass
    return JSONResponse({"ok": True})


@app.get("/api/app/latest-version")
async def latest_app_version(response: Response):
    # Allow marketing site (vessences.com) to fetch this cross-origin
    response.headers["Access-Control-Allow-Origin"] = "*"
    # Read version.json fresh each time so builds are picked up without server restart.
    return _release_downloads.latest_version_payload()


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.get("/auth/google")
async def login_google(request: Request):
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this deployment.")
    redirect_uri = build_external_url(
        request,
        str(request.app.url_path_for("auth_google_callback")),
        "JANE_PUBLIC_BASE_URL",
    )
    return await oauth.google.authorize_redirect(
        request, redirect_uri, access_type="offline", prompt="consent",
    )


@app.get("/challenge", response_class=HTMLResponse)
async def challenge_page(request: Request):
    store = SecretStore()
    if store.is_unlocked():
        return RedirectResponse(url="/")
    
    question = store.get_challenge_question()
    is_init = question is None
    
    return templates.TemplateResponse(
        "challenge.html",
        {
            "request": request,
            "question": question or "Set up your security challenge",
            "is_init": is_init,
            "app_title": os.getenv("APP_TITLE", "Vessences"),
            "app_subtitle": os.getenv("APP_SUBTITLE", "Your personal AI companion"),
        }
    )

@app.post("/api/auth/challenge")
async def verify_challenge(request: Request):
    body = await request.json()
    answer = body.get("answer", "").strip()
    
    store = SecretStore()
    if not os.path.exists(VAULT_ENC_PATH):
        # First-time setup
        question = body.get("question", "").strip()
        if not answer or not question:
            return JSONResponse({"ok": False, "error": "Passphrase and question required for setup."})
        store.initialize(answer, question)
        return JSONResponse({"ok": True})
    
    # Existing vault
    if store.unlock(answer):
        return JSONResponse({"ok": True})
    else:
        return JSONResponse({"ok": False, "error": "Incorrect answer."})


@app.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request):
    if not google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this deployment.")
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="OAuth error")
    user_info = token.get("userinfo", {})
    email = user_info.get("email", "")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    trusted_device_id = trusted_device_id_for_fingerprint(
        fp,
        email,
        register_trusted_device=register_trusted_device,
        get_trusted_device_by_fingerprint=get_trusted_device_by_fingerprint,
        is_device_trusted=is_device_trusted,
    )
    # Store Gmail OAuth token for email skill
    try:
        from agent_skills.email_oauth import store_gmail_token
        gmail_token_data = {
            "access_token": token.get("access_token", ""),
            "refresh_token": token.get("refresh_token", ""),
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at", 0),
            "scope": token.get("scope", ""),
        }
        if gmail_token_data["access_token"]:
            store_gmail_token(email, gmail_token_data)
            _logger.info("Gmail token stored for %s during OAuth callback", email)
    except Exception as exc:
        _logger.warning("Failed to store Gmail token: %s", exc)

    session_id = create_session(fp, trusted=True, user_id=email)
    prewarm_session(session_id, email)
    resp = RedirectResponse(url="/")
    _attach_auth_cookies(resp, request, session_id, trusted_device_id)
    return resp


@app.post("/api/auth/google-token")
async def auth_google_token(request: Request):
    """Accept a Google ID token from native Android apps and create a session."""
    body = await request.json()
    id_token_str = body.get("id_token", "")
    if not id_token_str:
        raise HTTPException(status_code=400, detail="id_token is required")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), client_id
        )
        email = idinfo.get("email", "")
    except Exception as exc:
        _logger.error("Google ID token verification failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid Google ID token: {exc}")
    if not allowed_email(email):
        raise HTTPException(status_code=403, detail=f"Account {email} is not authorized.")
    fp = device_fingerprint_from_request(request)
    trusted_device_id = trusted_device_id_for_fingerprint(
        fp,
        email,
        register_trusted_device=register_trusted_device,
        get_trusted_device_by_fingerprint=get_trusted_device_by_fingerprint,
        is_device_trusted=is_device_trusted,
    )
    session_id = create_session(fp, trusted=True, user_id=email)
    prewarm_session(session_id, email)
    resp = JSONResponse({"ok": True, "session_id": session_id, "trusted_device_id": trusted_device_id})
    _attach_auth_cookies(resp, request, session_id, trusted_device_id)
    return resp


@app.post("/api/auth/verify-share")
async def verify_share(request: Request, body: dict, response: Response):
    code = body.get("code", "")
    share = validate_share(code)
    if not share:
        return JSONResponse({"ok": False, "error": "Invalid share code"}, status_code=400)
    response.set_cookie("share_code", code, httponly=True, secure=_cookie_secure_flag(request), samesite="lax")
    return {"ok": True, "path": share["path"]}


@app.post("/api/auth/verify-otp")
async def verify_totp_login(request: Request, body: dict):
    code = (body.get("code") or "").strip()
    if not code:
        return JSONResponse({"ok": False, "error": "Code required."}, status_code=400)

    ok, error = verify_otp(code, request.client.host)
    if not ok:
        return JSONResponse({"ok": False, "error": error or "Invalid code."}, status_code=400)

    fp = device_fingerprint_from_request(request)
    user_id = _default_user_id()
    trusted_device_id = trusted_device_id_for_fingerprint(
        fp,
        user_id,
        register_trusted_device=register_trusted_device,
        get_trusted_device_by_fingerprint=get_trusted_device_by_fingerprint,
    )
    session_id = create_session(fp, trusted=True, user_id=user_id)
    prewarm_session(session_id, user_id)

    response = JSONResponse({"ok": True})
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    session_id = get_session_id(request)
    if session_id:
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    resp.delete_cookie(TRUSTED_DEVICE_COOKIE)
    return resp


@app.get("/api/auth/devices")
async def list_devices(_=Depends(require_auth)):
    return get_trusted_devices()


@app.delete("/api/auth/devices/{device_id}")
async def delete_device(device_id: str, _=Depends(require_auth)):
    revoke_device(device_id)
    return {"ok": True}


@app.post("/api/auth/check")
async def check_auth(request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    response = JSONResponse({"authenticated": bool(session_id)})
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


@app.post("/api/auth/is-new-device")
async def is_new_device(request: Request):
    fp = device_fingerprint_from_request(request)
    return {"new_device": not is_device_trusted(fp)}


@app.get("/api/jane/announcements")
async def get_announcements(request: Request, since: Optional[str] = None, _=Depends(require_auth)):
    result = {"items": [_tokenize_ra_report_item(item, request) for item in _read_announcements(since)]}
    # Piggyback pending device commands on announcement polls
    cmds = _drain_pending_commands()
    if cmds:
        result["pending_commands"] = cmds
    return result


def _ra_report_html_response(path: Path, request: Request, report_id: str) -> HTMLResponse:
    page = path.read_text(encoding="utf-8", errors="replace")
    share_url = build_external_url(request, _ra_report_share_path(report_id), "JANE_PUBLIC_BASE_URL")
    page = page.replace(
        'data-share-url=""',
        f'data-share-url="{html.escape(share_url, quote=True)}"',
        1,
    )
    return HTMLResponse(page)


@app.get("/api/research/ra/reports/latest")
async def get_latest_ra_report(request: Request, _=Depends(require_auth)):
    path = _latest_ra_report_html_path()
    return _ra_report_metadata(path, request)


@app.get("/api/research/ra/reports/{report_id}.html")
async def get_ra_report_html(report_id: str, request: Request, rt: Optional[str] = None):
    path = _ra_report_html_path(report_id)
    _require_ra_report_access(request, report_id, rt)
    return _ra_report_html_response(path, request, report_id)


@app.get("/research/ra/reports/latest", response_class=HTMLResponse)
async def latest_ra_report_page(request: Request, _=Depends(require_auth)):
    path = _latest_ra_report_html_path()
    _ra_report_metadata(path, request)
    return _ra_report_html_response(path, request, _ra_report_id_from_html_path(path))


@app.get("/research/ra/reports/{report_id}", response_class=HTMLResponse)
async def ra_report_page(report_id: str, request: Request, rt: Optional[str] = None):
    path = _ra_report_html_path(report_id)
    _require_ra_report_access(request, report_id, rt)
    return _ra_report_html_response(path, request, report_id)


@app.get("/share/research/ra/reports/{report_id}/{share_token}", response_class=HTMLResponse)
async def public_ra_report_page(report_id: str, share_token: str, request: Request):
    path = _ra_report_html_path(report_id)
    if not _valid_ra_report_share_token(report_id, share_token):
        raise HTTPException(status_code=404, detail="Report not found")
    return _ra_report_html_response(path, request, report_id)


# ─── Device command queue (server → Android) ─────────────────────────────────
# Simple in-memory queue. Commands are drained on each announcement poll.
# Used for server-initiated actions like "sync your SMS now".

_device_command_queue = DeviceCommandQueue()
_pending_device_commands = _device_command_queue.commands
_pending_lock = _device_command_queue.lock
queue_device_command = _device_command_queue.queue
_drain_pending_commands = _device_command_queue.drain


@app.post("/api/device/sync-sms")
async def trigger_sms_sync(session_id: str = Depends(require_auth)):
    """Server-initiated SMS sync. Queues a command for the Android app."""
    _require_capability(session_id, "phone")
    queue_device_command("sync_sms")
    return {"status": "queued", "message": "SMS sync will trigger on next Android poll"}


# ─── User Administration ─────────────────────────────────────────────────────

class CreateManagedUserRequest(BaseModel):
    email: str
    display_name: Optional[str] = None
    capabilities: Optional[list[str]] = None
    seed_memories: Optional[list[str]] = None


@app.get("/api/admin/users")
async def list_managed_users(session_id: str = Depends(require_auth)):
    _require_admin_session(session_id)
    from agent_skills.user_manager import AVAILABLE_CAPABILITIES, list_users
    return {
        "users": [_public_user_config(config) for config in list_users()],
        "capabilities": AVAILABLE_CAPABILITIES,
    }


@app.post("/api/admin/users")
async def create_managed_user(body: CreateManagedUserRequest, session_id: str = Depends(require_auth)):
    admin_user = _require_admin_session(session_id)
    email = _normalize_managed_user_email(body.email)

    from agent_skills.user_manager import create_user_space, normalize_user_id, user_config_exists

    user_id = normalize_user_id(email)
    if user_config_exists(user_id):
        raise HTTPException(status_code=409, detail=f"User {email} already exists.")

    display_name = _managed_user_display_name(body.display_name, email)
    seed_memories = _clean_seed_memories(body.seed_memories)
    config = create_user_space(
        user_id,
        display_name,
        email=email,
        capabilities=body.capabilities,
        seed_memories=seed_memories,
    )
    allowlist_updated = _add_allowed_google_email(email)
    _logger.info(
        "Managed user created by %s: user_id=%s email=%s capabilities=%s allowlist_updated=%s",
        admin_user,
        user_id,
        email,
        config.get("capabilities"),
        allowlist_updated,
    )
    return {
        "ok": True,
        "user": _public_user_config(config),
        "allowlist_updated": allowlist_updated,
    }


@app.delete("/api/admin/users/{user_id}")
async def delete_managed_user(user_id: str, session_id: str = Depends(require_auth)):
    """Delete a managed user's config, memory, and vault. Admin-only.

    Refuses to delete the admin's own account. Allowlist (ALLOWED_GOOGLE_EMAILS)
    is also cleaned up if the user had an email attached.
    """
    admin_user = _require_admin_session(session_id)
    from agent_skills.user_manager import (
        delete_user_space,
        get_user_config,
        normalize_user_id,
        user_config_exists,
    )

    target = normalize_user_id(user_id)
    if not user_config_exists(target):
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if target == normalize_user_id(admin_user):
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")

    # Pull email so we can also remove from the Google allowlist.
    email = (get_user_config(target).get("email") or "").strip().lower()

    result = delete_user_space(target)
    if not result.get("removed"):
        raise HTTPException(
            status_code=400,
            detail=f"Could not delete user: {result.get('reason', 'unknown')}",
        )

    allowlist_updated = _remove_allowed_google_email(email) if email else False

    _logger.info(
        "Managed user deleted by %s: user_id=%s email=%s allowlist_updated=%s",
        admin_user, target, email, allowlist_updated,
    )
    return {"ok": True, "user_id": target, "allowlist_updated": allowlist_updated}


# ─── Brain Model Settings ────────────────────────────────────────────────────


@app.get("/api/settings/models")
async def get_model_settings(_=Depends(require_auth)):
    """Return current model config, available options, and 3-tier architecture."""
    return build_model_settings_payload(os.environ)


@app.post("/api/settings/models")
async def save_model_settings(request: Request, _=Depends(require_auth)):
    """Save model selection to .env and restart the standing brain."""
    body = await request.json()
    env_var, model, error = model_save_target(body, os.environ)
    if error:
        return error

    _write_env_var(env_var, model)

    # Restart the standing brain so it picks up the new model
    try:
        from llm_brain.v1.standing_brain import get_standing_brain_manager
        manager = get_standing_brain_manager()
        if manager._started:
            await manager.shutdown()
            await manager.start()
            logger.info("Standing brain restarted with model=%s after settings change", model)
    except Exception:
        logger.exception("Failed to restart standing brain after model change")

    return {"ok": True, "model": model}


# ─── Live Broadcast SSE ──────────────────────────────────────────────────────

@app.get("/api/jane/live")
async def jane_live_stream(request: Request):
    """SSE endpoint: broadcasts summarized progress when Jane is working on another session."""
    from jane_web.broadcast import broadcast_manager

    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = get_session_user(session_id) or _default_user_id()

    q = await broadcast_manager.subscribe(user_id)

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield event.to_json() + "\n"
                except asyncio.TimeoutError:
                    # Send keepalive to prevent proxy/browser timeout
                    yield json.dumps({"type": "keepalive"}) + "\n"
        finally:
            await broadcast_manager.unsubscribe(user_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jane/prefetch-memory")
async def prefetch_memory(request: Request):
    """Pre-fetch memory context while user is idle. Cached for 60s.

    Fire-and-forget: starts a background query and returns immediately.
    When the user sends their first message, the cached result is used as
    memory_summary_fallback, skipping the ChromaDB round-trip.
    """
    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    run_prefetch_memory(session_id, get_session_user(session_id) or _default_user_id())
    return {"status": "ok", "cached": True}


# ─── Files API (shared vault) ─────────────────────────────────────────────────

@app.get("/api/files")
async def list_root(
    request: Request,
    offset: int = 0,
    limit: int = 0,
    session_id: str = Depends(require_auth),
):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    return _paginate_listing(list_directory("", root_dir=vault_root), offset, limit)


@app.get("/api/files/list/{path:path}")
async def list_path(
    path: str,
    request: Request,
    offset: int = 0,
    limit: int = 0,
    session_id: str = Depends(require_auth),
):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    return _paginate_listing(list_directory(path, root_dir=vault_root), offset, limit)


@app.get("/api/files/meta/{path:path}")
async def file_meta(path: str, request: Request, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    return get_file_metadata(path, root_dir=vault_root)


@app.patch("/api/files/description/{path:path}")
async def update_file_description(path: str, body: dict, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, uid = _require_capability(session_id, "vault_write")
    ok = update_description(path, body.get("description", ""), root_dir=vault_root, user_id=uid)
    return {"ok": ok}


@app.get("/api/files/thumbnail/{path:path}")
async def thumbnail(path: str, request: Request):
    check_share_or_auth(request, path)
    vault_root = _request_vault_root(request)
    data = generate_thumbnail(path, root_dir=vault_root)
    if not data:
        raise HTTPException(status_code=404)
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/files/serve/{path:path}")
async def serve_file(path: str, request: Request):
    check_share_or_auth(request, path)
    vault_root = _request_vault_root(request)
    try:
        target = safe_vault_path(path, root_dir=vault_root)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    mime = get_mime(target.name)
    range_header = request.headers.get("range")
    if range_header:
        return _range_response(target, mime, range_header)
    headers = {}
    if mime and mime.startswith("image/"):
        headers["Cache-Control"] = "public, max-age=86400, immutable"
    return FileResponse(str(target), media_type=mime, headers=headers)


@app.get("/api/files/changes")
async def file_changes(_=Depends(require_auth)):
    return {"last_change": get_last_change_timestamp()}


@app.get("/api/files/find")
async def find_file(name: str, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    name = os.path.basename(name)
    for root, dirs, files in os.walk(vault_root):
        if name in files:
            rel = os.path.relpath(os.path.join(root, name), vault_root)
            return {"path": rel}
    raise HTTPException(status_code=404, detail="File not found in vault")


@app.get("/api/files/search")
async def search_files(q: str, type: Optional[str] = None, session_id: str = Depends(require_auth)):
    """Search vault files by name and ChromaDB description."""
    if not q or not q.strip():
        return {"results": []}

    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    query = q.strip().lower()
    type_exts = _FILE_TYPE_EXTENSIONS.get(type) if type else None
    results_map: dict[str, dict] = _filename_search_results(
        vault_root=vault_root,
        query=query,
        type_exts=type_exts,
        detect_file_type=_detect_file_type,
    )

    # 2. Query ChromaDB for file descriptions
    try:
        _skills_dir = os.path.join(
            os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence")),
            "agent_skills",
        )
        if _skills_dir not in sys.path:
            sys.path.insert(0, _skills_dir)
        from memory_retrieval import _query_collection
        vector_db = os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        ) + "/memory/v1/vector_db"
        # Managed users must never see another user's description, even if two
        # users happen to have a same-named file. We filter by the user_id
        # metadata tag written by upsert_file_index_entry.
        allowed_scope = _uid if _managed else None
        for collection_name in ("vault_files", "facts"):
            try:
                docs, metas, _dists = _query_collection(vector_db, collection_name, q, 20)
                _merge_index_search_results(
                    results_map,
                    docs,
                    metas,
                    vault_root=vault_root,
                    type_exts=type_exts,
                    allowed_scope=allowed_scope,
                    detect_file_type=_detect_file_type,
                )
                break  # If first collection worked, don't try fallback
            except Exception:
                continue
    except Exception:
        pass  # ChromaDB not available — filename results only

    results = list(results_map.values())[:20]
    return {"results": results}


@app.get("/api/files/play/{path:path}")
async def play_audio_file(path: str, session_id: str = Depends(require_auth)):
    """Serve an audio file with appropriate headers for streaming playback."""
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    try:
        target = safe_vault_path(path, root_dir=vault_root)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    mime = get_mime(target.name)
    return FileResponse(
        str(target),
        media_type=mime,
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/api/files/content/{path:path}")
async def get_file_content(path: str, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_read")
    try:
        target = safe_vault_path(path, root_dir=vault_root)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    if not is_text(target.name):
        raise HTTPException(status_code=400, detail="Not a text file")
    if target.stat().st_size > TEXT_SIZE_LIMIT:
        raise HTTPException(status_code=413, detail="File too large to edit in browser")
    async with aiofiles.open(target, "r", encoding="utf-8", errors="replace") as f:
        content = await f.read()
    return {"content": content}


@app.put("/api/files/content/{path:path}")
async def save_file_content(path: str, body: dict, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, _uid = _require_capability(session_id, "vault_write")
    try:
        target = safe_vault_path(path, root_dir=vault_root)
    except ValueError:
        raise HTTPException(status_code=403)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404)
    if not is_text(target.name):
        raise HTTPException(status_code=400, detail="Not a text file")
    async with aiofiles.open(target, "w", encoding="utf-8") as f:
        await f.write(body.get("content", ""))
    with get_db() as conn:
        conn.execute("INSERT INTO file_changes DEFAULT VALUES")
    return {"ok": True}


@app.delete("/api/files/{path:path}")
async def delete_file(path: str, session_id: str = Depends(require_auth)):
    vault_root, _caps, _managed, uid = _require_capability(session_id, "vault_write")
    result = delete_vault_file(path, root_dir=vault_root, user_id=uid)
    error = result.get("error")
    if error == "Invalid path":
        raise HTTPException(status_code=403, detail=error)
    if error == "Not found":
        raise HTTPException(status_code=404, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    _log_work_activity(f"File delete: {result.get('path', path)}", category="file_delete")
    return result


@app.post("/api/files/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    destination: str = Form(""),
    descriptions_json: str = Form("[]"),
    session_id: str = Depends(require_auth),
):
    vault_root_str, _caps, _managed, upload_user_id = _require_capability(session_id, "vault_write")
    vault_root = Path(vault_root_str)
    hash_index_path = vault_root / ".hash_index.json"
    descriptions = parse_upload_descriptions(descriptions_json)
    hash_index = load_upload_hash_index(hash_index_path)

    results = []
    for index, upload in enumerate(files):
        data = await upload.read()
        file_hash = hashlib.sha256(data).hexdigest()

        if file_hash in hash_index:
            existing = hash_index[file_hash]
            results.append(duplicate_upload_result(upload.filename, existing))
            continue

        mime = upload.content_type or get_mime(upload.filename or "")
        subdir = upload_subdir(destination, mime, _route_subdir)
        description = upload_description(descriptions, index)
        is_image_upload = mime.startswith("image/")
        if is_image_upload and not description:
            raise HTTPException(status_code=400, detail="Image uploads require a description.")

        dest_dir = vault_root / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = upload_safe_name(
            upload.filename,
            description,
            is_image_upload=is_image_upload,
            destination=destination,
            descriptive_filename=make_descriptive_filename,
        )
        dest_path = next_available_path(dest_dir, safe_name)

        with open(dest_path, "wb") as f:
            f.write(data)

        rel_path = str(dest_path.relative_to(vault_root))
        hash_index[file_hash] = hash_index_entry(dest_path, rel_path, description)
        upsert_file_index_entry(
            rel_path,
            description,
            mime,
            updated_by="jane_web_upload",
            root_dir=vault_root,
            user_id=upload_user_id,
        )

        try:
            _add_fact_cmd = upload_memory_fact_command(
                python_bin=ADK_VENV_PYTHON,
                add_fact_script=ADD_FACT_SCRIPT,
                fact_text=upload_memory_fact_text("via web UI", dest_path.name, subdir),
                user_id=upload_user_id,
                memory_path=_user_memory_path(upload_user_id),
            )
            subprocess.run(_add_fact_cmd, timeout=10, capture_output=True)
        except Exception:
            pass

        results.append(upload_success_result(upload.filename, dest_path, rel_path, subdir, description))

    write_upload_hash_index(hash_index_path, hash_index)

    with get_db() as conn:
        conn.execute("INSERT INTO file_changes DEFAULT VALUES")

    activity_message = upload_work_activity_message(results)
    if activity_message:
        _log_work_activity(activity_message, category="file_upload")

    return {"results": results}


@app.post("/api/files/upload/single")
async def upload_single_file(
    request: Request,
    file: UploadFile = File(...),
):
    """Simple single-file upload for Android — returns a serveable URL."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    vault_root_str, _caps, _managed, upload_user_id = _require_capability(session_id, "vault_write")
    vault_root = Path(vault_root_str)
    data = await file.read()
    mime = file.content_type or get_mime(file.filename or "")
    subdir = "working_files/android_uploads"
    dest_dir = vault_root / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "upload").name
    dest_path = next_available_path(dest_dir, safe_name)

    with open(dest_path, "wb") as f:
        f.write(data)

    rel_path = str(dest_path.relative_to(vault_root))

    # Index in ChromaDB so Jane and memory system can find the file
    try:
        from vault_web.files import upsert_file_index_entry
        upsert_file_index_entry(
            rel_path,
            f"File uploaded from Android: {dest_path.name}",
            mime,
            updated_by="android_upload",
            root_dir=vault_root,
            user_id=upload_user_id,
        )
    except Exception:
        pass

    # Save to memory
    try:
        import subprocess as _sp
        _add_fact_cmd = upload_memory_fact_command(
            python_bin=sys.executable,
            add_fact_script=str(Path(__file__).resolve().parents[1] / "agent_skills" / "add_fact.py"),
            fact_text=upload_memory_fact_text("from Android", dest_path.name, subdir),
            user_id=upload_user_id,
            memory_path=_user_memory_path(upload_user_id),
        )
        _sp.run(_add_fact_cmd, timeout=10, capture_output=True)
    except Exception:
        pass

    response = JSONResponse({
        "file_url": f"/api/files/serve/{rel_path}",
        "filename": dest_path.name,
        "path": rel_path,
        "mime": mime,
    })
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


# ─── Share API ────────────────────────────────────────────────────────────────

@app.get("/api/shares")
async def get_shares(_=Depends(require_auth)):
    return list_shares()


@app.post("/api/shares")
async def new_share(body: dict, _=Depends(require_auth)):
    code = create_share(body.get("path", ""), body.get("recipient", "guest"))
    return {"ok": True, "code": code}


@app.delete("/api/shares/{share_id}")
async def delete_share(share_id: str, _=Depends(require_auth)):
    revoke_share(share_id)
    return {"ok": True}


# ─── Playlist API ─────────────────────────────────────────────────────────────

@app.get("/api/playlists")
async def get_playlists(_=Depends(require_auth)):
    return list_playlists()


@app.get("/api/playlists/{playlist_id}")
async def get_single_playlist(playlist_id: str, _=Depends(require_auth)):
    p = get_playlist(playlist_id)
    if not p:
        raise HTTPException(status_code=404)
    return p


@app.post("/api/playlists")
async def new_playlist(body: dict, _=Depends(require_auth)):
    return create_playlist(body.get("name", "New Playlist"), body.get("tracks", []))


@app.put("/api/playlists/{playlist_id}")
async def update_playlist_route(playlist_id: str, body: dict, _=Depends(require_auth)):
    p = update_playlist(playlist_id, body.get("name"), body.get("tracks"))
    if not p:
        raise HTTPException(status_code=404)
    return p


@app.delete("/api/playlists/{playlist_id}")
async def delete_playlist_route(playlist_id: str, _=Depends(require_auth)):
    delete_playlist(playlist_id)
    return {"ok": True}


def _cleanup_temporary_playlists():
    """Delete old Jane-generated temporary playlists from the database.

    Jane creates playlists named "Random Mix" or "Playing: <query>" via voice
    commands. These are meant to be ephemeral — played once and discarded.
    Without cleanup they accumulate indefinitely.

    Keeps playlists created in the last 5 minutes so the Android app has
    time to fetch them before they're deleted.
    """
    _cleanup_temporary_playlists_impl(
        list_playlists_fn=list_playlists,
        delete_playlist_fn=delete_playlist,
        logger=_logger,
    )


def create_music_playlist_from_query(query: str) -> dict | None:
    """Search vault music by query and create a temporary playlist.

    Returns playlist dict {"id", "name", "tracks", ...} or None if no matches.
    Shared by /api/music/play endpoint and jane_proxy Stage 2 music handler.
    Cleans up any prior temporary playlists first so they don't accumulate.

    Matching tiers:
      Tier 0: existing named user playlist (exact / substring / fuzzy) —
              returns the existing playlist, does NOT create a new one.
      Tier 1-4: substring / word / OR / fuzzy scan over vault/Music/*.mp3,
                builds a new ephemeral playlist from the matched files.
    """
    import glob as _glob, random as _random

    return _music_playlist_from_query(
        query,
        list_playlists_fn=list_playlists,
        get_playlist_fn=get_playlist,
        create_playlist_fn=create_playlist,
        delete_playlist_fn=delete_playlist,
        vault_home=os.environ.get("VAULT_HOME", Path.home() / "ambient" / "vault"),
        glob_files_fn=_glob.glob,
        random_sample_fn=_random.sample,
        logger=_logger,
    )


@app.post("/api/music/play")
async def music_play(body: dict, _=Depends(require_auth)):
    """Search vault music by query and create a temporary playlist.

    Body: {"query": "the scientist"} or {"query": "shakira"} or {"query": "random"}
    Returns: {"playlist_id": "...", "name": "...", "tracks": [...], "temporary": true}
    """
    query = (body.get("query") or "").strip()
    playlist = create_music_playlist_from_query(query)
    if playlist is None:
        raise HTTPException(status_code=404, detail=f"No tracks matching '{query}'")
    return playlist


# ─── Jane Chat API ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: str
    file_context: Optional[str] = None
    platform: Optional[str] = None  # "web", "android", "cli"
    tts_enabled: Optional[bool] = False


class SessionControl(BaseModel):
    session_id: str


async def _handle_jane_chat(body: ChatMessage, request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        _logger.warning(
            "Rejected jane chat request: no authenticated session body_session=%s ip=%s",
            _session_log_id(body.session_id),
            _client_ip(request),
        )
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = get_session_user(session_id) or _default_user_id()
    _logger.info(
        "Accepted jane chat request session=%s user=%s msg_len=%d file_ctx=%s body_session=%s",
        _session_log_id(session_id),
        user_id,
        len(body.message or ""),
        bool(body.file_context),
        _session_log_id(body.session_id),
    )
    result = await send_message(user_id, session_id, body.message, body.file_context, platform=body.platform, tts_enabled=body.tts_enabled or False)
    response = JSONResponse({"response": result.get("text", ""), "files": result.get("files", [])})
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


def _should_use_v2(body: ChatMessage) -> bool:
    """Every chat request now goes through the v2 3-stage pipeline.

    The only escape hatch is the env var JANE_PIPELINE=v1, which forces
    every caller back to v1 (for emergency rollback). Unset or any other
    value → v2.

    Stage 3 of v2 delegates to v1's brain internally, so web users still
    get the rich Opus "thinking stream" for anything that escalates past
    Stage 2 (weather/music get answered locally by the local LLM and skip Opus).
    """
    return _should_use_v2_pipeline(os.environ)


def _should_use_v3(body: ChatMessage) -> bool:
    """Opt-in to jane_v3 pipeline (FIFO-aware Haiku classification).

    Enable with `JANE_USE_V3_PIPELINE=1` in .env. When enabled, v3 takes
    precedence over v2 for every chat request on the configured user. When
    the flag is unset or any non-1 value, v2 continues to serve — v3 code
    is never imported. This flag is independent of `JANE_PIPELINE=v1`
    which forces the old gemma_router path regardless.
    """
    return _should_use_v3_pipeline(os.environ)


@app.post("/api/jane/chat")
async def jane_chat(body: ChatMessage, request: Request):
    if _should_use_v3(body):
        from jane_web.jane_v3.pipeline import handle_chat as _v3_handle_chat
        return await _v3_handle_chat(body, request)
    if _should_use_v2(body):
        from jane_web.jane_v2.pipeline import handle_chat as _v2_handle_chat
        return await _v2_handle_chat(body, request)
    return await _handle_jane_chat(body, request)


@app.post("/api/jane/session/end")
async def jane_end_session(body: SessionControl, request: Request):
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    _logger.info(
        "Ending Jane session active_session=%s body_session=%s ip=%s",
        _session_log_id(session_id),
        _session_log_id(body.session_id),
        _client_ip(request),
    )
    user_id = get_session_user(session_id) or _default_user_id()
    end_session(user_id, session_id)
    response = JSONResponse({"ok": True})
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


# ─── Provider Switch API ──────────────────────────────────────────────────────

class SwitchProviderRequest(BaseModel):
    provider: str

@app.post("/api/jane/switch-provider")
async def switch_provider(body: SwitchProviderRequest, request: Request):
    """Switch the active LLM provider at runtime (kill old CLI, start new one)."""
    session_id, trusted_device_id = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_provider = body.provider.lower().strip()
    if new_provider not in ("claude", "gemini", "openai"):
        return JSONResponse({"ok": False, "error": f"Unknown provider: {new_provider}"}, status_code=400)

    from llm_brain.v1.standing_brain import get_standing_brain_manager
    manager = get_standing_brain_manager()

    _logger.info("Provider switch requested: → %s (session=%s, ip=%s)",
                 new_provider, _session_log_id(session_id), _client_ip(request))

    result = await manager.switch_provider(new_provider)

    if result.get("ok") and result.get("needs_auth"):
        # Return info so the frontend can trigger the OAuth flow
        result["auth_endpoint"] = "/api/cli-login"
        result["auth_status_endpoint"] = "/api/cli-login/status"

    return JSONResponse(result)


@app.get("/api/jane/current-provider")
async def current_provider(_=Depends(require_auth)):
    """Return the currently active provider, model, and all available providers."""
    from llm_brain.v1.standing_brain import get_standing_brain_manager, _PROVIDER
    manager = get_standing_brain_manager()
    health = await manager.health_check()
    return JSONResponse(current_provider_payload(_PROVIDER, health))


# ─── Generic Essence Tool API ─────────────────────────────────────────────────
# Allows any essence's custom_tools.py functions to be called via API
# without hardcoding routes per essence.

@app.post("/api/essence/{essence_name}/tool/{tool_name}")
async def call_essence_tool(essence_name: str, tool_name: str, request: Request, _=Depends(require_auth)):
    """Generic endpoint to invoke any essence tool by name."""
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    search_dirs = essence_search_dirs(ambient_base, os.environ.get("TOOLS_DIR"))
    tools_path = find_essence_tools_path(essence_name, search_dirs)

    if not tools_path:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found or has no tools")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    cmd = essence_tool_command(python_bin, tools_path, tool_name, body)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                cwd=os.path.dirname(tools_path))
        if result.returncode != 0:
            return JSONResponse(essence_tool_error_payload(result.stderr), status_code=500)
        return JSONResponse(essence_tool_success_payload(result.stdout))
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Tool execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dynamic essence page serving
@app.get("/essence/{essence_name}", response_class=HTMLResponse)
async def serve_essence_page(essence_name: str, request: Request, _=Depends(require_auth)):
    """Serve an essence's UI — or redirect to Jane's chat for essence-type items."""
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    search_dirs = essence_search_dirs(ambient_base, os.environ.get("TOOLS_DIR"))
    page_target = find_essence_page_target(essence_name, search_dirs)
    essence_type = page_target["essence_type"]
    essence_folder_name = page_target["folder_name"]
    template_path = page_target["template_path"]

    # Essence-type items redirect to Jane's chat with the essence activated
    if essence_type == "essence" and essence_folder_name:
        return RedirectResponse(url=f"/?essence={essence_folder_name}", status_code=302)

    if not template_path:
        raise HTTPException(status_code=404, detail=f"No UI template found for essence '{essence_name}'")

    with open(template_path) as f:
        html = f.read()
    return HTMLResponse(html)




# ─── Instant Commands (no LLM, no ChromaDB, <100ms) ─────────────────────────

def _check_instant_command(message: str, platform: str = "web") -> str | None:
    """Check if a message is an exact data-lookup command. Returns formatted result or None.

    Only matches short imperative commands, not questions or sentences that
    happen to contain the keyword.
    """
    del platform
    return instant_command_response(message)


# ─── Chat Stream ─────────────────────────────────────────────────────────────

# Per-IP concurrent SSE stream limit — prevents a single IP from consuming
# all available CLI brain slots.
_active_streams: dict[str, int] = {}
_MAX_STREAMS_PER_IP = 3


async def _handle_jane_chat_stream(body: ChatMessage, request: Request):
    session_id, trusted_device_id = _chat_stream_session_for_request(
        request,
        body_session_id=body.session_id,
        get_or_bootstrap_session_fn=get_or_bootstrap_session,
        is_local_control_ip_fn=_is_local_control_ip,
    )
    if not session_id:
        _logger.warning(
            "Rejected jane stream request: no authenticated session body_session=%s ip=%s",
            _session_log_id(body.session_id),
            _client_ip(request),
        )
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ── Idempotency dedupe (job_076) ────────────────────────────────────────
    # Android's ChatRepository attaches X-Request-ID per voice turn. A retry
    # of the same turn_id within DEDUPE_TTL_SECONDS must NOT re-dispatch the
    # brain, or side-effecting tools (SMS, calendar write) fire twice.
    turn_id = request.headers.get("X-Request-ID", "").strip()
    if turn_id:
        dedupe_start = await begin_turn_dedupe(turn_id, session_id)
        if dedupe_start.pending_join_waited:
            _logger.info(
                "[%s] turn_dedupe PENDING join-wait turn_id=%s",
                _session_log_id(session_id), turn_id[:8],
            )
        if dedupe_start.replay_response_json is not None:
            if dedupe_start.replay_reason == "completed":
                _logger.info(
                    "[%s] turn_dedupe COMPLETED replay turn_id=%s",
                    _session_log_id(session_id), turn_id[:8],
                )
            return StreamingResponse(
                iter_replay_ndjson(dedupe_start.replay_response_json),
                media_type="application/x-ndjson",
            )
        turn_id = dedupe_start.active_turn_id
    # ── End idempotency dedupe ──────────────────────────────────────────────
    _logger.info(
        "Accepted jane stream request session=%s msg_len=%d file_ctx=%s body_session=%s ip=%s",
        _session_log_id(session_id),
        len(body.message or ""),
        bool(body.file_context),
        _session_log_id(body.session_id),
        _client_ip(request),
    )

    # ── Concurrent stream limit per IP ──────────────────────────────────────
    stream_ip = _client_ip(request)
    if stream_limit_exceeded(_active_streams, stream_ip, _MAX_STREAMS_PER_IP):
        _logger.warning("Concurrent stream limit hit for %s (%d active)", stream_ip, _active_streams.get(stream_ip, 0))
        return JSONResponse(
            {"error": "Too many concurrent streams. Please close a tab and try again."},
            status_code=429,
        )

    # ── Instant commands: bypass all LLM processing for pure data lookups ──
    raw_message = (body.message or "").strip()
    instant_result = _check_instant_command(raw_message, platform=body.platform or "web")
    if instant_result is not None:
        async def _instant_stream():
            for chunk in _instant_command_stream_chunks(instant_result):
                yield chunk
        return StreamingResponse(_instant_stream(), media_type="application/x-ndjson")

    # ── Big-task offload check ──────────────────────────────────────────────
    from jane_web.task_classifier import classify_task, strip_bg_prefix
    from jane_web.task_offloader import offload_task

    task_class = classify_task(raw_message)

    if task_class == "big":
        clean_message = strip_bg_prefix(raw_message)
        task_id = offload_task(clean_message, session_id, body.file_context, body.platform)
        _logger.info(
            "Offloaded big task %s session=%s msg_len=%d",
            task_id, _session_log_id(session_id), len(clean_message),
        )

        async def offloaded_stream():
            for chunk in _offloaded_task_stream_chunks(task_id):
                yield chunk

        response = StreamingResponse(
            offloaded_stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        _attach_auth_cookies(response, request, session_id, trusted_device_id)
        return response

    # ── Normal streaming flow ─────────────────────────────────────────────
    # Use the CLIENT's session_id (from body) for in-memory conversation state,
    # not the cookie-based auth session. The Android app maintains a stable
    # session_id ("jane_android_xxxx") across requests — using the cookie-based
    # session would create a new conversation state on every request.
    requested_conversation_session_id = body.session_id or session_id
    event_stream = _normal_chat_stream_chunks(
        active_streams=_active_streams,
        stream_ip=stream_ip,
        auth_session_id=session_id,
        body_session_id=body.session_id,
        requested_conversation_session_id=requested_conversation_session_id,
        message=body.message,
        file_context=body.file_context,
        platform=body.platform,
        tts_enabled=body.tts_enabled or False,
        turn_id=turn_id,
        response_wait_seconds=JANE_RESPONSE_WAIT_SECONDS,
        stream_message_fn=stream_message,
        get_session_user_fn=get_session_user,
        default_user_id_fn=_default_user_id,
        scoped_session_id_fn=_scoped_conversation_session_id,
        session_log_id_fn=_session_log_id,
        logger=_logger,
    )

    response = StreamingResponse(
        event_stream,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
    _attach_auth_cookies(response, request, session_id, trusted_device_id)
    return response


# ─── Permission Gate (web-based tool approval) ──────────────────────────────

@app.post("/api/jane/permission/request")
async def permission_request_endpoint(request: Request):
    """Called by the PreToolUse hook inside the CLI. Blocks until user responds."""
    from jane_web.permission_broker import get_permission_broker
    body = await request.json()
    broker = get_permission_broker()
    req = await broker.create_request(**permission_request_args(body))
    approved = await broker.wait_for_response(req)
    return JSONResponse(permission_wait_payload(approved, req))


@app.post("/api/jane/permission/respond")
async def permission_respond_endpoint(request: Request, _=Depends(require_auth)):
    """Called by the web frontend when user clicks approve/deny."""
    from jane_web.permission_broker import get_permission_broker
    body = await request.json()
    broker = get_permission_broker()
    success = broker.resolve(**permission_response_args(body))
    return JSONResponse({"ok": success})


@app.get("/api/jane/permission/pending")
async def permission_pending_endpoint(request: Request, _=Depends(require_auth)):
    """Return all pending permission requests (for page reload recovery)."""
    from jane_web.permission_broker import get_permission_broker
    broker = get_permission_broker()
    pending = broker.get_all_pending()
    return JSONResponse({"requests": [permission_pending_entry(r) for r in pending]})


@app.post("/api/jane/chat/stream")
async def jane_chat_stream(body: ChatMessage, request: Request):
    if _should_use_v3(body):
        from jane_web.jane_v3.pipeline import handle_chat_stream as _v3_handle_chat_stream
        return await _v3_handle_chat_stream(body, request)
    if _should_use_v2(body):
        from jane_web.jane_v2.pipeline import handle_chat_stream as _v2_handle_chat_stream
        return await _v2_handle_chat_stream(body, request)
    return await _handle_jane_chat_stream(body, request)


@app.post("/api/jane/init-session")
async def jane_init_session(body: SessionControl, request: Request):
    """Pre-warm Jane's Claude CLI session so the first real message is fast.

    Triggers the full session init (CLAUDE.md, hooks, context build) with a
    lightweight prompt. Returns a streaming NDJSON response with status events
    and a greeting.
    """
    session_id, _ = get_or_bootstrap_session(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from jane_proxy import _get_brain_name, _use_persistent_claude, _use_persistent_codex, _get_execution_profile
    except ImportError:
        from .jane_proxy import _get_brain_name, _use_persistent_claude, _use_persistent_codex, _get_execution_profile
    from context_builder.v1.context_builder import build_jane_context_async

    brain_name = _get_brain_name()
    if not (_use_persistent_claude(brain_name) or _use_persistent_codex(brain_name)):
        # Non-persistent brains don't need pre-warming
        return JSONResponse({"status": "skipped", "greeting": "Hey! What's on your mind?"})

    if _use_persistent_claude(brain_name):
        from llm_brain.v1.persistent_claude import get_claude_persistent_manager
        manager = get_claude_persistent_manager()
        init_status = "Sending init prompt to Claude..."
    else:
        from llm_brain.v1.persistent_codex import get_codex_persistent_manager
        manager = get_codex_persistent_manager()
        init_status = "Sending init prompt to Codex..."
    session_user_id = get_session_user(session_id) or _default_user_id()
    session = await manager.get(session_user_id, body.session_id or session_id)

    if not session.is_fresh():
        # Already warm — no init needed
        return JSONResponse({"status": "already_warm", "greeting": ""})

    user_id = get_session_user(session_id) or _default_user_id()
    stream = _session_init_stream_chunks(
        manager=manager,
        build_context_async=build_jane_context_async,
        get_execution_profile_fn=_get_execution_profile,
        brain_name=brain_name,
        user_id=user_id,
        session_id=body.session_id or session_id,
        init_status=init_status,
        status_chunk_fn=_status_stream_chunk,
        done_chunk_fn=_done_stream_chunk,
        logger=_logger,
    )
    return StreamingResponse(stream, media_type="application/x-ndjson")


# ─── Essence Management API ──────────────────────────────────────────────────

from agent_skills.essence_loader import (
    load_essence,
    unload_essence,
    delete_essence,
    list_available_essences,
    list_available,
    list_loaded_essences,
    EssenceState,
)

_essence_states: dict[str, EssenceState] = {}
_capability_registry = None  # Initialized in _auto_load_essences()
_ACTIVE_ESSENCE_PATH = os.path.join(VESSENCE_DATA_HOME, "data", "active_essence.json")


def _read_active_essences() -> list[str]:
    """Read the active essence list from disk."""
    return read_active_essences(_ACTIVE_ESSENCE_PATH)


def _write_active_essences(active: list[str]) -> None:
    """Write the active essence list to disk."""
    write_active_essences(_ACTIVE_ESSENCE_PATH, active)


@app.get("/api/essences")
async def list_essences(type: str = "all", _=Depends(require_auth)):
    """List all available essences/tools. Optional ?type=tool or ?type=essence filter."""
    available = list_available_essences(type_filter=type)
    loaded_names = list_loaded_essences()
    results = []
    for e in available:
        manifest_path = os.path.join(e["path"], "manifest.json")
        capabilities, preferred_model = read_essence_manifest_summary(manifest_path)
        results.append(essence_list_item(
            e,
            capabilities=capabilities,
            preferred_model=preferred_model,
            loaded_names=loaded_names,
        ))
    return results


@app.get("/api/essences/active")
async def get_active_essences(_=Depends(require_auth)):
    """Get the currently active essence(s)."""
    return {"active": _read_active_essences()}


@app.get("/api/essences/work_log/activities")
async def get_work_log_activities_route(count: int = 50, _=Depends(require_auth)):
    """Get recent activities from the Work Log essence."""
    try:
        from agent_skills.work_log_tools import get_recent_activities
        activities = get_recent_activities(count=count)
        return {"activities": activities}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Work Log error: {exc}")


@app.get("/api/essences/capabilities")
async def get_capabilities_map_route(_=Depends(require_auth)):
    """Get the capability -> essence mapping for all loaded essences."""
    if _capability_registry is None:
        return {"capabilities": {}}
    return {"capabilities": _capability_registry._providers}


@app.get("/api/essences/{essence_name}")
async def get_essence_detail(essence_name: str, _=Depends(require_auth)):
    """Get details of a specific essence."""
    available = list_available_essences()
    match = find_essence_by_name(available, essence_name)
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    manifest_path = os.path.join(match["path"], "manifest.json")
    try:
        return read_essence_detail_manifest(manifest_path, essence_name, list_loaded_essences())
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read manifest: {exc}")


@app.post("/api/essences/{essence_name}/load")
async def load_essence_endpoint(essence_name: str, _=Depends(require_auth)):
    """Load an essence by name."""
    available = list_available_essences()
    match = find_essence_by_name(available, essence_name)
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    try:
        state = load_essence(match["path"])
        _essence_states[essence_name] = state
        # Register capabilities
        if _capability_registry:
            caps = state.capabilities.get("provides", [])
            if caps:
                _capability_registry.register(essence_name, caps)
        return loaded_essence_payload(state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/essences/{essence_name}/unload")
async def unload_essence_endpoint(essence_name: str, _=Depends(require_auth)):
    """Unload a loaded essence."""
    try:
        unload_essence(essence_name)
        _essence_states.pop(essence_name, None)
        # Unregister capabilities
        if _capability_registry:
            _capability_registry.unregister(essence_name)
        active = _read_active_essences()
        active, changed = remove_active_essence(active, essence_name)
        if changed:
            _write_active_essences(active)
        return {"status": "unloaded"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' is not loaded")


@app.delete("/api/essences/{essence_name}")
async def delete_essence_endpoint(essence_name: str, port_memory: bool = False, _=Depends(require_auth)):
    """Delete an essence. Use ?port_memory=true to port memory to Jane first."""
    try:
        delete_essence(essence_name, port_memory=port_memory)
        _essence_states.pop(essence_name, None)
        active = _read_active_essences()
        active, changed = remove_active_essence(active, essence_name)
        if changed:
            _write_active_essences(active)
        return {"status": "deleted", "memory_ported": port_memory}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/essences/{essence_name}/activate")
async def activate_essence(essence_name: str, _=Depends(require_auth)):
    """Set an essence as the active one. Accepts display name or folder name."""
    available = list_available_essences()
    match = find_essence_match(available, essence_name)
    if not match:
        raise HTTPException(status_code=404, detail=f"Essence '{essence_name}' not found")
    _write_active_essences([match["name"]])
    # Invalidate context builder cache so Jane picks up the new essence immediately
    _invalidate_essence_context_cache()
    return {"status": "activated", "name": match["name"]}


@app.post("/api/essences/deactivate")
async def deactivate_essence(_=Depends(require_auth)):
    """Deactivate all active essences — return Jane to baseline."""
    _write_active_essences([])
    _invalidate_essence_context_cache()
    return {"status": "deactivated"}


@app.post("/api/jane/invalidate-essence-cache")
async def invalidate_essence_cache(_=Depends(require_auth)):
    """Invalidate the context builder's cached essence personality and tools."""
    _invalidate_essence_context_cache()
    return {"status": "ok"}


def _invalidate_essence_context_cache():
    """Clear essence-related entries from the context builder's in-memory cache."""
    try:
        from context_builder.v1.context_builder import _context_cache
        for key in ["essence_personality", "essence_tools"]:
            _context_cache.pop(key, None)
    except Exception:
        pass  # non-fatal — cache will expire naturally within 5 minutes


# ─── Work Log Activity Logging ────────────────────────────────────────────────

def _log_work_activity(description: str, category: str = "general") -> None:
    """Log an activity to the Work Log essence if it is loaded."""
    try:
        from agent_skills.work_log_tools import log_activity
        log_activity(description, category=category)
    except Exception:
        pass  # Work log not available — non-fatal


# ─── Daily Briefing API ──────────────────────────────────────────────────────

_BRIEFING_FUNCTIONS_DIR = os.path.join(
    os.environ.get("TOOLS_DIR",
                   os.path.join(os.path.expanduser("~"), "ambient", "skills")),
    "daily_briefing", "functions"
)


def _briefing_tools():
    """Lazy import of daily briefing custom_tools."""
    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
    import custom_tools as _bt
    return _bt


@app.get("/api/briefing/articles")
async def get_briefing_articles(
    topic: Optional[str] = None,
    view: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    _=Depends(require_auth),
):
    """Get latest briefing articles.

    Filters: topic name, or view='saved'.
    Pagination: when `limit` is provided, returns that slice starting at `offset`.
    `full_summary` is omitted from the list view (call /api/briefing/article/{id} for the full text).
    """
    bt = _briefing_tools()
    result = bt.get_briefing_cards()
    if result.get("status") != "ok":
        return result
    cards = result["cards"]
    try:
        return build_briefing_articles_response(cards, topic=topic, view=view, limit=limit, offset=offset)
    except ValueError:
        raise HTTPException(status_code=400, detail="limit/offset must be integers")


@app.get("/api/briefing/article/{article_id}")
async def get_briefing_article_detail(article_id: str, _=Depends(require_auth)):
    """Get full article detail with comprehensive summary."""
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    bt = _briefing_tools()
    result = bt.get_article_detail(article_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
    return result


@app.get("/api/briefing/audio/{article_id}/{summary_type}")
async def briefing_audio(article_id: str, summary_type: str = "brief", _=Depends(require_auth)):
    """Serve pre-generated TTS audio for a briefing article (Opus/OGG preferred, WAV fallback).
    Returns 503 if system load is too high (protects TTS/CPU-heavy workloads)."""
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    if not is_briefing_identifier(summary_type):
        raise HTTPException(status_code=400, detail="Invalid summary_type")
    # Gate on system load — reject bulk downloads when the machine is busy
    try:
        load_1min = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        if load_1min / cpu_count > 0.8:
            return JSONResponse(
                status_code=503,
                content={"detail": "Server busy", "load": round(load_1min, 2)},
                headers={"Retry-After": "60"},
            )
    except OSError:
        pass  # getloadavg not available on this platform

    tools_dir = os.environ.get(
        "TOOLS_DIR",
        os.path.join(os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient")), "skills"),
    )
    audio_dir = daily_briefing_audio_dir(tools_dir)
    # Prefer Opus/OGG, fall back to legacy WAV
    audio = select_briefing_audio(audio_dir, article_id, summary_type)
    if audio:
        path, media_type = audio
        return FileResponse(path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Audio not available for this article")


@app.get("/api/briefing/topics")
async def get_briefing_topics(_=Depends(require_auth)):
    """Get all tracked topics."""
    bt = _briefing_tools()
    return bt.list_topics()


@app.post("/api/briefing/topics")
async def add_briefing_topic(body: dict, _=Depends(require_auth)):
    """Add a topic. Body: {name, keywords, priority}"""
    bt = _briefing_tools()
    name = body.get("name", "")
    keywords = body.get("keywords", [])
    priority = body.get("priority", "normal")
    if not name or not keywords:
        raise HTTPException(status_code=422, detail="name and keywords are required")
    category = body.get("category", "General")
    return bt.add_topic(name, keywords, priority, category)


@app.put("/api/briefing/topics/{topic_name}")
async def update_briefing_topic(topic_name: str, body: dict, _=Depends(require_auth)):
    """Update a topic. Body may contain: new_name, keywords, priority, category."""
    bt = _briefing_tools()
    update_fn = getattr(bt, "update_topic", None)
    if update_fn is None:
        raise HTTPException(status_code=501, detail="update_topic not available in daily_briefing tools")
    kwargs = {}
    if "new_name" in body and body["new_name"]:
        kwargs["new_name"] = body["new_name"]
    if "keywords" in body and body["keywords"] is not None:
        kwargs["keywords"] = body["keywords"]
    if "priority" in body and body["priority"]:
        kwargs["priority"] = body["priority"]
    if "category" in body and body["category"]:
        kwargs["category"] = body["category"]
    result = update_fn(topic_name, **kwargs)
    if result.get("status") == "error":
        msg = result.get("message", "")
        code = 409 if "already exists" in msg else 404
        raise HTTPException(status_code=code, detail=msg)
    return result


@app.delete("/api/briefing/topics/{topic_name}")
async def delete_briefing_topic(topic_name: str, _=Depends(require_auth)):
    """Remove a topic."""
    bt = _briefing_tools()
    result = bt.remove_topic(topic_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
    return result


# ── Background shared-article processor ──────────────────────────────────────


async def _resume_shared_queue_if_needed():
    """On startup, check if there are unprocessed shared articles and spawn processor."""
    await asyncio.sleep(30)  # let the server finish warming up first
    try:
        queue_file = os.path.join(os.path.dirname(_BRIEFING_FUNCTIONS_DIR), "working_files", "shared_queue.json")
        if not os.path.exists(queue_file):
            return
        with open(queue_file, "r") as f:
            queue = json.load(f)
        unprocessed = [e for e in queue if not e.get("processed")]
        if not unprocessed:
            return
        _logger.info("Found %d unprocessed shared articles on startup — spawning processor", len(unprocessed))
        _spawn_shared_article_processor()
    except Exception:
        _logger.exception("Failed to check shared queue on startup")


_SHARED_ARTICLE_PROCESSOR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                 "..", "skills", "daily_briefing", "functions", "process_shared_articles.py")
)


def _spawn_shared_article_processor():
    """Spawn the article processor as a fully detached subprocess.

    Uses a file lock internally, so it's safe to call multiple times —
    duplicate spawns exit immediately. The subprocess survives server restarts.
    """
    import subprocess
    python = sys.executable
    log_dir = os.path.join(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient" / "vessence-data")), "logs", "System_log")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        log_dir = "/tmp"
    log_path = os.path.join(log_dir, "shared_article_processor.log")
    try:
        log_fd = open(log_path, "a")
        proc = subprocess.Popen(
            [python, _SHARED_ARTICLE_PROCESSOR],
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # fully detached from server process
        )
        log_fd.close()
        _logger.info("Spawned detached article processor (pid=%d, log=%s)", proc.pid, log_path)
    except Exception:
        _logger.exception("Failed to spawn article processor")


@app.post("/api/briefing/articles/submit")
async def submit_briefing_article(request: Request, _=Depends(require_auth)):
    body = await request.json()
    url, title, text, save_category = briefing_submit_values(body)
    if not url or not is_http_url(url):
        raise HTTPException(status_code=400, detail="A valid URL starting with http(s):// is required")
    bt = _briefing_tools()
    result = bt.submit_article(url, title=title, text=text, save_category=save_category)

    # Spawn detached processor subprocess — survives server restarts.
    # The processor uses a file lock so only one instance runs at a time.
    _spawn_shared_article_processor()

    return result


@app.post("/api/briefing/articles/summarize_now")
async def summarize_article_now(request: Request, _=Depends(require_auth)):
    """Fetch a URL and return a comprehensive summary synchronously for immediate TTS on the client.

    Returns {"status": "ok", "title": "...", "summary": "..."} or {"status": "error", "message": "..."}.
    """
    body = await request.json()
    url = briefing_url_value(body)
    if not url or not is_http_url(url):
        raise HTTPException(status_code=400, detail="A valid URL starting with http(s):// is required")

    # Keep the original shared URL in the server log.  Unlike queued articles,
    # this synchronous path does not persist an article record, so request logs
    # are the only way to identify a page that later proves unextractable.
    _logger.info("Immediate shared-article summary requested url=%s", url)

    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)

    try:
        from news_fetcher import extract_article, summarize_full
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Briefing module unavailable: {e}")

    try:
        extracted = await asyncio.get_event_loop().run_in_executor(
            None, lambda: extract_article(url)
        )
    except Exception as e:
        _logger.exception("Immediate shared-article extraction failed url=%s", url)
        raise HTTPException(status_code=502, detail=f"Failed to fetch article: {e}")

    title = extracted.get("title") or ""
    text = extracted.get("text") or ""

    if not text and not title:
        _logger.warning(
            "Immediate shared-article extraction returned no content "
            "url=%s blocked=%s source_type=%s",
            url,
            bool(extracted.get("blocked")),
            extracted.get("source_type") or "unknown",
        )
        raise HTTPException(status_code=422, detail="Could not extract article content from that URL")

    _logger.info(
        "Immediate shared-article extraction succeeded url=%s blocked=%s "
        "source_type=%s title_chars=%d text_chars=%d",
        url,
        bool(extracted.get("blocked")),
        extracted.get("source_type") or "unknown",
        len(title),
        len(text),
    )

    if extracted.get("source_type") == "x_post":
        summary = text
    elif text:
        summary = await asyncio.get_event_loop().run_in_executor(
            None, lambda: summarize_full(title, text)
        )
    else:
        summary = title

    return {"status": "ok", "title": title, "summary": summary}


@app.post("/api/briefing/articles/summarize_text")
async def summarize_article_text(request: Request, _=Depends(require_auth)):
    """Accept pre-extracted article text from the Android WebView and return an LLM summary.

    Body: {"title": "...", "text": "...", "url": "..."}
    Returns: {"status": "ok", "title": "...", "summary": "..."}
    """
    body = await request.json()
    title, text = briefing_text_summary_values(body)

    if not text:
        raise HTTPException(status_code=400, detail="Article text is required")

    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)

    try:
        from news_fetcher import summarize_full
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Briefing module unavailable: {e}")

    summary = await asyncio.get_event_loop().run_in_executor(
        None, lambda: summarize_full(title or "Untitled", text)
    )

    return {"status": "ok", "title": title, "summary": summary}


# ── Canonical docs ────────────────────────────────────────────────────────────
# Single source of truth for the "System Architecture" screen in the Android
# app (and anywhere else that needs human-readable docs). The files live in
# VESSENCE_HOME/configs/ and are updated whenever Jane's behaviour changes —
# see CLAUDE.md "Update Rules". The whitelist keeps the endpoint scoped so
# arbitrary files under configs/ cannot be leaked.

@app.get("/api/docs")
async def list_canonical_docs(_=Depends(require_auth)):
    """List the canonical docs the Android app can pull.

    Response: {"docs": [{"slug", "title", "bytes", "last_modified"}, ...]}

    Metadata only — Android compares the returned ``last_modified`` per
    slug against its cached body's ``last_modified`` to decide whether
    to refetch. Cheap (stat only), independent of file size.
    """
    docs = []
    for slug in _DOCS_WHITELIST:
        d = _read_doc_meta(slug, logger=_logger)
        if d is None:
            continue
        docs.append(d)
    return {"docs": docs}


@app.get("/api/docs/{slug}")
async def get_canonical_doc(slug: str, _=Depends(require_auth)):
    """Return the markdown body of one whitelisted canonical doc.

    Response: {"slug", "title", "file", "content", "last_modified", "bytes"}
    """
    d = _read_doc_body(slug, logger=_logger)
    if d is None:
        raise HTTPException(status_code=404, detail=f"Unknown or missing doc: {slug}")
    return d


# ── Web automation ────────────────────────────────────────────────────────────
# Runs a pre-planned sequence of browser actions via
# agent_skills.web_automation. Called from Jane (via the web.run_plan
# CLIENT_TOOL marker) and exposed here as REST for direct testing + Phase 2
# workflow replay. See configs/project_specs/web_automation_skill.md.

@app.post("/api/web_automation/plan")
async def web_automation_plan(request: Request, _=Depends(require_auth)):
    """Execute a scripted browser plan end-to-end in one session.

    Request JSON::
        {
          "steps": [
            {"action": "navigate", "args": {"url": "https://example.com"}},
            {"action": "snapshot", "args": {}},
            {"action": "extract",  "args": {}}
          ],
          "label": "adhoc",
          "headless": true,
          "record_trace": false
        }

    Response::
        {"ok": true, "run_id": "run_...", "summary": "...", "data": {...}}

    Phase 1 limitations: no workflow persistence, no profiles (each call
    gets a fresh BrowserContext), no iterative LLM-in-the-loop. Opus
    precomputes the plan and the server runs it.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    try:
        raw_steps = web_plan_raw_steps(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from agent_skills.web_automation.skill import TaskStep, run_task
        from agent_skills.web_automation.browser_session import SessionOptions
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Web automation module unavailable: {e}",
        )

    try:
        step_specs = web_plan_step_specs(raw_steps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    steps = [TaskStep(**spec) for spec in step_specs]

    label = web_plan_label(body)
    profile_id = web_plan_profile_id(body)
    storage_state = None
    if profile_id:
        try:
            from agent_skills.web_automation import profiles as _profiles
            storage_state = web_plan_storage_state_path(profile_id, steps, _profiles)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Profile load failed: {e}")
    opts = SessionOptions(
        headless=web_plan_headless(body),
        record_trace=web_plan_record_trace(body),
        storage_state_path=storage_state,
    )

    result = await run_task(steps, label=label, options=opts)
    return automation_result_payload(result)


# Profile management — named persistent browser auth contexts (spec 9.5).

@app.get("/api/web_automation/profiles")
async def list_web_profiles(_=Depends(require_auth)):
    from agent_skills.web_automation import profiles as _profiles
    return {"profiles": [p.to_dict() for p in _profiles.list_profiles()]}


@app.post("/api/web_automation/profiles")
async def create_web_profile(request: Request, _=Depends(require_auth)):
    body = await request.json()
    name, domain = web_profile_create_values(body)
    if not name or not domain:
        raise HTTPException(
            status_code=400,
            detail="'display_name' and 'domain' are required",
        )
    from agent_skills.web_automation import profiles as _profiles
    meta = _profiles.create(name, domain)
    return meta.to_dict()


@app.delete("/api/web_automation/profiles/{profile_id}")
async def delete_web_profile(profile_id: str, _=Depends(require_auth)):
    from agent_skills.web_automation import profiles as _profiles
    try:
        _profiles.delete(profile_id)
    except _profiles.ProfileNotFound:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
    return {"ok": True}


@app.post("/api/web_automation/profiles/{profile_id}/capture")
async def capture_web_profile(profile_id: str, request: Request, _=Depends(require_auth)):
    """Open a VISIBLE browser to ``login_url``, wait for the user to
    reach ``success_url_pattern``, then save the storage_state.

    Request::
        {
          "login_url": "https://citywater.com/login",
          "success_url_pattern": "citywater.com/(dashboard|account)",
          "timeout_s": 300
        }
    """
    body = await request.json()
    login_url, success_pat, timeout_s = web_profile_capture_values(body)
    if not login_url or not success_pat:
        raise HTTPException(
            status_code=400,
            detail="'login_url' and 'success_url_pattern' required",
        )
    try:
        from agent_skills.web_automation import profiles as _profiles
        from agent_skills.web_automation.browser_session import (
            BrowserSessionManager, SessionOptions,
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))

    _profiles.bind_check(profile_id, login_url)

    import re as _re
    pat = _re.compile(success_pat)
    mgr = BrowserSessionManager.instance()
    opts = SessionOptions(headless=False)  # user needs to see the login page
    async with mgr.session(run_id=f"capture_{profile_id}", options=opts) as sess:
        page = sess.page
        await page.goto(login_url)
        try:
            await page.wait_for_url(pat, timeout=timeout_s * 1000)
        except Exception as e:
            raise HTTPException(status_code=408, detail=f"Login not completed in time: {e}")
        await _profiles.capture_after_login(page, profile_id)
    return {"ok": True, "profile_id": profile_id}


# Secret management — encrypted credential store with domain binding.

@app.get("/api/web_automation/secrets")
async def list_web_secrets(_=Depends(require_auth)):
    from agent_skills.web_automation import secrets as _secrets
    return {"secrets": [web_secret_public_entry(e) for e in _secrets.list_secrets()]}


@app.post("/api/web_automation/secrets")
async def create_web_secret(request: Request, _=Depends(require_auth)):
    body = await request.json()
    domain, label, username, password, notes = web_secret_create_values(body)
    if not domain or not label or not password:
        raise HTTPException(
            status_code=400,
            detail="'domain', 'label', and 'password' are required",
        )
    from agent_skills.web_automation import secrets as _secrets
    sid = _secrets.create(domain, label, username, password, notes)
    return {"secret_id": sid, "domain": domain, "label": label}


@app.delete("/api/web_automation/secrets/{secret_id}")
async def delete_web_secret(secret_id: str, _=Depends(require_auth)):
    from agent_skills.web_automation import secrets as _secrets
    try:
        _secrets.delete(secret_id)
    except _secrets.SecretNotFound:
        raise HTTPException(status_code=404, detail=f"Secret not found: {secret_id}")
    return {"ok": True}


# Workflows — save / load / replay named browser plans (Phase 3).

@app.get("/api/web_automation/workflows")
async def list_web_workflows(_=Depends(require_auth)):
    from agent_skills.web_automation import workflow as _wf
    return {"workflows": [s.__dict__ for s in _wf.list_workflows()]}


@app.post("/api/web_automation/workflows")
async def save_web_workflow(request: Request, _=Depends(require_auth)):
    body = await request.json()
    try:
        from agent_skills.web_automation import workflow as _wf
        wid = _wf.save(
            name=body.get("name", ""),
            description=body.get("description", ""),
            steps=body.get("steps", []),
            allowed_domains=body.get("allowed_domains"),
            browser_profile_id=body.get("browser_profile_id"),
            inputs_schema=body.get("inputs_schema"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"workflow_id": wid}


@app.get("/api/web_automation/workflows/{name_or_id}")
async def get_web_workflow(name_or_id: str, _=Depends(require_auth)):
    from agent_skills.web_automation import workflow as _wf
    try:
        return _wf.load(name_or_id)
    except _wf.WorkflowNotFound:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {name_or_id}")


@app.delete("/api/web_automation/workflows/{name_or_id}")
async def delete_web_workflow(name_or_id: str, _=Depends(require_auth)):
    from agent_skills.web_automation import workflow as _wf
    try:
        _wf.delete(name_or_id)
    except _wf.WorkflowNotFound:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {name_or_id}")
    return {"ok": True}


@app.post("/api/web_automation/workflows/{name_or_id}/run")
async def run_web_workflow(name_or_id: str, _=Depends(require_auth)):
    from agent_skills.web_automation import workflow as _wf
    try:
        result = await _wf.run(name_or_id)
    except _wf.WorkflowNotFound:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {name_or_id}")
    return automation_result_payload(result)


@app.post("/api/briefing/processor-status")
async def briefing_processor_status(request: Request):
    """Callback from the detached article processor after each article."""
    client_ip = _client_ip(request) if hasattr(request, 'headers') else ""
    if not _is_local_control_ip(client_ip, allow_unknown=True):
        return JSONResponse({"error": "localhost only"}, status_code=403)
    body = await request.json()
    aid = body.get("article_id", "?")
    remaining = body.get("remaining", 0)
    drained = body.get("queue_drained", False)
    if drained:
        _logger.info("Article processor finished — queue drained (last article: %s)", aid)
    else:
        _logger.info("Article processor update: %s done, %d remaining", aid, remaining)
    return {"status": "ok"}


@app.post("/api/briefing/fetch")
async def trigger_briefing_fetch(_=Depends(require_auth)):
    """Manually trigger a briefing fetch."""
    bt = _briefing_tools()
    result = bt.fetch_and_summarize_all()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Fetch failed"))
    # Apply the same variety/cap trim that the nightly cron uses so manual
    # fetches can't reintroduce list bloat.
    try:
        if _BRIEFING_FUNCTIONS_DIR not in sys.path:
            sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
        from run_briefing import _trim_to_cap, MAX_TOTAL_ARTICLES
        result["trim"] = _trim_to_cap(MAX_TOTAL_ARTICLES)
    except Exception as exc:
        _logger.warning("Manual briefing trim skipped: %s", exc)
    return result


@app.post("/api/briefing/article/{article_id}/dismiss")
async def dismiss_briefing_article(article_id: str, _=Depends(require_auth)):
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    """Mark an article as dismissed ('heard it')."""
    bt = _briefing_tools()
    return bt.dismiss_article(article_id)


@app.delete("/api/briefing/article/{article_id}/dismiss")
async def undismiss_briefing_article(article_id: str, _=Depends(require_auth)):
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    """Un-dismiss an article."""
    bt = _briefing_tools()
    return bt.undismiss_article(article_id)


_SAVED_ARTICLES_DIR = Path(os.path.expanduser("~/ambient/vessence-data/briefing_saved"))
_VAULT_SAVED_ARTICLES = Path(os.path.expanduser("~/ambient/vault/saved_articles"))


@app.post("/api/briefing/saved")
async def save_briefing_article(request: Request, _=Depends(require_auth)):
    """Save an article permanently to a category. Saved articles are never auto-deleted."""
    body = await request.json()
    article_id = body.get("article_id")
    category = body.get("category", "Uncategorized")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id required")

    _SAVED_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    saved_file = saved_articles_index_path(_SAVED_ARTICLES_DIR)

    saved = {}
    if saved_file.exists():
        async with aiofiles.open(saved_file, "r") as f:
            saved = json.loads(await f.read())

    # Find article data from current briefing articles cache
    article_data = None
    tools_dir = os.environ.get("TOOLS_DIR", os.path.join(os.path.expanduser("~"), "ambient", "skills"))
    article_file = daily_briefing_article_path(tools_dir, article_id)
    if article_file.exists():
        async with aiofiles.open(article_file, "r") as f:
            article_data = json.loads(await f.read())

    # Store: keyed by article_id, includes category and saved timestamp
    saved[article_id] = saved_article_record(
        article_id,
        category,
        datetime.now(timezone.utc).isoformat(),
        article_data,
    )

    async with aiofiles.open(saved_file, "w") as f:
        await f.write(json.dumps(saved, indent=2))

    # Also save to vault as file: vault/saved_articles/<group>/<article_id>.json
    vault_article_file = vault_saved_article_path(_VAULT_SAVED_ARTICLES, category, article_id)
    vault_group_dir = vault_article_file.parent
    vault_group_dir.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(vault_article_file, "w") as f:
        await f.write(json.dumps(saved[article_id], indent=2))
    _logger.info("Saved article %s to vault group '%s'", article_id, category)

    return {"status": "ok", "article_id": article_id, "category": category}


@app.get("/api/briefing/saved/categories")
async def list_saved_categories(_=Depends(require_auth)):
    """List all categories that have saved articles (from vault folders)."""
    cats = []
    # Scan vault folders — these are the source of truth for group names
    if _VAULT_SAVED_ARTICLES.exists():
        for d in _VAULT_SAVED_ARTICLES.iterdir():
            if d.is_dir() and any(d.glob("*.json")):
                cats.append(d.name)
    # Also check JSON index for anything not yet in vault
    saved_file = saved_articles_index_path(_SAVED_ARTICLES_DIR)
    saved = {}
    if saved_file.exists():
        async with aiofiles.open(saved_file, "r") as f:
            saved = json.loads(await f.read())
    return {"categories": saved_category_names(cats, saved)}


@app.get("/api/briefing/saved")
async def list_saved_articles(category: str = None, _=Depends(require_auth)):
    """List saved articles, optionally filtered by category."""
    saved_file = saved_articles_index_path(_SAVED_ARTICLES_DIR)
    if not saved_file.exists():
        return {"articles": []}
    async with aiofiles.open(saved_file, "r") as f:
        saved = json.loads(await f.read())
    return {"articles": saved_article_list(saved, category)}


@app.delete("/api/briefing/saved/{article_id}")
async def unsave_briefing_article(article_id: str, _=Depends(require_auth)):
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    """Remove an article from saved collection."""
    saved_file = saved_articles_index_path(_SAVED_ARTICLES_DIR)
    if not saved_file.exists():
        raise HTTPException(status_code=404, detail="No saved articles")
    async with aiofiles.open(saved_file, "r") as f:
        saved = json.loads(await f.read())
    if article_id not in saved:
        raise HTTPException(status_code=404, detail="Article not saved")
    category = saved[article_id].get("category", "")
    del saved[article_id]
    async with aiofiles.open(saved_file, "w") as f:
        await f.write(json.dumps(saved, indent=2))
    # Remove from vault too
    if category:
        vault_file = vault_saved_article_path(_VAULT_SAVED_ARTICLES, category, article_id)
        if vault_file.exists():
            vault_file.unlink()
            # Remove empty group folder
            vault_group = vault_file.parent
            if vault_group.exists() and not any(vault_group.iterdir()):
                vault_group.rmdir()
    return {"status": "ok", "article_id": article_id}


@app.get("/api/briefing/search")
async def search_briefing_articles(q: str, _=Depends(require_auth)):
    """Search past articles via ChromaDB."""
    if _BRIEFING_FUNCTIONS_DIR not in sys.path:
        sys.path.insert(0, _BRIEFING_FUNCTIONS_DIR)
    from article_indexer import search_articles
    results = search_articles(q, n_results=10)
    return {"status": "ok", "results": results, "count": len(results)}


@app.get("/api/briefing/image/{article_id}")
async def get_briefing_image(article_id: str):
    """Serve a cached article image."""
    if not is_briefing_identifier(article_id):
        raise HTTPException(status_code=400, detail="Invalid article_id")
    tools_dir = os.environ.get("TOOLS_DIR", os.path.join(os.path.expanduser("~"), "ambient", "skills"))
    images_dir = daily_briefing_image_dir(tools_dir)
    # Try common extensions
    for img_path in briefing_image_candidates(images_dir, article_id):
        if img_path.exists():
            return FileResponse(str(img_path))
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/briefing/archive")
async def list_briefing_archive(_=Depends(require_auth)):
    """List available archived briefing dates."""
    archive_dir = Path(os.path.expanduser("~/ambient/vessence-data/briefings"))
    if not archive_dir.exists():
        return {"status": "ok", "dates": []}
    files = sorted(archive_dir.glob("*.json"), key=lambda f: f.name, reverse=True)
    dates = [f.stem for f in files]
    return {"status": "ok", "dates": dates}


@app.get("/api/briefing/archive/{date}")
async def get_archived_briefing(date: str, _=Depends(require_auth)):
    """Get a specific archived briefing by date."""
    if not is_archive_date(date):
        raise HTTPException(status_code=400, detail="Invalid date format")
    archive_dir = Path(os.path.expanduser("~/ambient/vessence-data/briefings"))
    file_path = briefing_archive_path(archive_dir, date)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archive not found")

    async with aiofiles.open(file_path, "r") as f:
        data = json.loads(await f.read())
    return data


# ─── Facebook Marketplace Routes ─────────────────────────────────────────────
#
# Saved searches live in vessence-data/config/marketplace_searches.json and
# harvested listings in vessence-data/data/facebook_marketplace_finds/<name>/.
# The harvester (agent_skills.marketplace.harvester) is intended to run via
# cron; these endpoints are read-mostly so the UI stays fast.


def _mk_mods():
    from agent_skills.marketplace import config as mk_config
    from agent_skills.marketplace import harvester as mk_harvester
    return mk_config, mk_harvester


def _mk_summarize():
    from agent_skills.marketplace import summarize as mk_summarize
    return mk_summarize


def _mk_refresh():
    from agent_skills.marketplace import refresh as mk_refresh
    return mk_refresh


def _ensure_safe_mk_name(name: str) -> None:
    if not is_safe_marketplace_name(name):
        raise HTTPException(status_code=400, detail="invalid search name")


@app.get("/api/marketplace/searches")
async def marketplace_searches(_=Depends(require_auth)):
    """List all saved Marketplace searches (with per-search passed_count)."""
    cfg, harv = _mk_mods()
    out = []
    for s in cfg.list_searches():
        summary = harv.listings_for(s["name"])
        out.append({
            "name": s["name"],
            "label": s.get("label", s["name"]),
            "queries": s.get("queries", []),
            "filters": s.get("filters", {}),
            "location_id": s.get("location_id"),
            "created": s.get("created"),
            "updated": s.get("updated"),
            "last_refreshed": summary.get("last_refreshed"),
            "passed_count": summary.get("passed_count", 0),
        })
    return JSONResponse({"searches": out})


@app.post("/api/marketplace/searches")
async def marketplace_create_search(request: Request, _=Depends(require_auth)):
    body = await request.json()
    cfg, _h = _mk_mods()
    payload = marketplace_create_search_payload(body, cfg.DEFAULT_LOCATION_ID)
    name = payload["name"]
    _ensure_safe_mk_name(name)
    if not payload["raw_queries_valid"]:
        raise HTTPException(status_code=400, detail="queries required")
    try:
        saved = cfg.save_search(
            name,
            label=payload["label"],
            queries=payload["queries"],
            filters=payload["filters"],
            location_id=payload["location_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"name": name, **saved})


@app.get("/api/marketplace/search/{name}")
async def marketplace_get_search(name: str, _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    cfg, harv = _mk_mods()
    search = cfg.get_search(name)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    summary = harv.listings_for(name)
    return JSONResponse({
        "name": name,
        "label": search.get("label", name),
        "queries": search.get("queries", []),
        "filters": search.get("filters", {}),
        "last_refreshed": summary.get("last_refreshed"),
        "passed_count": summary.get("passed_count", 0),
        "listings": summary.get("listings", []),
    })


@app.delete("/api/marketplace/search/{name}")
async def marketplace_delete_search(name: str, _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    cfg, _h = _mk_mods()
    if not cfg.delete_search(name):
        raise HTTPException(status_code=404, detail="search not found")
    return JSONResponse({"deleted": name})


@app.get("/api/marketplace/listing/{name}/{slug}/{listing_id}")
async def marketplace_listing_detail(name: str, slug: str, listing_id: str,
                                     _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    if not is_safe_listing_key(slug, listing_id):
        raise HTTPException(status_code=400, detail="invalid slug or id")
    _cfg, harv = _mk_mods()
    d = harv.listing_detail(name, slug, listing_id)
    if d is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return JSONResponse(d)


@app.get("/api/marketplace/summary/{name}")
async def marketplace_get_summary(name: str, _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    s = _mk_summarize().get_summary(name)
    if s is None:
        return JSONResponse({"search": name, "summary": None,
                             "generated_at": None})
    return JSONResponse(s)


@app.get("/api/marketplace/refresh/{name}")
async def marketplace_refresh_status(name: str, _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    return JSONResponse(_mk_refresh().get_status(name))


@app.post("/api/marketplace/refresh/{name}")
async def marketplace_refresh_now(name: str, _=Depends(require_auth)):
    """Kick off harvester+summarizer in the background. Returns immediately.

    The client should poll GET /api/marketplace/refresh/{name} until
    ``state`` goes back to ``idle`` (or ``error``).
    """
    _ensure_safe_mk_name(name)
    cfg, _h = _mk_mods()
    if cfg.get_search(name) is None:
        raise HTTPException(status_code=404, detail="search not found")
    r = _mk_refresh()
    current = r.get_status(name)
    if current.get("state") == "running":
        return JSONResponse({"state": "already_running", **current})

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    log_path = marketplace_refresh_log_path(data_home, name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = marketplace_refresh_env(os.environ)
    logf = open(log_path, "a")
    logf.write(marketplace_refresh_log_header(name, datetime.now()))
    logf.flush()
    subprocess.Popen(
        marketplace_refresh_command(python_bin, name),
        cwd=cwd, env=env, stdout=logf, stderr=logf,
        start_new_session=True,
    )
    return JSONResponse({"state": "started", "search": name})


@app.get("/marketplace-image/{name}/{slug}/{listing_id}/{photo_name}")
async def marketplace_image(name: str, slug: str, listing_id: str,
                            photo_name: str, _=Depends(require_auth)):
    _ensure_safe_mk_name(name)
    if not is_safe_listing_key(slug, listing_id):
        raise HTTPException(status_code=400, detail="invalid slug or id")
    if not is_safe_photo_name(photo_name):
        raise HTTPException(status_code=400, detail="invalid photo name")
    _cfg, harv = _mk_mods()
    p = harv.photo_path(name, slug, listing_id, photo_name)
    if p is None:
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(str(p))


# ─── Tax Accountant 2025 Routes ──────────────────────────────────────────────

_TAX_ESSENCE_DIR = os.path.join(os.path.expanduser("~/ambient/essences"), "tax_accountant_2025")
_TAX_FUNCTIONS_DIR = os.path.join(_TAX_ESSENCE_DIR, "functions")

def _run_tax_tool(tool_name: str, args: dict = None) -> dict:
    """Run a tax accountant tool and return the result."""
    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    tools_path = os.path.join(_TAX_FUNCTIONS_DIR, "custom_tools.py")
    cmd = tax_tool_command(python_bin, tools_path, tool_name, args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                            cwd=_TAX_FUNCTIONS_DIR)
    return tax_tool_result_payload(result.returncode, result.stdout, result.stderr)


@app.get("/tax-accountant")
async def tax_accountant_page(request: Request, _=Depends(require_auth)):
    """Redirect to Jane's chat with the tax accountant essence activated."""
    return RedirectResponse(url="/?essence=tax_accountant_2025", status_code=302)


@app.post("/api/tax/interview/start")
async def tax_interview_start(_=Depends(require_auth)):
    """Start or restart the tax interview."""
    return JSONResponse(_run_tax_tool("interview_step", {"step_id": "filing_status"}))


@app.post("/api/tax/interview/answer")
async def tax_interview_answer(request: Request, _=Depends(require_auth)):
    """Submit an answer to the current interview step."""
    body = await request.json()
    return JSONResponse(_run_tax_tool("interview_step", tax_interview_answer_args(body)))


@app.get("/api/tax/interview/state")
async def tax_interview_state(_=Depends(require_auth)):
    """Get the current interview state."""
    return JSONResponse(_run_tax_tool("get_interview_state"))


@app.post("/api/tax/calculate")
async def tax_calculate(_=Depends(require_auth)):
    """Run the full tax calculation."""
    return JSONResponse(_run_tax_tool("calculate_tax"))


@app.get("/api/tax/forms/{form_name}")
async def tax_get_form(form_name: str, _=Depends(require_auth)):
    """Get a generated tax form."""
    if not is_safe_tax_form_name(form_name):
        raise HTTPException(status_code=400, detail="Invalid form name")
    output_dir = tax_output_dir(_TAX_ESSENCE_DIR)
    # Find the most recent file matching form_name
    match = latest_tax_form_file(output_dir, form_name)
    if match:
        file_path, filename = match
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail=f"Form '{form_name}' not found")


@app.get("/api/tax/summary")
async def tax_summary(_=Depends(require_auth)):
    """Get the most recent tax calculation summary."""
    result_path = tax_result_path(_TAX_ESSENCE_DIR)
    if not os.path.exists(result_path):
        return JSONResponse({"status": "error", "message": "No calculation found. Run calculate first."})
    with open(result_path) as f:
        return JSONResponse(json.load(f))


@app.post("/api/tax/upload")
async def tax_upload_document(file: UploadFile = File(...), doc_type: str = Form(""), _=Depends(require_auth)):
    """Upload a tax document for processing."""
    uploads_dir = tax_uploads_dir(_TAX_ESSENCE_DIR)
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = tax_upload_path(uploads_dir, file.filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return JSONResponse(_run_tax_tool("upload_document", tax_upload_document_args(file_path, doc_type)))


@app.post("/api/tax/reset")
async def tax_reset(_=Depends(require_auth)):
    """Reset the tax interview."""
    return JSONResponse(_run_tax_tool("reset_interview"))


@app.get("/api/tax/checklist")
async def tax_checklist(_=Depends(require_auth)):
    """Get the document checklist."""
    return JSONResponse(_run_tax_tool("get_document_checklist"))


@app.post("/api/tax/generate")
async def tax_generate_forms(_=Depends(require_auth)):
    """Generate all tax forms."""
    return JSONResponse(_run_tax_tool("generate_forms"))


@app.get("/api/tax/knowledge/search")
async def tax_knowledge_search(q: str = "", _=Depends(require_auth)):
    """Search the tax knowledge base."""
    if not q:
        return JSONResponse({"status": "error", "message": "Query parameter 'q' required"})
    try:
        chroma_path = os.path.join(_TAX_ESSENCE_DIR, "knowledge", "chromadb")
        chroma_client = get_chroma_client(chroma_path)
        coll = chroma_client.get_collection("tax_knowledge_2025")
        results = coll.query(query_texts=[q], n_results=5)
        return JSONResponse({
            "status": "ok",
            "results": [
                {
                    "content": doc,
                    "metadata": meta,
                    "distance": dist
                }
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )
            ]
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


# ── CLI Login (runs inside Jane container where CLI is installed) ─────────────

import select as _select

_cli_login_process = None
_cli_login_authenticated = False
_cli_login_transcript_path: str | None = None
_cli_login_provider: str | None = None
_cli_login_local_port: int | None = None
_cli_login_oauth_state: str | None = None
_cli_login_pty_master_fd: int | None = None
# Self-managed OAuth (bypasses CLI's broken Docker auth)
_claude_oauth_verifier: str | None = None
_claude_oauth_state: str | None = None
_gemini_oauth_verifier: str | None = None
_gemini_oauth_state: str | None = None

_auth_status_cache: dict[str, tuple[float, dict]] = {}


_claude_refresh_last_failure: float = 0.0  # timestamp of last failed refresh
_CLAUDE_REFRESH_COOLDOWN = 300  # seconds (5 minutes) before retrying after failure


def _attempt_claude_token_refresh() -> bool:
    """Attempt to refresh the Claude OAuth token using the refresh token. Sync version."""
    global _claude_refresh_last_failure

    # Cooldown: don't retry if we failed recently
    if _claude_refresh_last_failure and (time.time() - _claude_refresh_last_failure) < _CLAUDE_REFRESH_COOLDOWN:
        return False

    creds_path = _cli_credentials_path("claude")
    if not creds_path.exists():
        return False

    try:
        creds = json.loads(creds_path.read_text())
        refresh_token = _claude_refresh_token_from_credentials(creds)
        if not refresh_token:
            return False

        # Token exchange with backoff
        import urllib.request as _urllib_req
        token_url, token_data, token_headers = _claude_oauth_refresh_request_spec(refresh_token)

        for attempt in range(3):
            try:
                token_req = _urllib_req.Request(
                    token_url,
                    data=token_data,
                    headers=token_headers,
                )
                token_resp = _urllib_req.urlopen(token_req, timeout=15)
                tokens = json.loads(token_resp.read())

                # Update credentials
                _apply_claude_refresh_tokens(
                    creds,
                    tokens,
                    previous_refresh_token=refresh_token,
                    now_ms=int(time.time() * 1000),
                )
                creds_path.write_text(json.dumps(creds), encoding="utf-8")
                return True
            except Exception as exc:
                if hasattr(exc, "code") and exc.code == 429:
                    # Exponential backoff
                    wait_time = 2 ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                break
    except Exception:
        pass

    _claude_refresh_last_failure = time.time()
    return False


def _provider_auth_status_details(provider: str) -> dict:
    return _provider_auth_status_details_impl(
        provider,
        cache=_auth_status_cache,
        now_fn=time.time,
        run_command_fn=lambda cmd: subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        ),
        attempt_refresh_fn=_attempt_claude_token_refresh,
    )


def _provider_auth_status(provider: str) -> bool:
    return bool(_provider_auth_status_details(provider).get("logged_in"))


def _cli_login_debug_snapshot(provider: str) -> dict:
    transcript_lines = _read_cli_transcript_lines(_cli_login_transcript_path)
    return _cli_login_debug_payload(
        provider=provider,
        process=_cli_login_process,
        authenticated=_cli_login_authenticated,
        transcript_lines=transcript_lines,
        auth_status=_provider_auth_status_details(provider),
    )


def _terminate_cli_login_process() -> None:
    global _cli_login_process, _cli_login_transcript_path, _cli_login_provider
    global _cli_login_local_port, _cli_login_oauth_state, _cli_login_pty_master_fd
    if _cli_login_process and _cli_login_process.poll() is None:
        _cli_login_process.kill()
        try:
            _cli_login_process.wait(timeout=5)
        except Exception:
            pass
    if _cli_login_pty_master_fd is not None:
        try:
            os.close(_cli_login_pty_master_fd)
        except OSError:
            pass
    _cli_login_process = None
    _cli_login_transcript_path = None
    _cli_login_provider = None
    _cli_login_local_port = None
    _cli_login_oauth_state = None
    _cli_login_pty_master_fd = None


def _discover_cli_login_port() -> int | None:
    """Find the port Claude CLI's local OAuth callback server is listening on.

    Strategy: parse /proc/net/tcp for all TCP LISTEN sockets on 127.0.0.1,
    exclude known service ports, and return the remaining one.  In a Docker
    container the process list is small, so this is reliable.  Falls back to
    PID-based matching via /proc/<pid>/fd, then ss(8).
    """
    if not _cli_login_process or _cli_login_process.poll() is not None:
        return None

    # Known ports to ignore (our own services)
    KNOWN_PORTS = _CLI_LOGIN_IGNORED_PORTS

    # --- Method 1: Scan /proc/net/tcp AND /proc/net/tcp6 for LISTEN sockets ---
    # Claude CLI (Node.js) may bind on IPv6 ::1 instead of IPv4 127.0.0.1,
    # especially inside Docker containers.  Check both.
    try:
        candidate_ports, inode_to_port = _proc_net_listen_socket_candidates(
            ("/proc/net/tcp", "/proc/net/tcp6"),
            known_ports=KNOWN_PORTS,
        )

        # If there's exactly one unknown listening port, that's our target.
        # If multiple, try PID-based filtering below.
        if len(candidate_ports) == 1:
            return candidate_ports[0]

        # Multiple candidates — try to narrow via PID fd matching
        if candidate_ports:
            # Walk process tree from our PID
            process_port = _process_tree_socket_port(_cli_login_process.pid, inode_to_port)
            if process_port is not None:
                return process_port

            # Still multiple candidates — return the highest port (most likely
            # to be the ephemeral one Claude picked)
            return max(candidate_ports)
    except Exception:
        pass

    # --- Method 2: Fallback to ss (not available in all Docker images) ---
    try:
        result = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=5,
        )
        port = _ss_login_callback_port(result.stdout.splitlines(), known_ports=KNOWN_PORTS)
        if port is not None:
            return port
    except Exception:
        pass

    return None


def _attempt_claude_login_via_transcript(cmd: list[str]) -> tuple[str | None, list[str]]:
    """Start Claude CLI login using a PTY so the Ink TUI works.

    Uses pty.openpty() to give the CLI a real terminal, which is required
    for the interactive 'Paste code here' prompt.  The PTY master fd is
    stored in _cli_login_pty_master_fd so _submit_code_via_pty() can
    write the auth code later.
    """
    global _cli_login_process, _cli_login_transcript_path, _cli_login_pty_master_fd
    import pty as _pty
    import select as _select_mod

    # Create a PTY pair
    master_fd, slave_fd = _pty.openpty()
    _cli_login_pty_master_fd = master_fd

    # Also keep a transcript file for debug
    transcript_dir = tempfile.mkdtemp(prefix="jane-cli-login-")
    transcript_path = Path(transcript_dir) / "claude-auth.log"
    _cli_login_transcript_path = str(transcript_path)

    _cli_login_process = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "200", "LINES": "40"},
    )
    os.close(slave_fd)

    # Read output from the PTY master, looking for the auth URL
    auth_url = None
    raw_output = b""
    output_lines: list[str] = []
    deadline = time.time() + 30

    while time.time() < deadline:
        ready, _, _ = _select_mod.select([master_fd], [], [], 0.5)
        if ready:
            try:
                data = os.read(master_fd, 8192)
                raw_output += data
            except OSError:
                break

        text = _clean_cli_output(raw_output)
        output_lines = _cli_output_lines(text)

        # Write transcript for debugging
        transcript_path.write_text(text, encoding="utf-8")

        auth_url = _extract_claude_auth_url(output_lines)
        if auth_url:
            break
        if _cli_login_process.poll() is not None:
            break

    return auth_url, output_lines


_cli_login_device_code: str | None = None  # For OpenAI device-auth flow

def _attempt_cli_login_command(cmd: list[str]) -> tuple[str | None, list[str]]:
    global _cli_login_process, _cli_login_device_code
    if cmd[0] == "claude":
        return _attempt_claude_login_via_transcript(cmd)

    _cli_login_device_code = None
    _cli_login_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "TERM": "dumb"},
    )

    auth_url = None
    output_lines: list[str] = []
    deadline = time.time() + 30
    while time.time() < deadline:
        if _cli_login_process.poll() is not None:
            break
        ready, _, _ = _select.select([_cli_login_process.stdout], [], [], 1.0)
        if not ready:
            continue
        line = _cli_login_process.stdout.readline()
        if not line:
            break
        auth_url, _cli_login_device_code, stripped = _cli_login_output_update(
            line,
            auth_url=auth_url,
            device_code=_cli_login_device_code,
        )
        if stripped:
            output_lines.append(stripped)
        # Stop once we have both URL and device code (or just URL for non-device flows)
        if auth_url and (_cli_login_device_code or time.time() > deadline - 25):
            # Read a bit more to catch the device code if it comes shortly after
            if not _cli_login_device_code:
                extra_deadline = time.time() + 3
                while time.time() < extra_deadline:
                    ready2, _, _ = _select.select([_cli_login_process.stdout], [], [], 0.5)
                    if ready2:
                        line2 = _cli_login_process.stdout.readline()
                        if line2:
                            auth_url, _cli_login_device_code, stripped2 = _cli_login_output_update(
                                line2,
                                auth_url=auth_url,
                                device_code=_cli_login_device_code,
                            )
                            if stripped2:
                                output_lines.append(stripped2)
                            if _cli_login_device_code:
                                break
            break
    return auth_url, output_lines


@app.post("/api/cli-login")
async def cli_login(request: Request):
    """Start CLI login process and return the auth URL."""
    global _cli_login_process, _cli_login_authenticated, _cli_login_provider
    global _cli_login_local_port, _cli_login_oauth_state
    body = await request.json()
    provider = normalize_frontier_provider(body.get("provider", os.environ.get("JANE_BRAIN", "gemini")))

    # Kill any previous login process
    _terminate_cli_login_process()
    _cli_login_authenticated = False
    _cli_login_provider = provider

    cmd_candidates = _cli_login_candidates(provider)
    if not cmd_candidates:
        return JSONResponse({"error": f"Unknown provider: {provider}"})

    import shutil as _shutil
    cli_bin = _cli_binary_for_provider(provider)
    if not cli_bin or not _shutil.which(cli_bin):
        return JSONResponse({"error": f"CLI '{cli_bin or provider}' is not installed yet. The first-boot installer may still be running — please wait a minute and try again."})

    if _provider_auth_status(provider):
        _cli_login_authenticated = True
        return JSONResponse({"auth_url": None, "already_authenticated": True})

    # --- Claude: self-managed OAuth (no dependency on CLI's callback server) ---
    if provider == "claude":
        global _claude_oauth_verifier, _claude_oauth_state
        _claude_oauth_verifier = _base64url_no_padding(os.urandom(32))
        _claude_oauth_state = _base64url_no_padding(os.urandom(32))
        auth_url = _claude_oauth_authorization_url(
            _pkce_code_challenge(_claude_oauth_verifier),
            _claude_oauth_state,
        )
        return JSONResponse({"auth_url": auth_url})

    # --- Gemini: self-managed Google OAuth ---
    if provider == "gemini":
        global _gemini_oauth_verifier, _gemini_oauth_state
        _gemini_oauth_verifier = _base64url_no_padding(os.urandom(32))
        _gemini_oauth_state = _base64url_no_padding(os.urandom(32))
        auth_url = _gemini_oauth_authorization_url(
            _pkce_code_challenge(_gemini_oauth_verifier),
            _gemini_oauth_state,
        )
        return JSONResponse({"auth_url": auth_url})

    # --- Other providers: use CLI-based login ---
    try:
        last_output_lines: list[str] = []
        for cmd in cmd_candidates:
            auth_url, output_lines = _attempt_cli_login_command(cmd)
            last_output_lines = output_lines
            if auth_url:
                resp_data = {"auth_url": auth_url}
                if _cli_login_device_code:
                    resp_data["device_code"] = _cli_login_device_code
                return JSONResponse(resp_data)
            if _provider_auth_status(provider):
                _cli_login_authenticated = True
                return JSONResponse({"auth_url": None, "already_authenticated": True})
            _terminate_cli_login_process()

        tail = " | ".join(last_output_lines[-3:]) if last_output_lines else "No CLI output captured."
        return JSONResponse({"error": f"Could not get auth URL. Output: {tail}"})
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/api/cli-login/code")
async def cli_login_code(request: Request):
    """Submit a browser-returned auth code to the active CLI login session.

    For Claude: delivers the OAuth code to the CLI's local HTTP callback server
    at /callback?code=<code>&state=<state>.  The CLI uses PKCE and validates
    the state param, then exchanges the code for an auth token.
    """
    global _cli_login_authenticated, _cli_login_local_port
    body = await request.json()
    code = (body.get("code") or "").strip()
    provider = normalize_frontier_provider(body.get("provider") or _cli_login_provider or os.environ.get("JANE_BRAIN", "gemini"))

    if not code:
        return JSONResponse({"ok": False, "error": "Authentication code is required."}, status_code=400)

    # --- Claude: self-managed OAuth token exchange ---
    if provider == "claude":
        if not _claude_oauth_verifier or not _claude_oauth_state:
            return JSONResponse({"ok": False, "error": "No active OAuth session. Click Connect Account again."}, status_code=400)

        import urllib.request as _urllib_req
        creds, status_code, error = _oauth_login_credentials_for_code(
            provider,
            code,
            _claude_oauth_verifier,
            now_ms=int(time.time() * 1000),
            request_factory=_urllib_req.Request,
            urlopen_fn=_urllib_req.urlopen,
        )
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=status_code)

        _write_cli_credentials(provider, creds)

        # Invalidate cache for provider status
        _auth_status_cache.pop(provider, None)

        # Verify auth status
        _cli_login_authenticated = True
        if _provider_auth_status(provider):
            return JSONResponse({"ok": True, "authenticated": True})
        else:
            # Credentials written but status check failed — still OK
            return JSONResponse({"ok": True, "authenticated": True, "note": "Credentials saved, status check pending"})

    # --- Gemini: self-managed Google OAuth token exchange ---
    if provider == "gemini":
        if not _gemini_oauth_verifier or not _gemini_oauth_state:
            return JSONResponse({"ok": False, "error": "No active OAuth session. Click Connect Account again."}, status_code=400)

        auth_code = code.strip()
        import urllib.request as _urllib_req
        gemini_client_secret = os.getenv("GEMINI_CLI_OAUTH_SECRET", "")
        creds, status_code, error = _oauth_login_credentials_for_code(
            provider,
            auth_code,
            _gemini_oauth_verifier,
            now_ms=int(time.time() * 1000),
            request_factory=_urllib_req.Request,
            urlopen_fn=_urllib_req.urlopen,
            client_secret=gemini_client_secret,
        )
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=status_code)

        _write_cli_credentials(provider, creds)

        # Invalidate cache
        _auth_status_cache.pop(provider, None)

        _cli_login_authenticated = True
        return JSONResponse({"ok": True, "authenticated": True})

    # --- Other providers: need active CLI process ---
    if not _cli_login_process or _cli_login_process.poll() is not None:
        return JSONResponse({"ok": False, "error": "No active login session. Start Connect Account again."}, status_code=400)

    # --- Other providers: write code to stdin (original behavior) ---
    submitted, error, status_code = _submit_cli_login_code_to_stdin(_cli_login_process, code)
    if not submitted:
        return JSONResponse({"ok": False, "error": error}, status_code=status_code or 500)

    deadline = time.time() + 20
    while time.time() < deadline:
        if _provider_auth_status(provider):
            _cli_login_authenticated = True
            return JSONResponse({"ok": True, "authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
        if _cli_login_process.poll() is not None:
            authenticated = _cli_login_process.returncode == 0 or _provider_auth_status(provider)
            _cli_login_authenticated = authenticated
            if authenticated:
                return JSONResponse({"ok": True, "authenticated": True, "debug": _cli_login_debug_snapshot(provider)})
            break
        await asyncio.sleep(2.0)

    return JSONResponse({"ok": True, "authenticated": False, "pending": True, "debug": _cli_login_debug_snapshot(provider)})


@app.get("/api/cli-login/status")
async def cli_login_status(request: Request):
    """Check if the CLI login completed."""
    global _cli_login_process, _cli_login_authenticated
    provider = normalize_frontier_provider(_cli_login_provider or os.environ.get("JANE_BRAIN", "gemini"))
    if _cli_login_authenticated:
        response_data = {"authenticated": True, "debug": _cli_login_debug_snapshot(provider)}
    elif _provider_auth_status(provider):
        _cli_login_authenticated = True
        response_data = {"authenticated": True, "debug": _cli_login_debug_snapshot(provider)}
    elif _cli_login_process and _cli_login_process.poll() is not None:
        _cli_login_authenticated = _cli_login_process.returncode == 0 or _provider_auth_status(provider)
        response_data = {"authenticated": _cli_login_authenticated, "debug": _cli_login_debug_snapshot(provider)}
    else:
        response_data = {"authenticated": False, "debug": _cli_login_debug_snapshot(provider)}
    if not _is_local_control_ip(_client_ip(request)):
        # Don't leak debug info to non-local requests
        response_data.pop("debug", None)
    return JSONResponse(response_data)
