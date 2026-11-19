"""Design interview history: transactional storage and read-only search.

The store lives at ``<checkout>/.sdd/design-history.sqlite3``. It records the
raw question text, the options in presentation order, and the value the host
actually delivered. The model never writes these rows; the OpenCode adapter
forwards host events and tool results to this module.

Write access requires a Git precheck: the database and its sidecar files must
be ignored by Git and must not be tracked. Search never creates or modifies
the database, so a missing database is reported instead of being created.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from typing import Any, Iterable, Iterator, Sequence

DB_RELATIVE = Path(".sdd") / "design-history.sqlite3"
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

SCHEMA_VERSION = 1

HOST = "opencode-v2"

# Imported past logs are not a host event stream. Their `host` and `source`
# values must stay distinguishable from every `opencode.*` live source so a
# reader can never mistake an import for a recorded presentation.
IMPORT_HOST = "design-history-import"
IMPORT_SOURCE = "design-history.import"

# A hand-written import document is an excerpt list, not a transcript.
IMPORT_LOG_LIMIT_BYTES = 4 * 1024 * 1024

# Form / answer states. "answered", "held", and "corrected" are user-supplied
# answers. "cancelled", "unanswered", and "partial" are the absence of an
# answer and must never be read as agreement.
STATE_ANSWERED = "answered"
STATE_HELD = "held"
STATE_CORRECTED = "corrected"
STATE_CANCELLED = "cancelled"
STATE_UNANSWERED = "unanswered"
STATE_PARTIAL = "partial"
STATE_ACTIVE = "active"
STATE_STOPPED = "stopped"
STATE_ERROR = "error"
STATE_UNCONFIGURED = "unconfigured"

ANSWER_STATES = (STATE_ANSWERED, STATE_HELD, STATE_CORRECTED)

SEARCH_STATUS_OK = "ok"
SEARCH_STATUS_NO_MATCHES = "no-matches"
SEARCH_STATUS_NO_DATABASE = "no-database"
SEARCH_STATUS_UNAVAILABLE = "unavailable"
SEARCH_STATUS_RECORDING_UNAVAILABLE = "recording-unavailable"
SEARCH_STATUS_INVALID = "invalid"

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_NO_MATCHES = 3
EXIT_NO_DATABASE = 4
EXIT_UNAVAILABLE = 5
EXIT_GIT_REFUSED = 6

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"(?i)\b(?:password|passwd|passphrase|secret|api[_-]?key|access[_-]?token|"
        r"refresh[_-]?token|client[_-]?secret|authorization)\b\s*[:=]\s*\S{6,}"
    ),
)


class DesignHistoryError(Exception):
    """Base error for store operations."""


class GitPrecheckError(DesignHistoryError):
    """The database location fails the Git exclusion/untracked precheck."""

    def __init__(self, reason: str, detail: str, *, guidance: str | None = None) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.guidance = guidance or (
            "Add the history directory to .gitignore (for example `.sdd/`), "
            "keep it untracked, and run the design interview again."
        )


@dataclass(frozen=True)
class PrecheckResult:
    checkout: Path
    git_root: Path
    database: Path
    ignored: bool
    tracked: bool

    @property
    def ok(self) -> bool:
        return self.ignored and not self.tracked


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def database_path(checkout: Path | str, db: Path | str | None = None) -> Path:
    root = Path(checkout).expanduser()
    if db is not None:
        candidate = Path(db).expanduser()
        return candidate if candidate.is_absolute() else (root / candidate)
    return root / DB_RELATIVE


def _git(cwd: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def git_precheck(checkout: Path | str, db: Path | str | None = None) -> PrecheckResult:
    """Check that the database is ignored by Git and untracked.

    Raises :class:`GitPrecheckError` when the checkout is not a Git work tree,
    the database escapes the checkout, or Git does not ignore it.
    """

    root = Path(checkout).expanduser().resolve()
    database = database_path(root, db).resolve()

    try:
        database.relative_to(root)
    except ValueError as exc:
        raise GitPrecheckError(
            "outside-checkout",
            f"history database {database} is outside checkout {root}",
        ) from exc

    probe = _git(root, ["rev-parse", "--show-toplevel"])
    if probe.returncode != 0 or not probe.stdout.strip():
        raise GitPrecheckError(
            "not-a-git-repository",
            f"{root} is not inside a Git work tree, so the history cannot be excluded from Git",
        )
    git_root = Path(probe.stdout.strip()).resolve()

    relative = database.relative_to(root).as_posix()
    # Check tracked state first: a tracked path is never "ignored" in the
    # check-ignore sense, and "tracked" is the more precise refusal.
    tracked = _git(root, ["ls-files", "--error-unmatch", "--", relative]).returncode == 0
    ignored = _git(root, ["check-ignore", "-q", "--", relative]).returncode == 0

    if tracked:
        raise GitPrecheckError(
            "tracked",
            f"{database} is tracked by Git; design history must stay untracked",
        )
    if not ignored:
        raise GitPrecheckError(
            "not-ignored",
            f"{database} is not ignored by Git; design history would be committed",
        )

    for suffix in SIDECAR_SUFFIXES:
        sidecar = f"{relative}{suffix}"
        if _git(root, ["ls-files", "--error-unmatch", "--", sidecar]).returncode == 0:
            raise GitPrecheckError(
                "tracked",
                f"history sidecar {sidecar} is tracked by Git",
            )

    return PrecheckResult(
        checkout=root,
        git_root=git_root,
        database=database,
        ignored=ignored,
        tracked=tracked,
    )


def _schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS design_form (
        id INTEGER PRIMARY KEY,
        checkout TEXT NOT NULL,
        session_id TEXT NOT NULL,
        form_id TEXT NOT NULL,
        design_case TEXT NOT NULL,
        title TEXT,
        host TEXT NOT NULL,
        source TEXT NOT NULL,
        metadata_json TEXT,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (session_id, form_id)
    );

    CREATE TABLE IF NOT EXISTS design_question (
        id INTEGER PRIMARY KEY,
        form_pk INTEGER NOT NULL REFERENCES design_form(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL,
        field_key TEXT,
        ordinal INTEGER NOT NULL,
        text TEXT NOT NULL,
        header TEXT,
        description TEXT,
        options_json TEXT NOT NULL,
        allows_free_text INTEGER NOT NULL DEFAULT 1,
        required INTEGER NOT NULL DEFAULT 0,
        UNIQUE (form_pk, question_id)
    );

    CREATE TABLE IF NOT EXISTS design_answer (
        id INTEGER PRIMARY KEY,
        question_pk INTEGER NOT NULL REFERENCES design_question(id) ON DELETE CASCADE,
        state TEXT NOT NULL,
        answer_json TEXT,
        answer_text TEXT NOT NULL DEFAULT '',
        revision INTEGER NOT NULL DEFAULT 1,
        source TEXT NOT NULL,
        delivery TEXT NOT NULL,
        event_id TEXT,
        digest TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        UNIQUE (question_pk, digest)
    );

    CREATE TABLE IF NOT EXISTS design_omission (
        id INTEGER PRIMARY KEY,
        form_pk INTEGER NOT NULL REFERENCES design_form(id) ON DELETE CASCADE,
        question_pk INTEGER,
        question_id TEXT,
        reason TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS recorder_status (
        id INTEGER PRIMARY KEY,
        checkout TEXT NOT NULL,
        session_id TEXT,
        status TEXT NOT NULL,
        detail TEXT,
        updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS design_form_case_idx ON design_form (design_case);
    CREATE INDEX IF NOT EXISTS design_form_checkout_idx ON design_form (checkout);
    CREATE INDEX IF NOT EXISTS design_question_form_idx ON design_question (form_pk, ordinal);
    CREATE INDEX IF NOT EXISTS design_answer_question_idx ON design_answer (question_pk, revision);
    CREATE INDEX IF NOT EXISTS recorder_status_checkout_idx ON recorder_status (checkout, updated_at);
    """


