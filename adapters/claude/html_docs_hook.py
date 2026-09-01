#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _policy import (
    AdapterInputError,
    PolicyExecutionError,
    invoke_policy,
    target_source_paths,
)


EVENTS = {"PreToolUse", "PostToolUse"}
FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "notebookPath")
LIST_KEYS = ("edits", "files", "changes")
KNOWN_FIELDS = {
    "session_id",
    "transcript_path",
    "cwd",
    "hook_event_name",
    "event",
    "tool_name",
    "tool_input",
    "tool_response",
    "tool_use_id",
    "permission_mode",
    "agent_id",
    "agent_type",
    "model",
    "reason",
    "source",
    "prompt",
    "last_assistant_message",
    "stop_hook_active",
    "duration",
    "duration_ms",
    "bootstrap_paths",
    "new_source_paths",
}


def _check_fields(payload: dict[str, Any]) -> None:
    unknown = sorted(set(payload) - KNOWN_FIELDS)
    if unknown:
        raise AdapterInputError("payload contains unknown field(s): " + ", ".join(unknown))


def _event_name(payload: dict[str, Any]) -> str:
    values = [payload[name] for name in ("hook_event_name", "event") if name in payload]
    if len(values) == 2 and values[0] != values[1]:
        raise AdapterInputError("payload contains conflicting event names")
    value = values[0] if values else None
    if not isinstance(value, str) or value not in EVENTS:
        raise AdapterInputError("payload contains an unknown Claude hook event")
    return value


def _paths(value: Any) -> list[str]:
    if not isinstance(value, dict):
        raise AdapterInputError("file-tool input must be an object")
    found: list[str] = []
    for key in PATH_KEYS:
        if key not in value:
            continue
        path = value[key]
        if not isinstance(path, str) or not path:
            raise AdapterInputError(f"{key} must be a non-empty path")
        found.append(path)
    for key in LIST_KEYS:
        if key not in value:
            continue
        entries = value[key]
        if not isinstance(entries, list):
            raise AdapterInputError(f"{key} must be an array")
        for entry in entries:
            if isinstance(entry, str):
                if not entry:
                    raise AdapterInputError(f"{key} contains an empty path")
                found.append(entry)
            else:
                found.extend(_paths(entry))
    return list(dict.fromkeys(found))


def _options(payload: dict[str, Any], tool_input: dict[str, Any] | None = None) -> dict[str, list[str]]:
    options: dict[str, list[str]] = {}
    for name in ("bootstrap_paths", "new_source_paths"):
        value = payload.get(name, tool_input.get(name, []) if tool_input else [])
        if not isinstance(value, list) or any(not isinstance(path, str) or not path for path in value):
            raise AdapterInputError(f"{name} must be an array of non-empty paths")
        if value:
            options[name] = value
    return options


def request_from_payload(payload: Any) -> tuple[str, dict[str, Any] | None]:
    if not isinstance(payload, dict):
        raise AdapterInputError("Claude hook input must be a JSON object")
    _check_fields(payload)
    event = _event_name(payload)
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        raise AdapterInputError("Claude hook payload has no tool name")
    if tool not in FILE_TOOLS:
        return event, None
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        raise AdapterInputError("tool_input must be an object")
    paths = _paths(tool_input)
    if not paths:
        return event, None
    options = _options(payload, tool_input)
    if tool == "Write":
        new_sources = target_source_paths(paths)
        if new_sources:
            options["new_source_paths"] = list(
                dict.fromkeys([*options.get("new_source_paths", []), *new_sources])
            )
    return event, {"operation": "edit", "paths": paths, **options}


def _response(event: str, decision: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def handle_payload(payload: Any) -> dict[str, Any]:
    event = payload.get("hook_event_name", payload.get("event", "Unknown")) if isinstance(payload, dict) else "Unknown"
    if not isinstance(event, str) or not event:
        event = "Unknown"
    try:
        event, request = request_from_payload(payload)
        if request is None:
            return _response(event, "allow", "No synchronized target documents are affected.")
        result = invoke_policy(request)
        message = result.get("message", "")
        reason = message if isinstance(message, str) and message else "The html-docs policy completed."
        return _response(event, result["decision"], reason)
    except (AdapterInputError, PolicyExecutionError) as exc:
        return _response(
            event,
            "deny",
            f"HTML synchronization hook setup failed: {exc}. "
            "HTML edits are blocked; Markdown editing remains available.",
        )
    except Exception as exc:  # noqa: BLE001 - host process boundary
        return _response(
            event,
            "deny",
            f"HTML synchronization hook failed closed: {exc}. "
            "Run html-docs doctor; Markdown editing remains available.",
        )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        result = _response(
            "Unknown",
            "deny",
            f"HTML synchronization hook setup failed: malformed Claude payload ({exc}). "
            "Run html-docs doctor; Markdown editing remains available.",
        )
    else:
        result = handle_payload(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
