"""``scripts/design-history`` command line.

Subcommands:

- ``search``: read-only JSON search over recorded design question/answer pairs.
- ``status``: read-only report of the store, Git precheck, and recorder state.
- ``record``: write one host payload (``register``, ``reply``, ``cancel``,
  ``status``) from a host adapter's stdin. Imports never take this path.
- ``git-check``: verify the Git ignore/untracked precheck without writing.
- ``import-preview``: report the excerpt pairs a named log would contribute and
  the exact reason every other pair is excluded. Writes nothing.
- ``import-confirm``: save exactly those previewed pairs. This is the only
  import command that writes.

Search and status are read-only and never create the database. A preview is not
consent: only ``import-confirm`` may write, and it re-reads the same log.
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
from sddlib.design_history_import import (
    FORMAT_NAME,
    FORMAT_VERSION,
    STATUS_NOTHING_TO_IMPORT,
    confirm_import,
    preview_import,
)

USAGE = f"""usage: design-history <command> [options]

commands:
  search [--case TEXT] [--question-id ID] [--query TEXT] [--state STATE]
         [--source SOURCE] [--limit N] [--json]
  status [--json]
  record [--db PATH]
  git-check [--db PATH]
  import-preview --log FILE --case CASE [--db PATH]
  import-confirm --log FILE --case CASE [--db PATH]

Search, status, and import-preview only read. Search and import-preview never
create the database. import-preview reports the excerpt pairs that would be
imported and the exact reason every other pair is excluded. import-confirm is
the only command that saves an import; a preview is not consent.

Import log format (version {FORMAT_VERSION}, UTF-8 JSON, excerpts only):

  {{
    "format": "{FORMAT_NAME}",
    "version": {FORMAT_VERSION},
    "title": "Past interview: checkout cancel",        (optional)
    "questions": [
      {{
        "question": "Can a deletion be undone?",       (required)
        "id": "checkout-cancel.q1",                    (optional)
        "header": "Delete",                            (optional)
        "options": ["Yes", "No"],                      (optional, in order)
        "answer": "Yes",                               (required)
        "state": "answered"                            (optional)
      }}
    ]
  }}

A pair is imported only when the question text, the ordered options, and the
answer correspondence are provable from the document: every answer value must
be exactly one listed option, or the pair must list no options at all. The
source file is read only and never modified. Full transcripts, attachments,
tool output, and credentials are not part of this format; a pair containing a
credential is excluded and only the omission is reported. Name both the log
and the design case explicitly; the tool never scans directories.

import procedure:
  1. design-history import-preview --log FILE --case CASE
     Review "importable" and the reason on every entry in "excluded".
  2. design-history import-confirm --log FILE --case CASE
     Re-reads the same FILE; compare its reported log.sha256 with step 1.

An excluded pair is never imported, and a preview is not consent.

exclusion reasons (importable is reported separately, with its own reason):
  ambiguous-question-id      two pairs use one ID for different content
  ambiguous-options          one option label is listed twice
  answer-not-in-options      the answer is not one of the listed options
  changed-question           this case already imported a different question
  duplicate-pair             identical to an earlier pair in the log
  excerpt-too-long           a field exceeds its excerpt limit
  invalid-pair-shape         a field has the wrong JSON type
  invalid-question-id        an explicit id is not one token
  missing-answer             the pair has no answer
  missing-question           the pair has no question text
  secret-detected            the pair holds a credential; text is not stored
  unsupported-answer-shape   the answer is not a string or list of strings
  unsupported-field          the pair or log has an unknown field
  unsupported-state          the state is an absence, not an answer
log-level reasons: log-unreadable, log-too-large, log-not-utf8, log-not-json,
  log-not-an-object, unsupported-format, unsupported-version,
  unsupported-field, no-questions

exit codes: 0 ok, 2 invalid request/format, 3 nothing importable or no
matches, 4 no database, 5 unavailable (unreadable database), 6 Git-refused
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
    if status == STATUS_NOTHING_TO_IMPORT:
        return EXIT_NO_MATCHES
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


def _import_options(argv: list[str]) -> tuple[str, str, str | None]:
    options, rest = _parse_options(argv)
    if rest:
        raise DesignHistoryError(f"unexpected argument: {rest[0]}")
    log = options.get("log") or options.get("file")
    if not log:
        raise DesignHistoryError("import requires --log FILE naming one local log")
    case = options.get("case")
    if not case:
        raise DesignHistoryError("import requires --case naming the design case")
    return log, case, options.get("db")


def _import_preview(argv: list[str]) -> int:
    log, case, db = _import_options(argv)
    result = preview_import(checkout=Path.cwd(), log=log, case=case, db=db)
    _emit(result)
    return _exit_for_status(result["status"])


def _import_confirm(argv: list[str]) -> int:
    log, case, db = _import_options(argv)
    result = confirm_import(checkout=Path.cwd(), log=log, case=case, db=db)
    _emit(result)
    return _exit_for_status(result["status"])


COMMANDS = {
    "search": _search,
    "status": _status,
    "record": _record,
    "git-check": _git_check,
    "import-preview": _import_preview,
    "import-confirm": _import_confirm,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in ("--help", "-h"):
        print(USAGE, end="")
        return EXIT_OK if args else EXIT_INVALID
    command, rest = args[0], args[1:]
    # A per-command ``--help`` documents the same format and the same
    # write/no-write split as the top-level help, and never requires --log.
    if any(arg in ("--help", "-h") for arg in rest):
        print(USAGE, end="")
        return EXIT_OK
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
