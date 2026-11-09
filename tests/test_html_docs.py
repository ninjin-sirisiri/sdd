from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from gitutil import git, init_repo
from sddlib.html_host_api import policy_identity
from sddlib.html_policy import (
    PolicyInputError,
    bind_receipt,
    canonical_receipt_path,
    resolve_target,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "html-docs"
FIXTURES = ROOT / "tests" / "fixtures"
SEMANTIC_STEM = "0001-queue-choice"
SEMANTIC_SOURCE = f"docs/adr/{SEMANTIC_STEM}.md"
SEMANTIC_HTML = f"docs/adr/{SEMANTIC_STEM}.html"
CSS_PATH = "docs/sdd/assets/sdd.css"


def digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def run_cli(
    repo: Path,
    *args: str,
    payload: object | None = None,
) -> subprocess.CompletedProcess[str]:
    input_text = None if payload is None else json.dumps(payload)
    return subprocess.run(
        [str(CLI), *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
    )


def result(process: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert process.stdout.endswith("\n")
    assert process.stderr == ""
    return json.loads(process.stdout)


def copy_fixture(repo: Path, kind: str, stem: str) -> tuple[Path, Path]:
    if kind == "glossary":
        relative = Path("CONTEXT.md")
    elif kind == "adr":
        relative = Path("docs/adr") / f"{stem}.md"
    elif kind == "spec":
        relative = Path("docs/sdd/specs") / f"{stem}.md"
    else:
        relative = Path("docs/sdd/plans") / f"{stem}.md"
    source = repo / relative
    companion = source.with_suffix(".html")
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / kind / f"{stem}.md", source)
    shutil.copyfile(FIXTURES / kind / f"{stem}.html", companion)
    css = repo / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* test stylesheet */\n", encoding="utf-8")
    return source, companion


def commit_all(repo: Path, message: str = "change") -> None:
    git(repo, "add", ".")
    git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", message)


def update_digest(companion: Path, old: bytes, new: bytes) -> None:
    companion.write_text(
        companion.read_text(encoding="utf-8").replace(digest(old), digest(new)),
        encoding="utf-8",
    )


def receipt_document(
    repo: Path,
    source_relative: str = SEMANTIC_SOURCE,
    *,
    source_bytes: bytes | None = None,
    html_bytes: bytes | None = None,
    css: dict[str, bytes] | None = None,
    resources: dict[str, bytes] | None = None,
    policy_version: str | None = None,
    policy_digest: str | None = None,
    versions: dict[str, str] | None = None,
    generation: dict[str, object] | None = None,
    verification: dict[str, object] | None = None,
    conditions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    html_relative = source_relative[:-3] + ".html"
    source = source_bytes if source_bytes is not None else (repo / source_relative).read_bytes()
    html = html_bytes if html_bytes is not None else (repo / html_relative).read_bytes()
    css = css if css is not None else {CSS_PATH: (repo / CSS_PATH).read_bytes()}
    resources = resources or {}
    identity = policy_identity()
    generation = generation or {
        "id": "generation-1",
        "revision": 1,
        "parent": None,
        "job": "job-1",
        "cycle": "cycle-1",
    }
    versions = versions or {
        "settings": "settings-1",
        "rubric": "rubric-1",
        "profile": "profile-1",
    }
    verification = verification or {
        "result": "pass",
        "checks": [
            {
                "name": "static",
                "decision": "pass",
                "evidence": ["docs/sdd/html-evidence/run-1/static.json"],
            }
        ],
    }
    conditions = conditions or [
        {
            "id": name,
            "decision": "met",
            "evidence": [f"docs/sdd/html-evidence/run-1/{name}.json"],
        }
        for name in ("information", "support", "usability", "render")
    ]
    return {
        "schema": "sdd-html-receipt",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": source_relative, "digest": digest(source)},
        "html": {"path": html_relative, "digest": digest(html)},
        "inputs": {
            "css": [
                {"path": path, "digest": digest(content)}
                for path, content in sorted(css.items())
            ],
            "resources": [
                {"path": path, "digest": digest(content)}
                for path, content in sorted(resources.items())
            ],
            "policy": {
                "version": policy_version or identity["version"],
                "digest": policy_digest or identity["digest"],
            },
        },
        "versions": versions,
        "generation": generation,
        "h2": {"reference": "h2-run-1", "purpose": "Html"},
        "verification": verification,
        "conditions": conditions,
    }


def receipt_path(repo: Path, source_relative: str = SEMANTIC_SOURCE) -> Path:
    return repo / canonical_receipt_path(source_relative)


def write_receipt(
    repo: Path,
    data: dict[str, object],
    source_relative: str = SEMANTIC_SOURCE,
) -> Path:
    path = receipt_path(repo, source_relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_receipt(repo: Path, source_relative: str = SEMANTIC_SOURCE) -> dict[str, object]:
    return json.loads(receipt_path(repo, source_relative).read_text(encoding="utf-8"))


def advance_generation(
    receipt: dict[str, object],
    *,
    identifier: str = "generation-2",
    revision: int = 2,
    parent: str | None = "generation-1",
) -> dict[str, object]:
    updated = json.loads(json.dumps(receipt))
    updated["generation"] = {
        "id": identifier,
        "revision": revision,
        "parent": parent,
        "job": "job-2",
        "cycle": "cycle-2",
    }
    return updated


def setup_semantic(
    repo: Path,
    *,
    with_receipt: bool = True,
    commit: bool = True,
    **receipt_options: object,
) -> tuple[Path, Path]:
    source, companion = copy_fixture(repo, "adr", SEMANTIC_STEM)
    if with_receipt:
        write_receipt(repo, receipt_document(repo, **receipt_options))
    if commit:
        commit_all(repo, "semantic base")
    return source, companion


def change_semantic_html(companion: Path) -> None:
    companion.write_text(
        companion.read_text(encoding="utf-8").replace(
            "We use <code", "Our team uses <code"
        ),
        encoding="utf-8",
    )


def violation_codes(result: dict[str, object]) -> set[str]:
    return {item["code"] for item in result["violations"]}  # type: ignore[index]


def test_edit_check_returns_policy_json_and_current_digest(tmp_path: Path) -> None:
    source = tmp_path / "CONTEXT.md"
    source.write_bytes(b"# Context\n")

    process = run_cli(
        tmp_path,
        "edit-check",
        payload={"operation": "edit", "paths": ["CONTEXT.md"]},
    )

    assert process.returncode == 0
    assert result(process) == {
        "decision": "allow",
        "message": "Markdown changed; author CONTEXT.html separately.",
        "paths": ["CONTEXT.md", "CONTEXT.html"],
        "expected_digests": {"CONTEXT.html": digest(b"# Context\n")},
    }


@pytest.mark.parametrize(
    ("payload", "needle"),
    (
        ("not json", "JSON object"),
        ({"operation": "edit", "paths": [], "unknown": []}, "unknown"),
        ({"operation": "read", "paths": []}, "operation"),
    ),
)
def test_edit_check_rejects_invalid_input_with_exit_two(
    tmp_path: Path, payload: object, needle: str
) -> None:
    process = run_cli(tmp_path, "edit-check", payload=payload)

    assert process.returncode == 2
    assert needle.casefold() in str(result(process)["message"]).casefold()
    assert result(process)["decision"] == "deny"


def test_edit_check_rejects_malformed_json_with_exit_two(tmp_path: Path) -> None:
    process = subprocess.run(
        [str(CLI), "edit-check"],
        cwd=tmp_path,
        input="{",
        text=True,
        capture_output=True,
    )

    assert process.returncode == 2
    assert "valid JSON" in str(result(process)["message"])


def test_edit_check_does_not_modify_repository_state(tmp_path: Path) -> None:
    source = tmp_path / "CONTEXT.md"
    companion = tmp_path / "CONTEXT.html"
    source.write_bytes(b"# Context\n")
    companion.write_text('<meta name="sdd-source-digest" content="sha256:' + "0" * 64 + '">', encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    process = run_cli(
        tmp_path,
        "edit-check",
        payload={"operation": "edit", "paths": ["CONTEXT.html"]},
    )

    assert process.returncode == 0
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before
    assert companion.read_text(encoding="utf-8").endswith(">")


def test_check_explicit_paths_validates_a_complete_pair(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8")
        .replace("Ordering", "Vocabulary")
        .replace('id="ordering"', 'id="vocabulary"'),
        encoding="utf-8",
    )
    update_digest(companion, old, new)

    process = run_cli(tmp_path, "check", "--paths", "CONTEXT.md", "CONTEXT.html")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["paths"] == ["CONTEXT.md", "CONTEXT.html"]
    assert checked["violations"] == []


def test_validate_accepts_a_current_companion(tmp_path: Path) -> None:
    init_repo(tmp_path)
    _source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")

    process = run_cli(tmp_path, "validate", companion.relative_to(tmp_path).as_posix())

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["paths"] == ["CONTEXT.md", "CONTEXT.html"]
    assert checked["violations"] == []


def test_check_staged_rejects_markdown_only_change(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, _companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    source.write_bytes(source.read_bytes() + b"\nChanged\n")
    git(tmp_path, "add", "CONTEXT.md")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert "CONTEXT.html" in str(checked["message"])
    assert checked["expected_digests"] == {
        "CONTEXT.html": digest(source.read_bytes())
    }


def test_check_staged_rejects_html_only_change_even_when_valid(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    companion.write_text(
        companion.read_text(encoding="utf-8").replace("Glossary", "Glossary notes"),
        encoding="utf-8",
    )
    git(tmp_path, "add", "CONTEXT.html")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "HTML-only" in str(result(process)["message"])
    assert source.exists()


def test_check_staged_validates_index_html_not_worktree_html(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    valid_html = (
        companion.read_text(encoding="utf-8")
        .replace("Ordering", "Vocabulary")
        .replace('id="ordering"', 'id="vocabulary"')
        .replace(digest(old), digest(new))
    )
    invalid_html = valid_html.replace(
        'name="sdd-source-digest"', 'name="wrong-digest"'
    )
    companion.write_text(invalid_html, encoding="utf-8")
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html")
    companion.write_text(valid_html, encoding="utf-8")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert any(
        item["code"] == "digest-metadata"  # type: ignore[index]
        for item in result(process)["violations"]  # type: ignore[index]
    )


def test_check_staged_allows_css_only_and_unrelated_changes(tmp_path: Path) -> None:
    init_repo(tmp_path)
    copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    (tmp_path / "docs/sdd/assets/sdd.css").write_text("/* changed */\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
    git(tmp_path, "add", ".")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_staged_rejects_stale_complete_pair(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    source.write_bytes(source.read_bytes() + b"\nChanged\n")
    companion.write_text(companion.read_text(encoding="utf-8").replace("Glossary", "Glossary notes"), encoding="utf-8")
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert any(item["code"] == "digest-mismatch" for item in checked["violations"])  # type: ignore[index]


def test_check_staged_rejects_partial_multi_document_change(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    other, _other_companion = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8").replace("Ordering", "Vocabulary"),
        encoding="utf-8",
    )
    update_digest(companion, old, new)
    other.write_bytes(other.read_bytes() + b"\nChanged\n")
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html", "docs/adr/0001-use-postgres.md")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "0001-use-postgres.html" in str(result(process)["message"])


def test_check_staged_allows_a_pair_rename_and_pair_delete(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    old_adr, old_adr_html = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    new_source = tmp_path / "docs/adr/0002-use-postgres.md"
    new_html = new_source.with_suffix(".html")
    new_source.parent.mkdir(parents=True, exist_ok=True)
    old_adr.rename(new_source)
    old_adr_html.rename(new_html)
    git(tmp_path, "add", "-A")
    source.unlink()
    companion.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_staged_validates_the_destination_of_a_pair_rename(tmp_path: Path) -> None:
    init_repo(tmp_path)
    old_source, old_html = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    new_source = old_source.with_name("0002-use-postgres.md")
    new_html = new_source.with_suffix(".html")
    old_source.rename(new_source)
    old_html.rename(new_html)
    new_html.write_text(
        new_html.read_text(encoding="utf-8").replace(
            'name="sdd-source-digest"', 'name="wrong-digest"'
        ),
        encoding="utf-8",
    )
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert any(item["code"] == "digest-metadata" for item in result(process)["violations"])  # type: ignore[index]


def test_check_staged_rejects_one_sided_target_delete(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, _companion = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    source.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "both" in str(result(process)["message"])


def test_check_base_reads_the_requested_three_dot_diff(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8")
        .replace("Ordering", "Vocabulary")
        .replace('id="ordering"', 'id="vocabulary"'),
        encoding="utf-8",
    )
    update_digest(companion, old, new)
    commit_all(tmp_path, "pair")

    process = run_cli(tmp_path, "check", "--base", base)

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_base_allows_explicit_bootstrap_for_html_only_migration(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    companion.write_text("<html>\n</html>\n", encoding="utf-8")
    commit_all(tmp_path, "legacy companion")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    companion.write_bytes((FIXTURES / "glossary" / "CONTEXT.html").read_bytes())
    commit_all(tmp_path, "bootstrap authored companion")

    process = run_cli(
        tmp_path,
        "check",
        "--base",
        base,
        "--bootstrap",
        source.relative_to(tmp_path).as_posix(),
    )

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["violations"] == []


def test_check_rejects_mixed_source_modes_and_missing_mode(tmp_path: Path) -> None:
    for args in (
        ("--staged", "--paths", "CONTEXT.md"),
        ("--paths", "CONTEXT.md", "--staged"),
        ("--paths", "CONTEXT.md", "--base", "HEAD"),
        (),
    ):
        process = run_cli(tmp_path, "check", *args)
        assert process.returncode == 2
        assert result(process)["decision"] == "deny"


def test_bootstrap_reports_only_requested_missing_or_metadata_less_targets(
    tmp_path: Path,
) -> None:
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    companion.unlink()
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    process = run_cli(tmp_path, "bootstrap", "CONTEXT.md")

    assert process.returncode == 0
    bootstrapped = result(process)
    assert bootstrapped["decision"] == "allow"
    assert bootstrapped["expected_digests"] == {"CONTEXT.html": digest(source.read_bytes())}
    assert bootstrapped["paths"] == ["CONTEXT.md", "CONTEXT.html"]
    assert not companion.exists()
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before


def test_bootstrap_rejects_omitted_and_non_target_paths(tmp_path: Path) -> None:
    for args in ((), ("README.md",)):
        process = run_cli(tmp_path, "bootstrap", *args)
        assert process.returncode == 2
        assert result(process)["decision"] == "deny"


def test_doctor_reports_three_registration_states_without_writing(tmp_path: Path) -> None:
    process = run_cli(tmp_path, "doctor")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert [item["host"] for item in checked["registrations"]] == [  # type: ignore[index]
        "cursor",
        "claude",
        "opencode",
    ]
    assert {item["status"] for item in checked["registrations"]} == {"missing"}  # type: ignore[index]


def test_doctor_accepts_compatible_explicit_registration_files(tmp_path: Path) -> None:
    cursor_adapter = tmp_path / "adapters/cursor/html_docs_hook.py"
    cursor_adapter.parent.mkdir(parents=True)
    cursor_adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    cursor_adapter.chmod(0o755)
    cursor = tmp_path / ".cursor/hooks.json"
    cursor.parent.mkdir()
    cursor.write_text(
        json.dumps(
            {
                "failClosed": True,
                "hooks": {
                        "preToolUse": [{"command": "adapters/cursor/html_docs_hook.py"}],
                        "afterFileEdit": [{"command": "adapters/cursor/html_docs_hook.py"}],
                        "stop": [{"command": "adapters/cursor/html_docs_hook.py"}],
                },
            }
        ),
        encoding="utf-8",
    )
    claude = tmp_path / ".claude/hooks.json"
    claude.parent.mkdir()
    claude_adapter = tmp_path / "adapters/claude/html_docs_hook.py"
    claude_adapter.parent.mkdir(parents=True)
    claude_adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    claude_adapter.chmod(0o755)
    claude.write_text(
        json.dumps(
            {
                "command": "adapters/claude/html_docs_hook.py",
                "events": ["PreToolUse", "PostToolUse"],
            }
        ),
        encoding="utf-8",
    )
    opencode = tmp_path / ".opencode/plugins/html_docs_plugin.ts"
    opencode.parent.mkdir(parents=True)
    opencode.write_text(
        "export const htmlDocs = true;\n"
        "const before = 'tool.execute.before';\n"
        "const edited = 'file.edited';\n",
        encoding="utf-8",
    )

    process = run_cli(tmp_path, "doctor")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert {item["status"] for item in checked["registrations"]} == {"enabled"}  # type: ignore[index]
def test_doctor_rejects_cursor_commands_outside_required_hooks(tmp_path: Path) -> None:
    cursor_adapter = tmp_path / "adapters/cursor/html_docs_hook.py"
    cursor_adapter.parent.mkdir(parents=True)
    cursor_adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    cursor_adapter.chmod(0o755)
    cursor = tmp_path / ".cursor/hooks.json"
    cursor.parent.mkdir()
    cursor.write_text(
        json.dumps(
            {
                "failClosed": True,
                "hooks": {
                    "preToolUse": [],
                    "afterFileEdit": [],
                    "stop": [],
                },
                "notes": "adapters/cursor/html_docs_hook.py "
                "adapters/cursor/html_docs_hook.py "
                "adapters/cursor/html_docs_hook.py",
            }
        ),
        encoding="utf-8",
    )

    process = run_cli(tmp_path, "doctor")

    checked = result(process)
    cursor_status = next(
        item["status"]
        for item in checked["registrations"]  # type: ignore[index]
        if item["host"] == "cursor"  # type: ignore[index]
    )
    assert cursor_status == "incompatible"


def test_host_api_command_returns_versioned_capabilities(tmp_path: Path) -> None:
    process = run_cli(
        tmp_path,
        "host-api",
        payload={"version": 1, "operation": "capabilities"},
    )

    assert process.returncode == 0
    checked = result(process)
    assert checked["ok"] is True
    assert checked["version"] == 1
    assert checked["operation"] == "capabilities"
    assert checked["result"]["protocol"]["version"] == 1  # type: ignore[index]
    assert checked["result"]["operations"] == [  # type: ignore[index]
        "capabilities",
        "discover",
        "source-units",
        "candidate-check",
    ]


def test_host_api_rejects_extra_arguments_with_stderr(tmp_path: Path) -> None:
    process = subprocess.run(
        [str(CLI), "host-api", "capabilities"],
        cwd=tmp_path,
        input="",
        text=True,
        capture_output=True,
    )

    assert process.returncode == 2
    assert process.stderr
    checked = json.loads(process.stdout)
    assert checked["ok"] is False
    assert checked["error"]["code"] == "invalid-request"


def test_canonical_receipt_path_uses_the_source_relative_utf8_bytes(
    tmp_path: Path,
) -> None:
    expected = (
        "docs/sdd/html-evidence/"
        + hashlib.sha256(SEMANTIC_SOURCE.encode("utf-8")).hexdigest()
        + ".json"
    )
    assert canonical_receipt_path(SEMANTIC_SOURCE) == expected
    japanese = "docs/adr/日本語.md"
    assert canonical_receipt_path(japanese) == (
        "docs/sdd/html-evidence/"
        + hashlib.sha256(japanese.encode("utf-8")).hexdigest()
        + ".json"
    )
    target = resolve_target(tmp_path, SEMANTIC_SOURCE)
    assert target is not None
    assert target.receipt_relative == expected
    assert target.receipt_path == tmp_path / expected
    for invalid in ("", "../CONTEXT.md", "/CONTEXT.md", "docs\\adr\\x.md", "docs/./x.md"):
        with pytest.raises(PolicyInputError):
            canonical_receipt_path(invalid)


def test_staged_semantic_pair_with_bound_receipt_allows(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, commit=False)
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["assurance"] == "static-only"
    assert checked["meaning_reevaluated"] is False
    assert "static-only" in str(checked["message"])
    assert "not re-evaluated" in str(checked["message"])
    receipt = checked["receipts"][0]  # type: ignore[index]
    assert receipt["status"] == "bound"
    assert receipt["path"] == canonical_receipt_path(SEMANTIC_SOURCE)
    assert receipt["source_digest"] == digest((tmp_path / SEMANTIC_SOURCE).read_bytes())
    assert receipt["versions"]["recorded"] == {
        "settings": "settings-1",
        "rubric": "rubric-1",
        "profile": "profile-1",
    }
    assert receipt["meaning_reevaluated"] is False


def test_staged_semantic_pair_requires_the_canonical_receipt(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, with_receipt=False, commit=False)
    other = tmp_path / "docs/sdd/html-evidence/run-1/receipt.json"
    other.parent.mkdir(parents=True)
    other.write_text(
        json.dumps(receipt_document(tmp_path)) + "\n", encoding="utf-8"
    )
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert "receipt-missing" in violation_codes(checked)
    assert canonical_receipt_path(SEMANTIC_SOURCE) in str(checked["message"])


def test_staged_semantic_receipt_rejects_invalid_json_and_unknown_versions(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, commit=False)
    receipt = read_receipt(tmp_path)
    receipt["version"] = 2
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-version" in violation_codes(result(process))

    init_repo(tmp_path)
    setup_semantic(tmp_path, commit=False)
    receipt_path(tmp_path).write_text("{", encoding="utf-8")
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-invalid-json" in violation_codes(result(process))


def test_staged_semantic_receipt_binds_paths_and_exact_digests(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, commit=False)
    receipt = read_receipt(tmp_path)
    receipt["source"]["path"] = "docs/adr/other.md"  # type: ignore[index]
    receipt["html"]["path"] = "docs/adr/other.html"  # type: ignore[index]
    receipt["html"]["digest"] = "sha256:" + "0" * 64  # type: ignore[index]
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    codes = violation_codes(result(process))
    assert {
        "receipt-source-path",
        "receipt-html-path",
        "receipt-html-digest",
    } <= codes


def test_staged_mode_reads_index_receipts_not_worktree_receipts(tmp_path: Path) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    original = companion.read_text(encoding="utf-8")
    change_semantic_html(companion)
    receipt = receipt_document(tmp_path)
    receipt["version"] = 2
    receipt_path(tmp_path).write_text(json.dumps(receipt), encoding="utf-8")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"

    git(tmp_path, "add", SEMANTIC_HTML)
    invalid_index_receipt = receipt_document(
        tmp_path, html_bytes=original.encode("utf-8")
    )
    invalid_index_receipt["version"] = 2
    write_receipt(tmp_path, invalid_index_receipt)
    git(tmp_path, "add", canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-version" in violation_codes(result(process))


def test_new_worktree_receipt_is_not_accepted_for_an_older_staged_html(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    git(tmp_path, "add", SEMANTIC_HTML)
    new_receipt = advance_generation(receipt_document(tmp_path))
    write_receipt(tmp_path, new_receipt)

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-html-digest" in violation_codes(result(process))

    git(tmp_path, "add", canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["receipts"][0]["re_evaluation"] == {  # type: ignore[index]
        "same_source": True,
        "html_changed": True,
        "new_generation": True,
        "previous_generation": {"id": "generation-1", "revision": 1},
    }


def test_semantic_html_only_reevaluation_allows_a_new_generation(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    receipt = advance_generation(receipt_document(tmp_path))
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", SEMANTIC_HTML, canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["receipts"][0]["re_evaluation"]["same_source"] is True  # type: ignore[index]
    assert checked["receipts"][0]["re_evaluation"]["html_changed"] is True  # type: ignore[index]
    assert "static-only" in str(checked["message"])
    # The strict HTML-only contract is not weakened.
    strict = run_cli(
        tmp_path,
        "validate",
        SEMANTIC_HTML,
    )
    assert strict.returncode == 0


def test_edited_old_receipt_without_a_new_generation_is_rejected(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    tampered = read_receipt(tmp_path)
    tampered["html"]["digest"] = digest(companion.read_bytes())  # type: ignore[index]
    write_receipt(tmp_path, tampered)
    git(tmp_path, "add", SEMANTIC_HTML, canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-generation" in violation_codes(result(process))


def test_receipt_generation_must_name_the_previous_generation_as_parent(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    receipt = advance_generation(read_receipt(tmp_path), parent=None)
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", SEMANTIC_HTML, canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-generation-parent" in violation_codes(result(process))


def test_css_change_invalidates_receipts_and_requires_a_new_generation(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path)
    (tmp_path / CSS_PATH).write_text("/* changed stylesheet */\n", encoding="utf-8")
    git(tmp_path, "add", CSS_PATH)

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-css-digest" in violation_codes(result(process))

    receipt = advance_generation(receipt_document(tmp_path))
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["receipts"][0]["re_evaluation"]["same_source"] is True  # type: ignore[index]
    assert checked["receipts"][0]["re_evaluation"]["html_changed"] is False  # type: ignore[index]


def test_partially_staged_css_and_receipt_is_rejected(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path)
    (tmp_path / CSS_PATH).write_text("/* changed stylesheet */\n", encoding="utf-8")
    receipt = advance_generation(receipt_document(tmp_path))
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-css-digest" in violation_codes(result(process))


def test_resource_fingerprints_are_bound_to_the_checked_tree(tmp_path: Path) -> None:
    init_repo(tmp_path)
    resource = tmp_path / "docs/sdd/assets/figure.svg"
    resource.parent.mkdir(parents=True, exist_ok=True)
    resource.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")
    setup_semantic(
        tmp_path,
        resources={resource.relative_to(tmp_path).as_posix(): resource.read_bytes()},
    )
    resource.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"><g></g></svg>\n", encoding="utf-8")
    git(tmp_path, "add", resource.relative_to(tmp_path).as_posix())

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-resource-digest" in violation_codes(result(process))


def test_policy_identity_and_recorded_versions_are_bound(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(
        tmp_path,
        commit=False,
        policy_digest="sha256:" + "0" * 64,
        policy_version="unknown-policy",
    )
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    codes = violation_codes(result(process))
    assert {"receipt-policy-version", "receipt-policy-digest"} <= codes

    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    write_receipt(
        tmp_path,
        advance_generation(
            receipt_document(
                tmp_path, versions={"settings": "settings-2", "rubric": "rubric-1", "profile": "profile-1"}
            )
        ),
    )
    git(tmp_path, "add", SEMANTIC_HTML, canonical_receipt_path(SEMANTIC_SOURCE))
    target = resolve_target(tmp_path, SEMANTIC_SOURCE)
    assert target is not None
    violations, evidence = bind_receipt(
        target,
        receipt_bytes=receipt_path(tmp_path).read_bytes(),
        source_bytes=(tmp_path / SEMANTIC_SOURCE).read_bytes(),
        html_bytes=companion.read_bytes(),
        expected_versions={"settings": "settings-1", "rubric": "rubric-1", "profile": "profile-1"},
        baseline_receipt=json.dumps(read_receipt(tmp_path)).encode("utf-8"),
    )
    assert "receipt-settings-version" in {item["code"] for item in violations}
    assert evidence["versions"]["recorded"]["profile"] == "profile-1"  # type: ignore[index]


def test_profile_or_rubric_changes_require_a_new_settings_version(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path)
    change_semantic_html(companion)
    receipt = advance_generation(
        receipt_document(
            tmp_path,
            versions={
                "settings": "settings-1",
                "rubric": "rubric-1",
                "profile": "profile-2",
            },
        )
    )
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", SEMANTIC_HTML, canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-profile-version" in violation_codes(result(process))

    receipt["versions"] = {  # type: ignore[index]
        "settings": "settings-2",
        "rubric": "rubric-1",
        "profile": "profile-2",
    }
    write_receipt(tmp_path, receipt)
    git(tmp_path, "add", canonical_receipt_path(SEMANTIC_SOURCE))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0


def test_receipt_verification_and_condition_decisions_must_pass(tmp_path: Path) -> None:
    init_repo(tmp_path)
    setup_semantic(
        tmp_path,
        commit=False,
        verification={
            "result": "fail",
            "checks": [
                {"name": "static", "decision": "fail", "evidence": ["run-1/static.json"]}
            ],
        },
        conditions=[
            {
                "id": "information",
                "decision": "unmet",
                "evidence": ["run-1/information.json"],
            },
            {"id": "support", "decision": "met", "evidence": ["run-1/support.json"]},
            {"id": "usability", "decision": "met", "evidence": ["run-1/usability.json"]},
            {"id": "render", "decision": "met", "evidence": ["run-1/render.json"]},
        ],
    )
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    codes = violation_codes(result(process))
    assert {"receipt-verification", "receipt-check", "receipt-condition"} <= codes


def test_semantic_pair_rename_requires_a_receipt_for_the_new_path(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    source, companion = setup_semantic(tmp_path)
    new_source = source.with_name("0002-queue-choice.md")
    new_html = companion.with_name("0002-queue-choice.html")
    source.rename(new_source)
    text = companion.read_text(encoding="utf-8").replace(SEMANTIC_SOURCE, "docs/adr/0002-queue-choice.md")
    new_html.write_text(text, encoding="utf-8")
    companion.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "receipt-missing" in violation_codes(result(process))

    new_relative = "docs/adr/0002-queue-choice.md"
    write_receipt(
        tmp_path,
        receipt_document(tmp_path, new_relative),
        source_relative=new_relative,
    )
    git(tmp_path, "add", canonical_receipt_path(new_relative))

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_semantic_delete_contract_and_orphaned_artifacts_are_not_exempt(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    source, companion = setup_semantic(tmp_path)
    source.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "one-sided-delete" in violation_codes(result(process))

    companion.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert receipt_path(tmp_path).exists()


def test_check_base_binds_receipts_against_the_merge_base(tmp_path: Path) -> None:
    init_repo(tmp_path)
    _source, companion = setup_semantic(tmp_path, commit=False)
    commit_all(tmp_path, "semantic base")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    change_semantic_html(companion)
    write_receipt(tmp_path, advance_generation(receipt_document(tmp_path)))
    commit_all(tmp_path, "semantic re-evaluation")

    process = run_cli(tmp_path, "check", "--base", base)

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"

    companion.write_text(
        companion.read_text(encoding="utf-8").replace(
            "Our team uses", "The team uses"
        ),
        encoding="utf-8",
    )
    base_generation = receipt_document(tmp_path)
    write_receipt(tmp_path, base_generation)
    commit_all(tmp_path, "edited receipt without a new generation")

    process = run_cli(tmp_path, "check", "--base", base)

    assert process.returncode == 1
    assert "receipt-generation" in violation_codes(result(process))


def test_offline_check_opens_no_network_and_loads_no_model_client(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, commit=False)
    git(tmp_path, "add", "-A")
    script = """
import json
import sys

events = []

def audit(event, args):
    if event.startswith(("socket.", "urllib.", "http.")):
        events.append(event)

sys.addaudithook(audit)
sys.path.insert(0, sys.argv[1])
from sddlib.html_docs import main

code = main(["check", "--staged"])
models = sorted(
    name
    for name in ("openai", "anthropic", "requests", "httpx", "urllib.request")
    if name in sys.modules
)
print(json.dumps({"code": code, "events": events, "models": models}))
"""
    process = subprocess.run(
        [sys.executable, "-c", script, str(ROOT / "scripts")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert process.returncode == 0, process.stderr
    summary = json.loads(process.stdout.splitlines()[-1])
    assert summary["code"] == 0
    assert summary["events"] == []
    assert summary["models"] == []


def test_validate_remains_a_structural_check_without_a_receipt(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    setup_semantic(tmp_path, with_receipt=False, commit=False)

    process = run_cli(tmp_path, "validate", SEMANTIC_HTML)

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["violations"] == []
