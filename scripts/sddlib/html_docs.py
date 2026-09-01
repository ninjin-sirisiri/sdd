from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import NoReturn

from sddlib.html_policy import (
    GitChange,
    PolicyInputError,
    bootstrap_documents,
    check_edit,
    check_freshness,
    check_registrations,
    resolve_target,
    validate_html,
)


class CLIInputError(ValueError):
    """Invalid command-line or stdin input."""


def _result_error(message: str) -> dict[str, object]:
    return {
        "decision": "deny",
        "message": message,
        "paths": [],
        "expected_digests": {},
    }


def _write_result(result: dict[str, object], exit_code: int) -> int:
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    return exit_code


def _fail(message: str, exit_code: int = 2) -> NoReturn:
    raise CLIInputError(message)


def _normalize_edit_paths(root: Path, value: object, label: str) -> object:
    if not isinstance(value, list):
        raise CLIInputError(f"{label} must be a JSON array of paths")
    for path in value:
        # The policy resolver is deliberately called before the policy action so
        # every host sees the same repository-relative path validation.
        resolve_target(root, path)  # type: ignore[arg-type]
    return value


def _edit_check(root: Path) -> tuple[dict[str, object], int]:
    try:
        raw = sys.stdin.read()
    except OSError as exc:
        return _result_error(f"cannot read edit-check input: {exc}"), 2
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        return _result_error(f"edit-check input must be valid JSON: {exc}"), 2
    if not isinstance(payload, dict):
        return _result_error("edit-check input must be a JSON object"), 2

    allowed = {"operation", "paths", "bootstrap_paths", "new_source_paths"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        return _result_error(
            "edit-check input contains unknown field(s): " + ", ".join(unknown)
        ), 2
    if payload.get("operation") != "edit":
        return _result_error("edit-check operation must be 'edit'"), 2
    if "paths" not in payload:
        return _result_error("edit-check input requires paths"), 2

    try:
        paths = _normalize_edit_paths(root, payload["paths"], "paths")
        bootstrap_paths = _normalize_edit_paths(
            root, payload.get("bootstrap_paths", []), "bootstrap_paths"
        )
        new_source_paths = _normalize_edit_paths(
            root, payload.get("new_source_paths", []), "new_source_paths"
        )
        policy_result = check_edit(
            root,
            paths,  # type: ignore[arg-type]
            bootstrap_paths,  # type: ignore[arg-type]
            new_source_paths,  # type: ignore[arg-type]
        )
    except PolicyInputError as exc:
        return exc.result, exc.exit_code
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return _result_error(f"edit-check failed: {exc}"), 2
    return policy_result, 0 if policy_result["decision"] == "allow" else 1


def _parse_check_args(args: list[str]) -> tuple[str, str | None, list[str]]:
    if not args:
        _fail("check requires exactly one of --staged, --base REF, or explicit paths")

    mode: str | None = None
    reference: str | None = None
    explicit: list[str] = []
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--staged":
            if mode is not None or explicit:
                _fail("check accepts exactly one source mode")
            mode = "staged"
        elif argument == "--base":
            if mode is not None or explicit:
                _fail("check accepts exactly one source mode")
            if index + 1 >= len(args) or not args[index + 1]:
                _fail("--base requires REF")
            mode = "base"
            reference = args[index + 1]
            index += 1
        elif argument == "--paths":
            if mode is not None or explicit:
                _fail("check accepts exactly one source mode")
            if index + 1 >= len(args):
                _fail("--paths requires at least one path")
            mode = "paths"
            tail = args[index + 1 :]
            if any(item.startswith("-") for item in tail):
                _fail("check accepts exactly one source mode")
            explicit.extend(tail)
            break
        elif argument.startswith("-"):
            _fail(f"unknown check option: {argument}")
        else:
            if mode is not None:
                _fail("check accepts exactly one source mode")
            explicit.append(argument)
        index += 1

    if mode is None:
        if not explicit:
            _fail("check requires at least one explicit path")
        mode = "paths"
    if mode in {"staged", "base"} and index + 1 < len(args):
        _fail("check accepts exactly one source mode")
    return mode, reference, explicit


def _parse_git_changes(output: bytes) -> list[GitChange]:
    fields = output.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    changes: list[GitChange] = []
    index = 0
    while index < len(fields):
        try:
            status = fields[index].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CLIInputError("git status contains a non-UTF-8 status") from exc
        index += 1
        count = 2 if status[:1] in {"R", "C"} else 1
        if index + count > len(fields):
            raise CLIInputError("git status output is truncated")
        try:
            paths = tuple(fields[index + offset].decode("utf-8") for offset in range(count))
        except UnicodeDecodeError as exc:
            raise CLIInputError("git status contains a non-UTF-8 path") from exc
        index += count
        changes.append(GitChange(status, paths))
    return changes


def _git_changes(root: Path, mode: str, reference: str | None, paths: list[str]) -> list[GitChange]:
    if mode == "paths":
        return [GitChange("M", (path,)) for path in paths]
    if mode == "staged":
        command = ["git", "diff", "--cached", "--name-status", "--find-renames", "-z"]
    else:
        if reference is None:
            raise CLIInputError("check base reference is missing")
        command = [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            f"{reference}...HEAD",
            "-z",
        ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise CLIInputError(f"cannot execute git diff: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CLIInputError(f"git diff failed: {detail or 'unknown error'}")
    return _parse_git_changes(completed.stdout)


def _check(root: Path, args: list[str]) -> tuple[dict[str, object], int]:
    mode, reference, paths = _parse_check_args(args)
    changes = _git_changes(root, mode, reference, paths)
    policy_result = check_freshness(root, changes)
    return policy_result, 0 if policy_result["decision"] == "allow" else 1


def _validate(root: Path, args: list[str]) -> tuple[dict[str, object], int]:
    if not args or any(argument.startswith("-") for argument in args):
        raise CLIInputError("validate requires explicit Target paths")

    targets = {}
    for path in args:
        target = resolve_target(root, path)
        if target is not None:
            targets[target.source_relative] = target

    if not targets:
        return {
            "decision": "allow",
            "message": "No synchronized target documents are affected.",
            "paths": [],
            "expected_digests": {},
            "violations": [],
            "warnings": [],
        }, 0

    paths: list[str] = []
    expected_digests: dict[str, str] = {}
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for target in targets.values():
        result = validate_html(root, target.source_path, target.companion_path)
        paths.extend(result["paths"])  # type: ignore[arg-type]
        expected_digests.update(result["expected_digests"])  # type: ignore[arg-type]
        violations.extend(result["violations"])  # type: ignore[arg-type]
        warnings.extend(result["warnings"])  # type: ignore[arg-type]

    unique_paths = list(dict.fromkeys(paths))
    if violations:
        message = "HTML validation failed: " + " ".join(
            item["message"] for item in violations
        )
        decision = "deny"
    else:
        message = "All requested HTML companions are valid."
        decision = "allow"
    return {
        "decision": decision,
        "message": message,
        "paths": unique_paths,
        "expected_digests": expected_digests,
        "violations": violations,
        "warnings": warnings,
    }, 0 if decision == "allow" else 1


def _bootstrap(root: Path, args: list[str]) -> tuple[dict[str, object], int]:
    if not args or any(argument.startswith("-") for argument in args):
        raise CLIInputError("bootstrap requires explicit Target Markdown paths")
    policy_result = bootstrap_documents(root, args)
    return policy_result, 0 if policy_result["decision"] == "allow" else 1


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in {
        "edit-check",
        "check",
        "validate",
        "bootstrap",
        "doctor",
    }:
        return _write_result(
            _result_error(
                "usage: html-docs {edit-check|check|validate|bootstrap|doctor}"
            ),
            2,
        )

    command, command_args = arguments[0], arguments[1:]
    root = Path.cwd()
    try:
        if command == "edit-check":
            if command_args:
                raise CLIInputError("edit-check does not accept command-line arguments")
            policy_result, code = _edit_check(root)
        elif command == "check":
            policy_result, code = _check(root, command_args)
        elif command == "validate":
            policy_result, code = _validate(root, command_args)
        elif command == "bootstrap":
            policy_result, code = _bootstrap(root, command_args)
        else:
            if command_args:
                raise CLIInputError("doctor does not accept command-line arguments")
            policy_result = check_registrations(root)
            code = 0 if policy_result["decision"] == "allow" else 1
    except PolicyInputError as exc:
        policy_result, code = exc.result, exc.exit_code
    except (CLIInputError, OSError, RuntimeError, TypeError, ValueError) as exc:
        policy_result, code = _result_error(str(exc)), 2
    except Exception as exc:  # noqa: BLE001 - CLI execution boundary
        policy_result, code = _result_error(f"html-docs failed: {exc}"), 2
    return _write_result(policy_result, code)
