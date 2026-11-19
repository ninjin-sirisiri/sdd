"""Import explicitly selected past design interview logs.

The import format is a small JSON document a person writes or extracts by hand.
It is deliberately *not* a transcript: only excerpts (question text, options,
and the answer that was given) are allowed, and an unknown key is refused
rather than ignored.

    {
      "format": "design-history-import",
      "version": 1,
      "title": "Past interview: checkout cancel",         (optional)
      "questions": [
        {
          "question": "Can a deletion be undone?",        (required)
          "id": "checkout-cancel.q1",                     (optional)
          "header": "Delete",                             (optional)
          "options": ["Yes", "No"],                       (optional, ordered)
          "answer": "Yes",                                (required)
          "state": "answered"                             (optional)
        }
      ]
    }

A pair is imported only when its correspondence is provable from the document:

- the question text is present and non-blank;
- every answer element is exactly one of the listed option labels, or the
  question lists no options at all (a free-text question);
- the pair does not carry a credential;
- no other pair in the same document claims the same question ID with
  different content.

Anything else is excluded with a machine-readable ``reason`` and a human
``detail``. No natural-language guessing happens anywhere: a markdown chat log
is not a supported format, and is refused as such.

The source file is opened read-only. Nothing is written until
``design_history.record_import`` runs, which happens only from the explicit
``import-confirm`` command, never from ``import-preview``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from sddlib.design_history import (
    ANSWER_STATES,
    IMPORT_LOG_LIMIT_BYTES,
    IMPORT_SOURCE,
    SEARCH_STATUS_INVALID,
    SEARCH_STATUS_OK,
    SEARCH_STATUS_UNAVAILABLE,
    DesignHistoryError,
    GitPrecheckError,
    answer_digest,
    contains_secret,
    database_path,
    git_precheck,
    imported_form_state,
    record_import,
)

FORMAT_NAME = "design-history-import"
FORMAT_VERSION = 1

STATUS_NOTHING_TO_IMPORT = "nothing-to-import"

TOP_LEVEL_KEYS = ("format", "version", "title", "questions")
PAIR_KEYS = ("question", "id", "header", "options", "answer", "state")

# Exclusion reasons. These are part of the reported contract: Task 3 and a
# person reading the preview both branch on them, so they are plain tokens.
REASON_UNSUPPORTED_FIELD = "unsupported-field"
REASON_INVALID_PAIR_SHAPE = "invalid-pair-shape"
REASON_MISSING_QUESTION = "missing-question"
REASON_MISSING_ANSWER = "missing-answer"
REASON_INVALID_QUESTION_ID = "invalid-question-id"
REASON_AMBIGUOUS_OPTIONS = "ambiguous-options"
REASON_UNSUPPORTED_ANSWER_SHAPE = "unsupported-answer-shape"
REASON_ANSWER_NOT_IN_OPTIONS = "answer-not-in-options"
REASON_UNSUPPORTED_STATE = "unsupported-state"
REASON_SECRET_DETECTED = "secret-detected"
REASON_DUPLICATE_PAIR = "duplicate-pair"
REASON_AMBIGUOUS_QUESTION_ID = "ambiguous-question-id"
REASON_CHANGED_QUESTION = "changed-question"
REASON_EXCERPT_TOO_LONG = "excerpt-too-long"

LOG_REASON_UNREADABLE = "log-unreadable"
LOG_REASON_TOO_LARGE = "log-too-large"
LOG_REASON_NOT_UTF8 = "log-not-utf8"
LOG_REASON_NOT_JSON = "log-not-json"
LOG_REASON_NOT_AN_OBJECT = "log-not-an-object"
LOG_REASON_UNSUPPORTED_FORMAT = "unsupported-format"
LOG_REASON_UNSUPPORTED_VERSION = "unsupported-version"
LOG_REASON_UNSUPPORTED_FIELD = "unsupported-field"
LOG_REASON_NO_QUESTIONS = "no-questions"

# These are excerpts, not prose. A field over its limit is refused rather than
# truncated, because a truncated question would be a different question.
EXCERPT_LIMITS = {
    "question": 2000,
    "header": 200,
    "option": 500,
    "answer": 4000,
    "id": 200,
}


class ImportLogError(DesignHistoryError):
    """The named log as a whole cannot be read as the documented format."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class _PairExcluded(Exception):
    """One pair cannot be imported; carries the exact reported reason."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ImportPair:
    """One excerpt pair that survived validation."""

    index: int
    question_id: str
    text: str
    header: str | None
    options: tuple[str, ...]
    value: Any
    state: str

    @property
    def digest(self) -> str:
        return answer_digest(self.state, self.value)

    def signature(self) -> tuple[str, tuple[str, ...], str]:
        return (self.text, self.options, self.digest)

    def report(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "questionID": self.question_id,
            "question": self.text,
            "header": self.header,
            "options": list(self.options),
            "answer": self.value,
            "state": self.state,
        }

    def store_payload(self, ordinal: int) -> dict[str, Any]:
        return {
            "questionID": self.question_id,
            "ordinal": ordinal,
            "text": self.text,
            "header": self.header,
            "options": list(self.options),
            "state": self.state,
            "value": self.value,
        }


@dataclass
class ImportPlan:
    status: str = SEARCH_STATUS_OK
    detail: str | None = None
    pairs_in_log: int = 0
    importable: list[ImportPair] = field(default_factory=list)
    already: list[ImportPair] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Question IDs: the same shape the live OpenCode adapter derives
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    """NFKC, lowercase, letters/digits only, ``-`` between runs, max 40.

    This mirrors ``questionIDFor()`` in
    ``adapters/opencode/design_history_plugin.ts`` so an imported pair is
    addressable with the same ID a live presentation would have used.
    """

    normalized = unicodedata.normalize("NFKC", text).lower()
    dashed = "".join(character if character.isalnum() else "-" for character in normalized)
    collapsed = re.sub(r"-+", "-", dashed).strip("-")
    # The adapter's ``.slice(0, 40)`` counts UTF-16 code units, so cut the same
    # way and never split a surrogate pair.
    encoded = collapsed.encode("utf-16-le")[:80]
    return encoded.decode("utf-16-le", errors="ignore")


def question_id_for(
    case: str,
    text: str,
    ordinal: int,
    explicit: str | None = None,
) -> str:
    """Derive an imported question ID, preferring an explicit one."""

    if explicit:
        return explicit
    slug = _slug(text)
    base = f"{case}.q{ordinal + 1}"
    return f"{base}-{slug}" if slug else base


# ---------------------------------------------------------------------------
# Reading the named document (read-only)
# ---------------------------------------------------------------------------


def _read_document(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read and parse one user-named log. Never writes to it."""

    resolved = path.expanduser().resolve()
    info: dict[str, Any] = {"path": str(resolved), "name": resolved.name}
    if not resolved.is_file():
        raise ImportLogError(
            LOG_REASON_UNREADABLE,
            f"import log {resolved} is not a readable file; name the local log explicitly",
        )
    data = resolved.read_bytes()
    info["bytes"] = len(data)
    info["sha256"] = hashlib.sha256(data).hexdigest()
    if len(data) > IMPORT_LOG_LIMIT_BYTES:
        raise ImportLogError(
            LOG_REASON_TOO_LARGE,
            f"import log {resolved} is {len(data)} bytes, over the "
            f"{IMPORT_LOG_LIMIT_BYTES}-byte limit; this format holds excerpts, not a transcript"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportLogError(
            LOG_REASON_NOT_UTF8, f"import log {resolved} is not UTF-8 text"
        ) from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportLogError(
            LOG_REASON_NOT_JSON,
            f"import log {resolved} is not the JSON import format ({exc}); "
            "a chat transcript is not a supported format",
        ) from exc
    if not isinstance(document, dict):
        raise ImportLogError(
            LOG_REASON_NOT_AN_OBJECT,
            f"import log {resolved} must be one JSON object with a 'questions' list",
        )
    return document, info


def _check_document(document: dict[str, Any]) -> None:
    extra = sorted(set(document) - set(TOP_LEVEL_KEYS))
    if extra:
        raise ImportLogError(
            LOG_REASON_UNSUPPORTED_FIELD,
            "import log has unsupported top-level field(s): "
            + ", ".join(extra)
            + "; allowed fields are "
            + ", ".join(TOP_LEVEL_KEYS)
        )
    if document.get("format") != FORMAT_NAME:
        raise ImportLogError(
            LOG_REASON_UNSUPPORTED_FORMAT,
            "import log is not the documented format: 'format' must be "
            f"{FORMAT_NAME!r}, got {document.get('format')!r}"
        )
    version = document.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FORMAT_VERSION:
        raise ImportLogError(
            LOG_REASON_UNSUPPORTED_VERSION,
            f"unsupported import log version {version!r}; this tool reads version {FORMAT_VERSION}",
        )
    if "title" in document and not isinstance(document.get("title"), str):
        raise ImportLogError(
            LOG_REASON_UNSUPPORTED_FIELD, "import log 'title' must be a string"
        )
    if isinstance(document.get("title"), str) and len(document["title"].strip()) > 200:
        raise ImportLogError(
            LOG_REASON_UNSUPPORTED_FIELD,
            "import log 'title' must be a short label of at most 200 characters; "
            "this format stores excerpts, not prose",
        )
    questions = document.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ImportLogError(
            LOG_REASON_NO_QUESTIONS, "import log 'questions' must be a non-empty list"
        )


def _required_case(case: str | None) -> str:
    if case is None or not case.strip():
        raise DesignHistoryError("import requires --case naming the design case")
    cleaned = case.strip()
    if any(character in cleaned for character in ("\n", "\r", "\t", "\0")):
        raise DesignHistoryError("--case must not contain control characters")
    return cleaned


def form_identity(case: str) -> dict[str, str]:
    """One import bucket per design case.

    Identity deliberately excludes the log path: the same excerpt pair imported
    twice — from the same file, a copy, or a second log — resolves to the same
    question and answer digest, so it cannot be duplicated. A different answer
    for an already imported question becomes a new revision, exactly like a
    live correction.
    """

    return {"sessionID": f"import:{case}", "formID": f"import:{case}"}


# ---------------------------------------------------------------------------
# Validating one pair
# ---------------------------------------------------------------------------


def _string_field(pair: dict[str, Any], key: str) -> str | None:
    value = pair.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _PairExcluded(
            REASON_INVALID_PAIR_SHAPE,
            f"'{key}' must be a string, not {type(value).__name__}",
        )
    cleaned = value.strip()
    return cleaned or None


def _options_field(pair: dict[str, Any]) -> tuple[str, ...]:
    raw = pair.get("options")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _PairExcluded(
            REASON_INVALID_PAIR_SHAPE, "'options' must be a list of option labels"
        )
    labels: list[str] = []
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            raise _PairExcluded(
                REASON_INVALID_PAIR_SHAPE, "'options' must contain non-empty strings"
            )
        labels.append(entry.strip())
    if len(set(labels)) != len(labels):
        raise _PairExcluded(
            REASON_AMBIGUOUS_OPTIONS,
            "the same option label is listed twice; which one was selected cannot be proven",
        )
    return tuple(labels)


def _require_excerpt(kind: str, value: str) -> None:
    limit = EXCERPT_LIMITS[kind]
    if len(value) > limit:
        raise _PairExcluded(
            REASON_EXCERPT_TOO_LONG,
            f"the {kind} is {len(value)} characters, over the {limit}-character excerpt limit; "
            "this format stores excerpts, not transcripts",
        )


def _answer_field(pair: dict[str, Any]) -> Any:
    if "answer" not in pair or pair.get("answer") is None:
        raise _PairExcluded(REASON_MISSING_ANSWER, "the pair has no answer")
    raw = pair["answer"]
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            raise _PairExcluded(REASON_MISSING_ANSWER, "the answer is blank")
        return cleaned
    if isinstance(raw, list):
        if not raw:
            raise _PairExcluded(REASON_MISSING_ANSWER, "the answer list is empty")
        values: list[str] = []
        for entry in raw:
            if not isinstance(entry, str) or not entry.strip():
                raise _PairExcluded(
                    REASON_UNSUPPORTED_ANSWER_SHAPE,
                    "a multi-select answer must be a list of non-empty strings",
                )
            values.append(entry.strip())
        if len(set(values)) != len(values):
            raise _PairExcluded(
                REASON_UNSUPPORTED_ANSWER_SHAPE, "the answer list repeats a value"
            )
        return values
    raise _PairExcluded(
        REASON_UNSUPPORTED_ANSWER_SHAPE,
        f"the answer must be a string or a list of strings, not {type(raw).__name__}",
    )


def _validate_pair(raw: Any, index: int, case: str) -> ImportPair:
    if not isinstance(raw, dict):
        raise _PairExcluded(REASON_INVALID_PAIR_SHAPE, f"pair #{index} is not a JSON object")
    extra = sorted(set(raw) - set(PAIR_KEYS))
    if extra:
        raise _PairExcluded(
            REASON_UNSUPPORTED_FIELD,
            f"pair #{index} carries unsupported field(s): "
            + ", ".join(extra)
            + "; allowed fields are "
            + ", ".join(PAIR_KEYS),
        )

    text = _string_field(raw, "question")
    if text is None:
        raise _PairExcluded(REASON_MISSING_QUESTION, f"pair #{index} has no question text")
    _require_excerpt("question", text)
    header = _string_field(raw, "header")
    if header is not None:
        _require_excerpt("header", header)
    explicit = _string_field(raw, "id")
    options = _options_field(raw)
    for option in options:
        _require_excerpt("option", option)
    value = _answer_field(raw)
    for entry in value if isinstance(value, list) else [value]:
        _require_excerpt("answer", entry)

    state = raw.get("state", "answered")
    if not isinstance(state, str):
        raise _PairExcluded(REASON_INVALID_PAIR_SHAPE, "'state' must be a string")
    state = state.strip() or "answered"
    if state not in ANSWER_STATES:
        raise _PairExcluded(
            REASON_UNSUPPORTED_STATE,
            f"state {state!r} is not an answer; only "
            + ", ".join(ANSWER_STATES)
            + " pairs can be imported, and absence is never imported as agreement",
        )

    # Shape is settled, so the excerpt is safe to inspect for credentials.
    answer_text = " / ".join(value) if isinstance(value, list) else value
    haystack = "\n".join(
        part for part in (text, header or "", explicit or "", *options, answer_text) if part
    )
    if contains_secret(haystack):
        raise _PairExcluded(
            REASON_SECRET_DETECTED,
            "the pair contains a credential; it was not imported and its text was not stored",
        )

    if explicit is not None:
        if any(character.isspace() for character in explicit):
            raise _PairExcluded(
                REASON_INVALID_QUESTION_ID,
                "an explicit 'id' must be one token without whitespace",
            )
        _require_excerpt("id", explicit)

    values = value if isinstance(value, list) else [value]
    if options:
        missing = [entry for entry in values if entry not in options]
        if missing:
            raise _PairExcluded(
                REASON_ANSWER_NOT_IN_OPTIONS,
                "the answer is not one of the listed options ("
                + ", ".join(repr(option) for option in options)
                + "), so the question/option/answer correspondence cannot be proven",
            )
    elif isinstance(value, list):
        raise _PairExcluded(
            REASON_UNSUPPORTED_ANSWER_SHAPE,
            "a multi-select answer needs a listed 'options' array to prove each selected value",
        )

    return ImportPair(
        index=index,
        question_id=question_id_for(case, text, index, explicit),
        text=text,
        header=header,
        options=options,
        value=value,
        state=state,
    )


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def _plan(
    document: dict[str, Any],
    *,
    case: str,
    checkout: Path,
    db: str | None,
) -> ImportPlan:
    questions = document["questions"]
    identity = form_identity(case)
    existing = imported_form_state(
        checkout,
        db,
        session_id=identity["sessionID"],
        form_id=identity["formID"],
    )
    if existing is None:
        return ImportPlan(
            status=SEARCH_STATUS_UNAVAILABLE,
            detail="the design history database exists but cannot be read; "
            "an empty result does not mean every pair is new",
            pairs_in_log=len(questions),
        )

    plan = ImportPlan(pairs_in_log=len(questions))
    valid: list[ImportPair] = []
    for index, raw in enumerate(questions):
        try:
            valid.append(_validate_pair(raw, index, case))
        except _PairExcluded as exc:
            plan.excluded.append(
                {
                    "index": index,
                    "reason": exc.reason,
                    "detail": exc.detail,
                    "questionID": None,
                }
            )

    # Group by the ID the store would use: two pairs claiming one ID are only
    # importable if they are the same pair. Otherwise *both* are ambiguous —
    # keeping the first and dropping the rest would be a guess.
    groups: dict[str, list[ImportPair]] = {}
    for pair in valid:
        groups.setdefault(pair.question_id, []).append(pair)

    stored_questions: dict[str, dict[str, Any]] = existing["questions"]
    stored_digests: set[tuple[str, str]] = existing["digests"]
    for question_id, group in groups.items():
        first = group[0]
        if any(pair.signature() != first.signature() for pair in group[1:]):
            for pair in group:
                plan.excluded.append(
                    {
                        "index": pair.index,
                        "reason": REASON_AMBIGUOUS_QUESTION_ID,
                        "detail": f"{len(group)} pairs claim question ID {question_id!r} "
                        "with different content, so none of them can be imported without guessing",
                        "questionID": question_id,
                    }
                )
            continue
        for pair in group[1:]:
            plan.excluded.append(
                {
                    "index": pair.index,
                    "reason": REASON_DUPLICATE_PAIR,
                    "detail": f"identical to pair #{first.index} in this log; one pair is imported",
                    "questionID": question_id,
                }
            )
        previous = stored_questions.get(question_id)
        if previous is not None and (
            previous["text"] != first.text or previous["options"] != first.options
        ):
            plan.excluded.append(
                {
                    "index": first.index,
                    "reason": REASON_CHANGED_QUESTION,
                    "detail": f"question ID {question_id!r} was already imported for this "
                    "case with different question text or options; re-importing would "
                    "change the recorded question, which an import must not do",
                    "questionID": question_id,
                }
            )
            continue
        if (question_id, first.digest) in stored_digests:
            plan.already.append(first)
        else:
            plan.importable.append(first)

    plan.importable.sort(key=lambda pair: pair.index)
    plan.already.sort(key=lambda pair: pair.index)
    plan.excluded.sort(key=lambda entry: (entry["index"] is None, entry["index"] or 0))
    return plan


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _git_state(checkout: Path, db: str | None) -> dict[str, Any]:
    try:
        precheck = git_precheck(checkout, db)
    except GitPrecheckError as exc:
        return {
            "ok": False,
            "reason": exc.reason,
            "detail": exc.detail,
            "guidance": exc.guidance,
        }
    return {
        "ok": True,
        "gitRoot": str(precheck.git_root),
        "ignored": precheck.ignored,
        "tracked": precheck.tracked,
    }


def _report(
    *,
    status: str,
    action: str,
    detail: str | None,
    reason: str | None = None,
    log: dict[str, Any],
    case: str | None,
    checkout: Path,
    db: str | None,
    document: dict[str, Any] | None = None,
    pairs_in_log: int = 0,
    form: dict[str, str] | None = None,
    importable: list[dict[str, Any]] | None = None,
    already: list[dict[str, Any]] | None = None,
    excluded: list[dict[str, Any]] | None = None,
    recorded: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = database_path(checkout, db).resolve()
    title = None
    if document is not None and isinstance(document.get("title"), str):
        title = document["title"].strip() or None
    payload: dict[str, Any] = {
        "status": status,
        "action": action,
        "reason": reason,
        "detail": detail,
        "log": log,
        "case": case,
        "title": title,
        "form": form,
        "database": {"path": str(path), "exists": path.exists()},
        "git": _git_state(checkout, db),
        "importable": importable or [],
        "alreadyRecorded": already or [],
        "excluded": excluded or [],
        "counts": {
            "pairsInLog": pairs_in_log,
            "importable": len(importable or []),
            "alreadyRecorded": len(already or []),
            "excluded": len(excluded or []),
            "recorded": len(recorded or []),
        },
    }
    if recorded is not None:
        payload["recorded"] = recorded
    return payload


def _readable(
    *,
    checkout: Path,
    log: str | Path,
    case: str | None,
    db: str | None,
    action: str,
) -> tuple[dict[str, Any], dict[str, Any], str] | dict[str, Any]:
    """Shared read step. Returns a finished error report when the log is invalid."""

    root = checkout.expanduser().resolve()
    log_path = Path(log)
    try:
        case_name = _required_case(case)
        document, info = _read_document(log_path)
        _check_document(document)
    except ImportLogError as exc:
        return _report(
            status=SEARCH_STATUS_INVALID,
            action=action,
            reason=exc.reason,
            detail=exc.detail,
            log={"path": str(log_path.expanduser().resolve())},
            case=case,
            checkout=root,
            db=db,
        )
    except DesignHistoryError as exc:
        return _report(
            status=SEARCH_STATUS_INVALID,
            action=action,
            reason=LOG_REASON_UNREADABLE,
            detail=str(exc),
            log={"path": str(log_path.expanduser().resolve())},
            case=case,
            checkout=root,
            db=db,
        )
    return document, info, case_name


# ---------------------------------------------------------------------------
# Public commands
# ---------------------------------------------------------------------------


def preview_import(
    *,
    checkout: Path | str,
    log: str | Path,
    case: str | None,
    db: str | None = None,
) -> dict[str, Any]:
    """Report what would be imported. Reads the log and the database only."""

    root = Path(checkout).expanduser().resolve()
    read = _readable(checkout=root, log=log, case=case, db=db, action="preview")
    if isinstance(read, dict):
        return read
    document, info, case_name = read
    plan = _plan(document, case=case_name, checkout=root, db=db)
    form = form_identity(case_name)
    if plan.status == SEARCH_STATUS_UNAVAILABLE:
        return _report(
            status=plan.status,
            action="preview",
            detail=plan.detail,
            log=info,
            case=case_name,
            checkout=root,
            db=db,
            document=document,
            pairs_in_log=plan.pairs_in_log,
            form=form,
            excluded=plan.excluded,
        )

    status = SEARCH_STATUS_OK
    detail = None
    if not plan.importable and not plan.already:
        status = STATUS_NOTHING_TO_IMPORT
        detail = "no pair in this log can be imported; every pair has a stated reason"
    elif not plan.importable:
        detail = "every importable pair is already recorded; nothing would be written"
    return _report(
        status=status,
        action="preview",
        detail=detail,
        log=info,
        case=case_name,
        checkout=root,
        db=db,
        document=document,
        pairs_in_log=plan.pairs_in_log,
        form=form,
        importable=[pair.report() for pair in plan.importable],
        already=[pair.report() for pair in plan.already],
        excluded=plan.excluded,
    )


def confirm_import(
    *,
    checkout: Path | str,
    log: str | Path,
    case: str | None,
    db: str | None = None,
) -> dict[str, Any]:
    """Write the pairs ``preview_import`` reported. The only writing command."""

    root = Path(checkout).expanduser().resolve()
    read = _readable(checkout=root, log=log, case=case, db=db, action="confirm")
    if isinstance(read, dict):
        return read
    document, info, case_name = read
    plan = _plan(document, case=case_name, checkout=root, db=db)
    form = form_identity(case_name)
    if plan.status == SEARCH_STATUS_UNAVAILABLE:
        return _report(
            status=plan.status,
            action="confirm",
            detail=plan.detail,
            log=info,
            case=case_name,
            checkout=root,
            db=db,
            document=document,
            pairs_in_log=plan.pairs_in_log,
            form=form,
            excluded=plan.excluded,
            recorded=[],
        )
    if not plan.importable:
        status = SEARCH_STATUS_OK if plan.already else STATUS_NOTHING_TO_IMPORT
        detail = (
            "every importable pair is already recorded; nothing was written"
            if plan.already
            else "no pair in this log can be imported; every pair has a stated reason"
        )
        return _report(
            status=status,
            action="confirm",
            detail=detail,
            log=info,
            case=case_name,
            checkout=root,
            db=db,
            document=document,
            pairs_in_log=plan.pairs_in_log,
            form=form,
            already=[pair.report() for pair in plan.already],
            excluded=plan.excluded,
            recorded=[],
        )

    result = record_import(
        {
            "checkout": str(root),
            "db": db,
            "sessionID": form["sessionID"],
            "formID": form["formID"],
            "case": case_name,
            "title": (document.get("title") or "").strip()
            or f"Imported past log: {Path(log).name}",
            "source": IMPORT_SOURCE,
            "pairs": [pair.store_payload(pair.index) for pair in plan.importable],
            "metadata": {
                "log": info.get("name"),
                "sha256": info.get("sha256"),
                "bytes": info.get("bytes"),
            },
            "provenance": f"import:{info.get('sha256')}",
        }
    )

    stored = set(result["recorded"])
    known = set(result["alreadyRecorded"])
    planned = [pair.report() for pair in plan.importable]
    recorded = [pair.report() for pair in plan.importable if pair.question_id in stored]
    already = [pair.report() for pair in plan.already] + [
        pair.report() for pair in plan.importable if pair.question_id in known
    ]
    excluded = list(plan.excluded) + [
        {
            "index": None,
            "reason": REASON_SECRET_DETECTED,
            "detail": "the pair contains a credential; it was not imported and its text was not stored",
            "questionID": question_id,
        }
        for question_id in result.get("omitted", ())
    ]
    detail = (
        f"saved {len(recorded)} pair(s) from the named log"
        if recorded
        else "nothing new was written; every pair was already recorded"
    )
    return _report(
        status=SEARCH_STATUS_OK,
        action="confirm",
        detail=detail,
        log=info,
        case=case_name,
        checkout=root,
        db=db,
        document=document,
        pairs_in_log=plan.pairs_in_log,
        form=form,
        importable=planned,
        already=already,
        excluded=excluded,
        recorded=recorded,
    )


__all__ = [
    "FORMAT_NAME",
    "ImportLogError",
    "FORMAT_VERSION",
    "PAIR_KEYS",
    "STATUS_NOTHING_TO_IMPORT",
    "TOP_LEVEL_KEYS",
    "ImportPair",
    "ImportPlan",
    "confirm_import",
    "form_identity",
    "preview_import",
    "question_id_for",
]
