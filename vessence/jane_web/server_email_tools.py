"""Server-side execution for email client-tool markers."""

from __future__ import annotations

import logging

from jane_web.email_tool_results import (
    format_email_readback as _format_email_readback,
    format_email_search_results as _format_email_search_results,
    format_inbox_emails as _format_inbox_emails,
    format_sent_email_status as _format_sent_email_status,
    prepare_send_email_args as _prepare_send_email_args,
)


logger = logging.getLogger("jane.proxy")


def execute_email_tool_serverside(tool_call: dict) -> str:
    """Execute an email.* tool call server-side and return visible status text."""
    tool = tool_call.get("tool", "")
    args = tool_call.get("args", {})
    try:
        if tool == "email.read_inbox":
            from agent_skills.email_tools import read_inbox

            limit = args.get("limit", 10)
            query = args.get("query", "is:unread")
            emails = read_inbox(limit=limit, query=query)
            return _format_inbox_emails(emails)

        if tool == "email.read":
            from agent_skills.email_tools import read_email

            msg_id = args.get("message_id", "")
            if not msg_id:
                return "\n\nError: no message_id provided."
            email_data = read_email(msg_id)
            return _format_email_readback(email_data)

        if tool == "email.search":
            from agent_skills.email_tools import search_emails

            query = args.get("query", "")
            limit = args.get("limit", 10)
            emails = search_emails(query=query, limit=limit)
            return _format_email_search_results(query, emails)

        if tool == "email.send":
            from agent_skills.email_tools import send_email

            request, validation_error = _prepare_send_email_args(args)
            if validation_error:
                return validation_error
            assert request is not None
            result = send_email(
                to=request.to,
                subject=request.subject,
                body=request.body,
                from_email=request.from_email,
            )
            sender, status_text = _format_sent_email_status(result, request)
            logger.info(
                "Email sent: id=%s from=%s to=%s",
                result.get("message_id", "?"),
                sender,
                request.to,
            )
            return status_text

        if tool == "email.delete":
            from agent_skills.email_tools import delete_email

            msg_id = (args.get("message_id") or "").strip()
            if not msg_id:
                return "\n\nEmail not deleted: no message_id provided."
            delete_email(msg_id)
            logger.info("Email trashed: id=%s", msg_id)
            return f"\n\n[Email {msg_id} moved to trash.]"

        logger.warning("Unknown email tool: %s", tool)
        return ""
    except RuntimeError as exc:
        logger.warning("Email tool %s failed (no credentials): %s", tool, exc)
        return (
            "\n\nGmail is not set up yet. Please sign in with Google on the Vessence web UI "
            "to enable email."
        )
    except Exception as exc:
        logger.error("Email tool %s failed: %s", tool, exc)
        return f"\n\nEmail error: {exc}"
