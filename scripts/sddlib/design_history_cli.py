"""``scripts/design-history`` command line.

Subcommands:

- ``search``: read-only JSON search over recorded design question/answer pairs.
- ``status``: read-only report of the store, Git precheck, and recorder state.
- ``record``: write one payload (``register``, ``reply``, ``cancel``, ``status``)
  from a host adapter's stdin.
- ``git-check``: verify the Git ignore/untracked precheck without writing.

Search is the only documented user-facing read path; it never creates the
database.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from sddlib.design_history import (
    EXIT_GIT_REFUSED,
    EXIT_INVALID,
    EXIT_NO_DATABASE,
    EXIT_NO_MATCHES,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    SEARCH_STATUS_INVALID,
    SEARCH_STATUS_NO_DATABASE,
    SEARCH_STATUS_NO_MATCHES,
    SEARCH_STATUS_OK,
    SEARCH_STATUS_RECORDING_UNAVAILABLE,
    SEARCH_STATUS_UNAVAILABLE,
    DesignHistoryError,
    GitPrecheckError,
    git_precheck,
    record_payload,
    search,
    status_report,
)

USAGE = """usage: design-history <command> [options]

commands:
  search [--case TEXT] [--question-id ID] [--query TEXT] [--state STATE]
         [--source SOURCE] [--limit N] [--json]
  status [--json]
  record [--db PATH]
  git-check [--db PATH]

Search and status only read. Search prints JSON and never creates the database.
"""


def _parse_options(args: list[str]) -> tuple[dict[str, str], list[str]]:
    options: dict[str, str] = {}
    rest: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--json", "--help", "-h"):
            options[arg] = "true"
            index += 1
            continue
        if arg.startswith("--"):
            name = arg[2:]
            if "=" in name:
                name, value = name.split("=", 1)
                options[name] = value
                index += 1
                continue
            if index + 1 >= len(args):
                raise DesignHistoryError(f"option --{name} requires a value")
            options[name] = args[index + 1]
            index += 2
            continue
        rest.append(arg)
        index += 1
    return options, rest


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


def _exit_for_status(status: str) -> int:
    if status == SEARCH_STATUS_OK:
        return EXIT_OK
    if status == SEARCH_STATUS_NO_MATCHES:
        return EXIT_NO_MATCHES
    if status == SEARCH_STATUS_NO_DATABASE:
        return EXIT_NO_DATABASE
    if status == SEARCH_STATUS_RECORDING_UNAVAILABLE:
        return EXIT_UNAVAILABLE
    if status == SEARCH_STATUS_UNAVAILABLE:
        return EXIT_UNAVAILABLE
    if status == SEARCH_STATUS_INVALID:
        return EXIT_INVALID
    return EXIT_UNAVAILABLE


def _search(argv: list[str]) -> int:
    options, rest = _parse_options(argv)
    if rest:
        raise DesignHistoryError(f"unexpected argument: {rest[0]}")
    limit_raw = options.get("limit")
    limit: int | None = None
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
        except ValueError as exc:
            raise DesignHistoryError(f"--limit must be an integer: {limit_raw}") from exc
    result = search(
        checkout=Path.cwd(),
        db=options.get("db"),
        case=options.get("case"),
        question_id=options.get("question-id") or options.get("question"),
        query=options.get("query") or options.get("q"),
        state=options.get("state"),
        source=options.get("source"),
        limit=limit,
    )
    _emit(result)
    return _exit_for_status(result["status"])


def _status(argv: list[str]) -> int:
    options, rest = _parse_options(argv)
    if rest:
        raise DesignHistoryError(f"unexpected argument: {rest[0]}")
    report = status_report(checkout=Path.cwd(), db=options.get("db"))
    _emit(report)
    git = report.get("git") or {}
    if git and not git.get("ok"):
        return EXIT_GIT_REFUSED
    return EXIT_OK


def _record(argv: list[str]) -> int:
    options, rest = _parse_options(argv)
    if rest:
        raise DesignHistoryError(f"unexpected argument: {rest[0]}")
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise DesignHistoryError(f"record expects one JSON payload on stdin: {exc}") from exc
    if not isinstance(payload, dict):
        raise DesignHistoryError("record payload must be a JSON object")
    if options.get("db"):
        payload.setdefault("db", options["db"])
    result = record_payload(payload)
    _emit(result)
    return EXIT_OK


def _git_check(argv: list[str]) -> int:
    options, rest = _parse_options(argv)
    if rest:
        raise DesignHistoryError(f"unexpected argument: {rest[0]}")
    precheck = git_precheck(Path.cwd(), options.get("db"))
    _emit(
        {
            "ok": True,
            "checkout": str(precheck.checkout),
            "gitRoot": str(precheck.git_root),
            "database": str(precheck.database),
            "ignored": precheck.ignored,
            "tracked": precheck.tracked,
        }
    )
    return EXIT_OK


COMMANDS = {
    "search": _search,
    "status": _status,
    "record": _record,
    "git-check": _git_check,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("--help", "-h"):
        print(USAGE, end="")
        return EXIT_OK if args else EXIT_INVALID
    command, rest = args[0], args[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        return EXIT_INVALID
    try:
        return handler(rest)
    except GitPrecheckError as exc:
        _emit({"status": "refused", "reason": exc.reason, "detail": exc.detail, "guidance": exc.guidance})
        return EXIT_GIT_REFUSED
    except DesignHistoryError as exc:
        _emit({"status": SEARCH_STATUS_INVALID, "detail": str(exc)})
        return EXIT_INVALID
    except OSError as exc:
        _emit({"status": SEARCH_STATUS_UNAVAILABLE, "detail": str(exc)})
        return EXIT_UNAVAILABLE
