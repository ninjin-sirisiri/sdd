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


EVENTS = {"preToolUse", "afterFileEdit", "stop"}
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "Delete"}
PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "notebookPath")
LIST_KEYS = ("edits", "files", "changes")
KNOWN_FIELDS = {
    "conversation_id",
    "generation_id",
    "model",
    "model_id",
    "model_params",
    "hook_event_name",
    "event",
    "cursor_version",
    "workspace_roots",
    "user_email",
    "transcript_path",
    "tool_name",
    "tool",
    "tool_input",
    "input",
    "tool_use_id",
    "cwd",
    "agent_message",
    "file_path",
    "filePath",
    "path",
    "edits",
    "files",
    "status",
    "loop_count",
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
    if not values or not isinstance(values[0], str) or values[0] not in EVENTS:
        raise AdapterInputError("payload contains an unknown Cursor hook event")
    return values[0]


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


def request_from_payload(payload: Any) -> dict[str, Any] | None:
    """Translate a Cursor payload; None means the event is not a file edit."""

    if not isinstance(payload, dict):
        raise AdapterInputError("Cursor hook input must be a JSON object")
    _check_fields(payload)
    event = _event_name(payload)
    if event == "stop":
        return {"operation": "edit", "paths": [], **_options(payload)}

    if event == "afterFileEdit":
        if "file_path" in payload or "filePath" in payload or "path" in payload:
            source = {key: payload[key] for key in PATH_KEYS if key in payload}
        else:
            source = payload.get("edits", payload.get("files"))
            if source is None:
                raise AdapterInputError("afterFileEdit payload has no edited path")
            source = {"files": source}
        paths = _paths(source)
        if not paths:
            raise AdapterInputError("afterFileEdit payload has no edited path")
        return {"operation": "edit", "paths": paths, **_options(payload)}

    tool = payload.get("tool_name", payload.get("tool"))
    if not isinstance(tool, str) or not tool:
        raise AdapterInputError("preToolUse payload has no tool name")
    if tool not in FILE_TOOLS:
        return None
    if "tool_input" in payload:
        tool_input = payload["tool_input"]
    elif "input" in payload:
        tool_input = payload["input"]
    else:
        tool_input = {}
    if not isinstance(tool_input, dict):
        raise AdapterInputError("preToolUse tool_input must be an object")
    paths = _paths(tool_input)
    if not paths:
        return None
    options = _options(payload, tool_input)
    if tool == "Write":
        new_sources = target_source_paths(paths)
        if new_sources:
            options["new_source_paths"] = list(
                dict.fromkeys([*options.get("new_source_paths", []), *new_sources])
            )
    return {"operation": "edit", "paths": paths, **options}


def _response(decision: str, message: str = "") -> dict[str, Any]:
    response: dict[str, Any] = {"continue": True, "permission": decision}
    if decision == "deny":
        response["user_message"] = message
        response["agent_message"] = message
    return response


def handle_payload(payload: Any) -> dict[str, Any]:
    try:
        request = request_from_payload(payload)
        if request is None:
            return _response("allow")
        result = invoke_policy(request)
        decision = result["decision"]
        message = result.get("message", "")
        return _response(decision, message if isinstance(message, str) else "")
    except (AdapterInputError, PolicyExecutionError) as exc:
        return _response(
            "deny",
            f"HTML synchronization hook setup failed: {exc}. "
            "HTML edits are blocked; Markdown editing remains available.",
        )
    except Exception as exc:  # noqa: BLE001 - host process boundary
        return _response(
            "deny",
            f"HTML synchronization hook failed closed: {exc}. "
            "Run html-docs doctor; Markdown editing remains available.",
        )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        result = _response(
            "deny",
            f"HTML synchronization hook setup failed: malformed Cursor payload ({exc}). "
            "Run html-docs doctor; Markdown editing remains available.",
        )
    else:
        result = handle_payload(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