def connect_for_write(
    checkout: Path | str,
    db: Path | str | None = None,
) -> sqlite3.Connection:
    """Open (creating when allowed) the history database for writing.

    The Git precheck runs before the directory or database file is created.
    """

    precheck = git_precheck(checkout, db)
    precheck.database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(precheck.database))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_schema_sql())
    connection.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    connection.commit()
    return connection


@contextmanager
def write_session(
    checkout: Path | str,
    db: Path | str | None = None,
) -> Iterator[sqlite3.Connection]:
    connection = connect_for_write(checkout, db)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def contains_secret(text: str) -> bool:
    """Return True when the text looks like a credential rather than a design answer."""

    if not text:
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _answer_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return " / ".join(_answer_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _digest(state: str, value: Any) -> str:
    payload = json.dumps(
        {"state": state, "answer": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def answer_digest(state: str, value: Any) -> str:
    """The stable identity of one answer revision, as stored in ``design_answer``.

    Import previews use this to tell "already recorded" from "new revision"
    without duplicating the store's digest rule.
    """

    return _digest(state, value)


def _normalize_options(options: Iterable[Any] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, option in enumerate(options or ()):
        if isinstance(option, dict):
            entry: dict[str, Any] = {"ordinal": index}
            for key in ("value", "label", "description"):
                if key in option and option[key] is not None:
                    entry[key] = option[key]
            if "value" not in entry and "label" in entry:
                entry["value"] = entry["label"]
            normalized.append(entry)
        else:
            normalized.append({"ordinal": index, "value": str(option), "label": str(option)})
    return normalized


def _form_metadata(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("metadata")
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return None


def _require_existing_database(
    checkout: Path,
    db: Path | str | None,
    operation: str,
) -> Path:
    """Refuse a reply/cancel before creating a database that has no form.

    A reply or cancel can only apply to a form the plugin already registered.
    If no database exists, there is nothing registered, so the operation must
    fail without leaving an empty database behind.
    """

    path = database_path(checkout, db).resolve()
    if not path.exists():
        raise DesignHistoryError(
            f"{operation} requires a registered design form, but no history database exists"
        )
    return path


def _resolve_checkout(payload: dict[str, Any]) -> Path:
    checkout = payload.get("checkout")
    if not isinstance(checkout, str) or not checkout:
        raise DesignHistoryError("payload requires a checkout directory")
    return Path(checkout).expanduser().resolve()


def _require_same_checkout(connection: sqlite3.Connection, checkout: Path) -> None:
    """Reject a payload that does not belong to this database's checkout.

    The database file is per checkout. Writing another checkout's session into
    it would mix repositories, so the boundary is re-checked at write time.
    """

    row = connection.execute("SELECT value FROM meta WHERE key = 'checkout'").fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO meta (key, value) VALUES ('checkout', ?)",
            (str(checkout),),
        )
        return
    if row["value"] != str(checkout):
        raise DesignHistoryError(
            f"history database belongs to {row['value']}, not {checkout}"
        )


def _upsert_form(connection: sqlite3.Connection, payload: dict[str, Any], checkout: Path) -> int:
    session_id = str(payload.get("sessionID") or "")
    form_id = str(payload.get("formID") or "")
    design_case = str(payload.get("case") or "")
    if not session_id or not form_id or not design_case:
        raise DesignHistoryError("register requires sessionID, formID, and case")
    now = utc_now()
    title = payload.get("title")
    source = str(payload.get("source") or HOST)
    host = str(payload.get("host") or HOST)
    metadata_json = _form_metadata(payload)
    connection.execute(
        """
        INSERT INTO design_form (
            checkout, session_id, form_id, design_case, title, host, source,
            metadata_json, state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, form_id) DO UPDATE SET
            design_case = excluded.design_case,
            title = COALESCE(excluded.title, design_form.title),
            source = excluded.source,
            metadata_json = COALESCE(excluded.metadata_json, design_form.metadata_json),
            updated_at = excluded.updated_at
        """,
        (
            str(checkout),
            session_id,
            form_id,
            design_case,
            title,
            host,
            source,
            metadata_json,
            STATE_ACTIVE,
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT id FROM design_form WHERE session_id = ? AND form_id = ?",
        (session_id, form_id),
    ).fetchone()
    return int(row["id"])


def _register_questions(
    connection: sqlite3.Connection,
    form_pk: int,
    payload: dict[str, Any],
) -> int:
    recorded = 0
    for ordinal, question in enumerate(payload.get("questions") or ()):
        if not isinstance(question, dict):
            raise DesignHistoryError("questions must be objects")
        question_id = str(question.get("questionID") or question.get("questionId") or "")
        if not question_id:
            raise DesignHistoryError("each question requires a questionID")
        field_key = question.get("fieldKey")
        field_key = str(field_key) if isinstance(field_key, str) and field_key else None
        text = str(question.get("text") or question.get("title") or "")
        header = question.get("header")
        description = question.get("description")
        options = _normalize_options(question.get("options"))
        secret_haystack = "\n".join(
            part
            for part in (
                text,
                str(header or ""),
                str(description or ""),
                *(str(option.get("label") or "") for option in options),
            )
            if part
        )
        if contains_secret(secret_haystack):
            connection.execute(
                "INSERT INTO design_omission (form_pk, question_pk, question_id, reason, recorded_at) "
                "VALUES (?, NULL, ?, 'secret-detected', ?)",
                (form_pk, question_id, utc_now()),
            )
            continue
        connection.execute(
            """
            INSERT INTO design_question (
                form_pk, question_id, field_key, ordinal, text, header, description,
                options_json, allows_free_text, required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(form_pk, question_id) DO UPDATE SET
                field_key = COALESCE(excluded.field_key, design_question.field_key),
                ordinal = excluded.ordinal,
                text = excluded.text,
                header = excluded.header,
                description = excluded.description,
                options_json = excluded.options_json,
                allows_free_text = excluded.allows_free_text,
                required = excluded.required
            """,
            (
                form_pk,
                question_id,
                field_key,
                int(question.get("ordinal", ordinal)),
                text,
                header,
                description,
                json.dumps(options, ensure_ascii=False),
                1 if question.get("allowsFreeText", True) else 0,
                1 if question.get("required") else 0,
            ),
        )
        recorded += 1
    return recorded


def _insert_answer(
    connection: sqlite3.Connection,
    question_pk: int,
    *,
    state: str,
    value: Any,
    source: str,
    delivery: str,
    event_id: str | None = None,
) -> bool:
    """Append one answer revision. Returns False when it is already recorded.

    Earlier revisions are never updated or deleted: a correction is a new row.
    """

    text = _answer_text(value)
    digest = _digest(state, value)
    existing = connection.execute(
        "SELECT id FROM design_answer WHERE question_pk = ? AND digest = ?",
        (question_pk, digest),
    ).fetchone()
    if existing is not None:
        return False
    if state in ANSWER_STATES and contains_secret(text):
        connection.execute(
            "INSERT INTO design_omission (form_pk, question_pk, question_id, reason, recorded_at) "
            "SELECT q.form_pk, q.id, q.question_id, 'secret-detected', ? "
            "FROM design_question q WHERE q.id = ?",
            (utc_now(), question_pk),
        )
        return False
    row = connection.execute(
        "SELECT COALESCE(MAX(revision), 0) AS revision FROM design_answer WHERE question_pk = ?",
        (question_pk,),
    ).fetchone()
    revision = int(row["revision"]) + 1
    connection.execute(
        """
        INSERT INTO design_answer (
            question_pk, state, answer_json, answer_text, revision,
            source, delivery, event_id, digest, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question_pk,
            state,
            json.dumps(value, ensure_ascii=False) if value is not None else None,
            text,
            revision,
            source,
            delivery,
            event_id,
            digest,
            utc_now(),
        ),
    )
    return True


def _question_rows(connection: sqlite3.Connection, form_pk: int) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            "SELECT * FROM design_question WHERE form_pk = ? ORDER BY ordinal, id",
            (form_pk,),
        )
    )


def _set_form_state(connection: sqlite3.Connection, form_pk: int, state: str) -> None:
    connection.execute(
        "UPDATE design_form SET state = ?, updated_at = ? WHERE id = ?",
        (state, utc_now(), form_pk),
    )


def _answer_map_by_question(
    questions: Sequence[sqlite3.Row],
    answers: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Translate host field keys to stable question IDs.

    ``form.replied`` keys are host field keys (``q0``…). A question is matched
    by its recorded field key, then by its stable question ID. Anything else is
    unregistered and must not become an answer.
    """

    by_field: dict[str, Any] = {}
    unregistered: list[str] = []
    field_to_question = {
        str(row["field_key"]): row["question_id"]
        for row in questions
        if row["field_key"]
    }
    question_ids = {str(row["question_id"]) for row in questions}
    for key, value in answers.items():
        if key in field_to_question:
            by_field[field_to_question[key]] = value
        elif key in question_ids:
            by_field[key] = value
        else:
            unregistered.append(str(key))
    return by_field, unregistered


def record_register(payload: dict[str, Any]) -> dict[str, Any]:
    """Create or update a design form and its questions."""

    checkout = _resolve_checkout(payload)
    with write_session(checkout, payload.get("db") or None) as connection:
        _require_same_checkout(connection, checkout)
        form_pk = _upsert_form(connection, payload, checkout)
        recorded = _register_questions(connection, form_pk, payload)
        _set_form_state(connection, form_pk, STATE_ACTIVE)
    return {
        "ok": True,
        "action": "register",
        "form": payload.get("formID"),
        "questions": recorded,
    }


def record_reply(payload: dict[str, Any]) -> dict[str, Any]:
    """Record the answer map delivered by the host for one registered form."""

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise DesignHistoryError("reply requires an answers object")
    checkout = _resolve_checkout(payload)
    source = str(payload.get("source") or "opencode.form.replied")
    delivery = str(payload.get("delivery") or "event")
    event_id = payload.get("eventID")
    state_override = payload.get("state")
    if state_override is not None and state_override not in ANSWER_STATES:
        raise DesignHistoryError(f"unsupported answer state: {state_override}")
    record_missing = bool(payload.get("recordMissing"))
    recorded: list[str] = []
    omitted: list[str] = []
    unanswered: list[str] = []

    _require_existing_database(checkout, payload.get("db") or None, "reply")
    with write_session(checkout, payload.get("db") or None) as connection:
        form_pk = _require_form(connection, payload)
        rows = _question_rows(connection, form_pk)
        if not rows:
            raise DesignHistoryError("form is not registered with any question")
        mapped, unregistered = _answer_map_by_question(rows, answers)
        for key in unregistered:
            connection.execute(
                "INSERT INTO design_omission (form_pk, question_pk, question_id, reason, recorded_at) "
                "VALUES (?, NULL, ?, 'unregistered-question', ?)",
                (form_pk, key, utc_now()),
            )
        for row in rows:
            question_id = str(row["question_id"])
            if question_id in mapped:
                value = mapped[question_id]
                if contains_secret(_answer_text(value)):
                    connection.execute(
                        "INSERT INTO design_omission (form_pk, question_pk, question_id, reason, recorded_at) "
                        "VALUES (?, ?, ?, 'secret-detected', ?)",
                        (form_pk, row["id"], question_id, utc_now()),
                    )
                    omitted.append(question_id)
                    continue
                if _insert_answer(
                    connection,
                    int(row["id"]),
                    state=state_override or STATE_ANSWERED,
                    value=value,
                    source=source,
                    delivery=delivery,
                    event_id=event_id,
                ):
                    recorded.append(question_id)
            elif record_missing:
                if _insert_answer(
                    connection,
                    int(row["id"]),
                    state=STATE_UNANSWERED,
                    value=None,
                    source=source,
                    delivery=delivery,
                    event_id=event_id,
                ):
                    unanswered.append(question_id)
        answered_count = sum(
            1
            for row in rows
            if connection.execute(
                "SELECT 1 FROM design_answer WHERE question_pk = ? AND state IN (?, ?, ?) LIMIT 1",
                (int(row["id"]), *ANSWER_STATES),
            ).fetchone()
            is not None
        )
        if answered_count == len(rows):
            state = STATE_ANSWERED
        elif answered_count:
            state = STATE_PARTIAL
        else:
            state = STATE_ACTIVE
        _set_form_state(connection, form_pk, state)
    return {
        "ok": True,
        "action": "reply",
        "recorded": recorded,
        "omitted": omitted,
        "unanswered": unanswered,
    }


def record_cancel(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a cancelled form without discarding earlier answers."""

    checkout = _resolve_checkout(payload)
    source = str(payload.get("source") or "opencode.form.cancelled")
    delivery = str(payload.get("delivery") or "event")
    event_id = payload.get("eventID")
    recorded: list[str] = []
    _require_existing_database(checkout, payload.get("db") or None, "cancel")
    with write_session(checkout, payload.get("db") or None) as connection:
        form_pk = _require_form(connection, payload)
        for row in _question_rows(connection, form_pk):
            question_id = str(row["question_id"])
            answered = connection.execute(
                "SELECT 1 FROM design_answer WHERE question_pk = ? AND state IN (?, ?, ?) LIMIT 1",
                (int(row["id"]), *ANSWER_STATES),
            ).fetchone()
            if answered is not None:
                continue
            if _insert_answer(
                connection,
                int(row["id"]),
                state=STATE_CANCELLED,
                value=None,
                source=source,
                delivery=delivery,
                event_id=event_id,
            ):
                recorded.append(question_id)
        _set_form_state(connection, form_pk, STATE_CANCELLED)
    return {"ok": True, "action": "cancel", "recorded": recorded}


def record_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Record whether recording is active, stopped, erroring, or unconfigured."""

    checkout = _resolve_checkout(payload)
    status = str(payload.get("status") or "")
    if not status:
        raise DesignHistoryError("status requires a status value")
    with write_session(checkout, payload.get("db") or None) as connection:
        _require_same_checkout(connection, checkout)
        connection.execute(
            "INSERT INTO recorder_status (checkout, session_id, status, detail, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                str(checkout),
                payload.get("sessionID"),
                status,
                payload.get("detail"),
                utc_now(),
            ),
        )
    return {"ok": True, "action": "status", "status": status}


def _imported_questions(
    connection: sqlite3.Connection, design_case: str
) -> dict[str, dict[str, str]]:
    """Question text and options already imported for one design case."""

    rows = connection.execute(
        """
        SELECT q.question_id, q.text, q.options_json
        FROM design_question q JOIN design_form f ON f.id = q.form_pk
        WHERE f.design_case = ? AND f.source = ?
        """,
        (design_case, IMPORT_SOURCE),
    ).fetchall()
    return {
        str(row["question_id"]): {
            "text": str(row["text"]),
            "options_json": str(row["options_json"]),
        }
        for row in rows
    }


def record_import(payload: dict[str, Any]) -> dict[str, Any]:
    """Store explicit excerpt pairs taken from a user-named past log.

    Imported records use :data:`IMPORT_HOST` / :data:`IMPORT_SOURCE`, never an
    ``opencode.*`` value, so a reader can tell an import from a recorded
    presentation. Repeating the same import appends no answer revision: the
    store's ``(question_pk, digest)`` identity dedupes it.

    ``payload["pairs"]`` carry only excerpts (question text, header, options,
    answer value). A pair that contains a credential is omitted and reported,
    never written.
    """

    checkout = _resolve_checkout(payload)
    session_id = str(payload.get("sessionID") or "")
    form_id = str(payload.get("formID") or "")
    design_case = str(payload.get("case") or "")
    if not session_id or not form_id or not design_case:
        raise DesignHistoryError("import requires sessionID, formID, and case")
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise DesignHistoryError("import requires at least one pair")

    metadata = payload.get("metadata")
    provenance = payload.get("provenance")
    provenance = str(provenance) if isinstance(provenance, str) and provenance else None
    recorded: list[str] = []
    already: list[str] = []
    omitted: list[str] = []

    with write_session(checkout, payload.get("db") or None) as connection:
        _require_same_checkout(connection, checkout)
        form_pk = _upsert_form(
            connection,
            {
                "sessionID": session_id,
                "formID": form_id,
                "case": design_case,
                "title": payload.get("title"),
                "host": IMPORT_HOST,
                "source": IMPORT_SOURCE,
                "metadata": {"import": metadata} if isinstance(metadata, dict) else None,
            },
            checkout,
        )
        # An import adds answers; it never rewrites a question already imported
        # for this case. Identity is the question ID, not the log file, so a
        # copied or moved log cannot silently redefine a question.
        previous_questions = _imported_questions(connection, design_case)
        for pair in pairs:
            if not isinstance(pair, dict):
                raise DesignHistoryError("each import pair must be an object")
            question_id = str(pair.get("questionID") or "")
            previous = previous_questions.get(question_id)
            if previous is None:
                continue
            incoming_options = json.dumps(
                _normalize_options(pair.get("options")), ensure_ascii=False
            )
            if previous["text"] != str(pair.get("text") or "") or previous[
                "options_json"
            ] != incoming_options:
                raise DesignHistoryError(
                    f"question {question_id!r} was already imported for case "
                    f"{design_case!r} with different question text or options; "
                    "an import must not change it"
                )

        _register_questions(connection, form_pk, {"questions": pairs})
        for ordinal, pair in enumerate(pairs):
            question_id = str(pair.get("questionID") or "")
            row = connection.execute(
                "SELECT id, text, options_json FROM design_question "
                "WHERE form_pk = ? AND question_id = ?",
                (form_pk, question_id),
            ).fetchone()
            if row is None:
                # The question itself carried a credential and was not stored.
                omitted.append(question_id)
                continue
            value = pair.get("value")
            if _insert_answer(
                connection,
                int(row["id"]),
                state=str(pair.get("state") or STATE_ANSWERED),
                value=value,
                source=IMPORT_SOURCE,
                delivery="import",
                event_id=provenance,
            ):
                recorded.append(question_id)
            else:
                already.append(question_id)
        total = len(pairs)
        if len(recorded) + len(already) == total:
            _set_form_state(connection, form_pk, STATE_ANSWERED)
        elif recorded or already:
            _set_form_state(connection, form_pk, STATE_PARTIAL)
    return {
        "ok": True,
        "action": "import",
        "recorded": recorded,
        "alreadyRecorded": already,
        "omitted": omitted,
    }


def imported_form_state(
    checkout: Path | str,
    db: Path | str | None = None,
    *,
    session_id: str,
    form_id: str,
) -> dict[str, Any] | None:
    """What one imported log already contributed.

    Returns ``{"digests": {(questionID, digest)}, "questions": {questionID:
    {"text": str, "options": tuple[str, ...]}}}``. Returns ``None`` when a
    database exists but cannot be read, so a preview can report "unavailable"
    instead of claiming every pair is new.
    """

    path = database_path(Path(checkout).expanduser().resolve(), db).resolve()
    if not path.exists():
        return {"digests": set(), "questions": {}}
    try:
        connection = _connect_readonly(path)
        try:
            form = connection.execute(
                "SELECT id FROM design_form WHERE session_id = ? AND form_id = ?",
                (session_id, form_id),
            ).fetchone()
            if form is None:
                return {"digests": set(), "questions": {}}
            rows = connection.execute(
                """
                SELECT q.question_id, q.text, q.options_json, a.digest
                FROM design_question q
                LEFT JOIN design_answer a ON a.question_pk = q.id
                WHERE q.form_pk = ?
                """,
                (int(form["id"]),),
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return None
    questions: dict[str, dict[str, Any]] = {}
    digests: set[tuple[str, str]] = set()
    for row in rows:
        question_id = str(row["question_id"])
        options = tuple(
            str(option.get("label") or option.get("value") or "")
            for option in json.loads(row["options_json"] or "[]")
        )
        questions[question_id] = {"text": str(row["text"]), "options": options}
        if row["digest"] is not None:
            digests.add((question_id, str(row["digest"])))
    return {"digests": digests, "questions": questions}


def _require_form(connection: sqlite3.Connection, payload: dict[str, Any]) -> int:
    session_id = str(payload.get("sessionID") or "")
    form_id = str(payload.get("formID") or "")
    if not session_id or not form_id:
        raise DesignHistoryError("form operations require sessionID and formID")
    row = connection.execute(
        "SELECT id FROM design_form WHERE session_id = ? AND form_id = ?",
        (session_id, form_id),
    ).fetchone()
    if row is None:
        raise DesignHistoryError(
            f"form {form_id} in session {session_id} is not a registered design form"
        )
    return int(row["id"])


def record_payload(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "")
    if action == "register":
        return record_register(payload)
    if action == "reply":
        return record_reply(payload)
    if action == "cancel":
        return record_cancel(payload)
    if action == "status":
        return record_status(payload)
    raise DesignHistoryError(f"unknown record action: {action or '<missing>'}")


# ---------------------------------------------------------------------------
# Read-only search
# ---------------------------------------------------------------------------


def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _latest_recorder_status(connection: sqlite3.Connection, checkout: str) -> dict[str, Any] | None:
    try:
        row = connection.execute(
            "SELECT session_id, status, detail, updated_at FROM recorder_status "
            "WHERE checkout = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
            (checkout,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    return {
        "sessionID": row["session_id"],
        "status": row["status"],
        "detail": row["detail"],
        "updatedAt": row["updated_at"],
    }


def _load_pairs(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    forms = list(connection.execute("SELECT * FROM design_form ORDER BY created_at, id"))
    pairs: list[dict[str, Any]] = []
    for form in forms:
        questions = list(
            connection.execute(
                "SELECT * FROM design_question WHERE form_pk = ? ORDER BY ordinal, id",
                (int(form["id"]),),
            )
        )
        omissions = {
            row["question_id"]: row["reason"]
            for row in connection.execute(
                "SELECT question_id, reason FROM design_omission WHERE form_pk = ? AND question_id IS NOT NULL",
                (int(form["id"]),),
            )
        }
        for question in questions:
            answers = list(
                connection.execute(
                    "SELECT state, answer_json, answer_text, revision, source, delivery, "
                    "event_id, recorded_at "
                    "FROM design_answer WHERE question_pk = ? ORDER BY revision, id",
                    (int(question["id"]),),
                )
            )
            pairs.append(
                {
                    "case": form["design_case"],
                    "checkout": form["checkout"],
                    "source": form["source"],
                    "host": form["host"],
                    "state": form["state"],
                    "form": {
                        "id": form["form_id"],
                        "sessionID": form["session_id"],
                        "title": form["title"],
                        "createdAt": form["created_at"],
                        "updatedAt": form["updated_at"],
                    },
                    "question": {
                        "questionID": question["question_id"],
                        "fieldKey": question["field_key"],
                        "ordinal": int(question["ordinal"]),
                        "text": question["text"],
                        "header": question["header"],
                        "description": question["description"],
                        "options": json.loads(question["options_json"]),
                        "allowsFreeText": bool(question["allows_free_text"]),
                        "required": bool(question["required"]),
                        "omitted": omissions.get(question["question_id"]),
                    },
                    "answers": [
                        {
                            "state": row["state"],
                            "value": json.loads(row["answer_json"]) if row["answer_json"] is not None else None,
                            "text": row["answer_text"],
                            "revision": int(row["revision"]),
                            "source": row["source"],
                            "delivery": row["delivery"],
                            "eventID": row["event_id"],
                            "recordedAt": row["recorded_at"],
                        }
                        for row in answers
                    ],
                }
            )
    return pairs


def pair_state(pair: dict[str, Any]) -> str:
    """The current state of one question, without treating silence as agreement."""

    answers = pair["answers"]
    if not answers:
        return STATE_UNANSWERED
    for row in reversed(answers):
        if row["state"] in ANSWER_STATES:
            return row["state"]
    return str(answers[-1]["state"])


def _match_query(pair: dict[str, Any], query: str) -> bool:
    needle = query.casefold()
    haystack: list[str] = [str(pair["case"]), str(pair["form"].get("title") or "")]
    question = pair["question"]
    haystack.extend(
        [
            str(question.get("text") or ""),
            str(question.get("header") or ""),
            str(question.get("description") or ""),
            str(question.get("questionID") or ""),
        ]
    )
    for option in question.get("options") or ():
        if isinstance(option, dict):
            haystack.extend(str(option.get(key) or "") for key in ("value", "label", "description"))
    for answer in pair["answers"]:
        haystack.append(str(answer.get("text") or ""))
        value = answer.get("value")
        if isinstance(value, list):
            haystack.extend(_answer_text(item) for item in value)
        elif value is not None:
            haystack.append(_answer_text(value))
    return any(needle in value.casefold() for value in haystack if value)


def filter_pairs(
    pairs: Iterable[dict[str, Any]],
    *,
    case: str | None = None,
    question_id: str | None = None,
    query: str | None = None,
    state: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for pair in pairs:
        if case is not None and case.casefold() not in str(pair["case"]).casefold():
            continue
        if question_id is not None and question_id.casefold() != str(pair["question"]["questionID"]).casefold():
            continue
        if state is not None:
            current = pair_state(pair)
            if state not in (current, str(pair["state"])):
                continue
        if source is not None and source not in (
            str(pair["source"]),
            *[str(answer["source"]) for answer in pair["answers"]],
        ):
            continue
        if query is not None and not _match_query(pair, query):
            continue
        selected.append(pair)
    return selected


def search(
    *,
    checkout: Path | str,
    db: Path | str | None = None,
    case: str | None = None,
    question_id: str | None = None,
    query: str | None = None,
    state: str | None = None,
    source: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Search recorded pairs without creating or modifying the database."""

    root = Path(checkout).expanduser().resolve()
    path = database_path(root, db).resolve()
    filters = {
        "case": case,
        "questionID": question_id,
        "query": query,
        "state": state,
        "source": source,
        "limit": limit,
    }

    if not path.exists():
        return {
            "status": SEARCH_STATUS_NO_DATABASE,
            "detail": "No design history database exists for this checkout yet.",
            "database": {"path": str(path), "exists": False},
            "recorder": None,
            "filters": filters,
            "results": [],
            "omissions": [],
        }

    try:
        connection = _connect_readonly(path)
        try:
            recorder = _latest_recorder_status(connection, str(root))
            pairs = filter_pairs(
                _load_pairs(connection),
                case=case,
                question_id=question_id,
                query=query,
                state=state,
                source=source,
            )
            omissions = [
                {
                    "case": row["design_case"],
                    "formID": row["form_id"],
                    "questionID": row["question_id"],
                    "reason": row["reason"],
                    "recordedAt": row["recorded_at"],
                }
                for row in connection.execute(
                    """
                    SELECT f.design_case, f.form_id, o.question_id, o.reason, o.recorded_at
                    FROM design_omission o JOIN design_form f ON f.id = o.form_pk
                    ORDER BY o.id
                    """
                )
            ]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {
            "status": SEARCH_STATUS_UNAVAILABLE,
            "detail": f"design history is unreadable: {exc}",
            "database": {"path": str(path), "exists": True},
            "recorder": None,
            "filters": filters,
            "results": [],
            "omissions": [],
        }

    if limit is not None:
        pairs = pairs[: max(limit, 0)]

    status = SEARCH_STATUS_OK if pairs else SEARCH_STATUS_NO_MATCHES
    detail = None
    if not pairs and recorder and recorder["status"] in (STATE_STOPPED, STATE_ERROR, STATE_UNCONFIGURED):
        status = SEARCH_STATUS_RECORDING_UNAVAILABLE
        detail = (
            f"Recording is {recorder['status']}; an empty result does not mean the "
            "interview had no answers."
        )
    return {
        "status": status,
        "detail": detail,
        "database": {"path": str(path), "exists": True},
        "recorder": recorder,
        "filters": filters,
        "results": pairs,
        "omissions": omissions,
    }


def status_report(*, checkout: Path | str, db: Path | str | None = None) -> dict[str, Any]:
    root = Path(checkout).expanduser().resolve()
    path = database_path(root, db).resolve()
    report: dict[str, Any] = {
        "checkout": str(root),
        "database": {"path": str(path), "exists": path.exists()},
        "git": None,
        "recorder": None,
        "counts": None,
    }
    try:
        precheck = git_precheck(root, db)
        report["git"] = {
            "ok": True,
            "gitRoot": str(precheck.git_root),
            "ignored": precheck.ignored,
            "tracked": precheck.tracked,
        }
    except GitPrecheckError as exc:
        report["git"] = {
            "ok": False,
            "reason": exc.reason,
            "detail": exc.detail,
            "guidance": exc.guidance,
        }
    if path.exists():
        try:
            connection = _connect_readonly(path)
            try:
                report["recorder"] = _latest_recorder_status(connection, str(root))
                report["counts"] = {
                    "forms": connection.execute("SELECT COUNT(*) FROM design_form").fetchone()[0],
                    "questions": connection.execute("SELECT COUNT(*) FROM design_question").fetchone()[0],
                    "answers": connection.execute("SELECT COUNT(*) FROM design_answer").fetchone()[0],
                    "omissions": connection.execute("SELECT COUNT(*) FROM design_omission").fetchone()[0],
                }
            finally:
                connection.close()
        except sqlite3.Error as exc:
            report["readError"] = str(exc)
    return report


__all__ = [
    "DB_RELATIVE",
    "DesignHistoryError",
    "GitPrecheckError",
    "PrecheckResult",
    "ANSWER_STATES",
    "HOST",
    "IMPORT_HOST",
    "IMPORT_LOG_LIMIT_BYTES",
    "IMPORT_SOURCE",
    "STATE_ANSWERED",
    "STATE_CANCELLED",
    "STATE_CORRECTED",
    "STATE_HELD",
    "STATE_PARTIAL",
    "STATE_UNANSWERED",
    "answer_digest",
    "contains_secret",
    "database_path",
    "filter_pairs",
    "git_precheck",
    "imported_form_state",
    "pair_state",
    "record_import",
    "record_payload",
    "search",
    "status_report",
    "write_session",
]
