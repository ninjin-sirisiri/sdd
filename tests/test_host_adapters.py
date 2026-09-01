from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.claude import html_docs_hook as claude
from adapters.cursor import html_docs_hook as cursor


CURSOR_HOOK = ROOT / "adapters/cursor/html_docs_hook.py"
CLAUDE_HOOK = ROOT / "adapters/claude/html_docs_hook.py"


def make_repo(tmp_path: Path, *, companion: bool = True) -> Path:
    (tmp_path / "CONTEXT.md").write_bytes(
        (ROOT / "tests/fixtures/glossary/CONTEXT.md").read_bytes()
    )
    (tmp_path / "docs/sdd/assets").mkdir(parents=True)
    shutil.copyfile(
        ROOT / "tests/fixtures/docs/sdd/assets/sdd.css",
        tmp_path / "docs/sdd/assets/sdd.css",
    )
    if companion:
        shutil.copyfile(
            ROOT / "tests/fixtures/glossary/CONTEXT.html",
            tmp_path / "CONTEXT.html",
        )
    return tmp_path


def run_hook(path: Path, repo: Path, payload: object) -> dict[str, Any]:
    process = subprocess.run(
        [str(path)],
        cwd=repo,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0
    assert process.stderr == ""
    return json.loads(process.stdout)


@pytest.mark.parametrize(
    ("hook", "fixture", "expected"),
    (
        (CURSOR_HOOK, "pre_tool_use.json", "allow"),
        (CURSOR_HOOK, "after_file_edit.json", "allow"),
        (CURSOR_HOOK, "stop.json", "allow"),
        (CURSOR_HOOK, "unknown.json", "deny"),
        (CLAUDE_HOOK, "pre_tool_use.json", "allow"),
        (CLAUDE_HOOK, "post_tool_use.json", "allow"),
        (CLAUDE_HOOK, "unknown.json", "deny"),
    ),
)
def test_stdin_fixtures_map_host_decisions(
    tmp_path: Path, hook: Path, fixture: str, expected: str
) -> None:
    repo = make_repo(tmp_path)
    host = "cursor" if hook == CURSOR_HOOK else "claude"
    payload = json.loads(
        (ROOT / "adapters" / host / "fixtures" / fixture).read_text(encoding="utf-8")
    )
    result = run_hook(hook, repo, payload)
    if host == "cursor":
        assert result["permission"] == expected
    else:
        assert result["hookSpecificOutput"]["permissionDecision"] == expected


@pytest.mark.parametrize(
    ("hook", "fixture", "key"),
    (
        (CURSOR_HOOK, "bootstrap.json", "permission"),
        (CLAUDE_HOOK, "bootstrap.json", "hookSpecificOutput"),
    ),
)
def test_stdin_fixtures_preserve_bootstrap_permissions(
    tmp_path: Path, hook: Path, fixture: str, key: str
) -> None:
    repo = make_repo(tmp_path, companion=False)
    host = "cursor" if hook == CURSOR_HOOK else "claude"
    payload = json.loads(
        (ROOT / "adapters" / host / "fixtures" / fixture).read_text(encoding="utf-8")
    )
    result = run_hook(hook, repo, payload)
    decision = result[key] if host == "cursor" else result[key]["permissionDecision"]
    assert decision == "allow"


def test_cursor_write_pretool_marks_new_target_source() -> None:
    request = cursor.request_from_payload(
        {
            "hook_event_name": "preToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "CONTEXT.md", "content": "# new\n"},
        }
    )

    assert request == {
        "operation": "edit",
        "paths": ["CONTEXT.md"],
        "new_source_paths": ["CONTEXT.md"],
    }


def test_claude_write_pretool_marks_new_target_source() -> None:
    event, request = claude.request_from_payload(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "CONTEXT.md", "content": "# new\n"},
        }
    )

    assert event == "PreToolUse"
    assert request == {
        "operation": "edit",
        "paths": ["CONTEXT.md"],
        "new_source_paths": ["CONTEXT.md"],
    }


def test_cursor_multiedit_maps_a_mixed_pair_to_policy_denial(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    result = run_hook(
        CURSOR_HOOK,
        repo,
        {
            "hook_event_name": "preToolUse",
            "tool_name": "MultiEdit",
            "tool_input": {
                "edits": [
                    {"file_path": "CONTEXT.md", "new_string": "changed"},
                    {"file_path": "CONTEXT.html", "new_string": "changed"},
                ]
            },
        },
    )
    assert result["permission"] == "deny"
    assert "paired Markdown and HTML" in result["agent_message"]


def test_non_target_file_edits_remain_available(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    result = run_hook(
        CURSOR_HOOK,
        repo,
        {
            "hook_event_name": "preToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "notes.txt", "content": "note"},
        },
    )
    assert result["permission"] == "allow"


@pytest.mark.parametrize("module", (cursor, claude))
def test_policy_timeout_or_failure_denies_html_edit(
    monkeypatch: pytest.MonkeyPatch, module: Any
) -> None:
    def fail(_request: object) -> dict[str, str]:
        raise module.PolicyExecutionError("the policy timed out")

    monkeypatch.setattr(module, "invoke_policy", fail)
    payload = (
        {
            "hook_event_name": "preToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "CONTEXT.html"},
        }
        if module is cursor
        else {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "CONTEXT.html"},
        }
    )
    result = module.handle_payload(payload)
    if module is cursor:
        assert result["permission"] == "deny"
        assert "Markdown editing remains available" in result["user_message"]
    else:
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Markdown editing remains available" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_registration_examples_use_required_markers() -> None:
    cursor_config = json.loads(
        (ROOT / "adapters/cursor/hooks.json.example").read_text(encoding="utf-8")
    )
    assert cursor_config["failClosed"] is True
    assert set(cursor_config["hooks"]) == {"preToolUse", "afterFileEdit", "stop"}
    for entries in cursor_config["hooks"].values():
        assert entries[0]["command"] == "adapters/cursor/html_docs_hook.py"

    claude_config = json.loads(
        (ROOT / "hooks/hooks.json").read_text(encoding="utf-8")
    )
    assert set(claude_config["hooks"]) == {"PreToolUse", "PostToolUse"}
    for groups in claude_config["hooks"].values():
        assert groups[0]["matcher"] == "Edit|Write|MultiEdit|NotebookEdit"
        assert (
            groups[0]["hooks"][0]["command"]
            == "${CLAUDE_PLUGIN_ROOT}/adapters/claude/html_docs_hook.py"
        )
