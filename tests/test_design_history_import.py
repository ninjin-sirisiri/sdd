"""Import of explicitly selected past design interview logs.

The tests below pin the parts a later phase depends on: the format, the
exclusion reasons, preview/confirm separation, deduplication, and that only
excerpts of the named log reach the database.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from sddlib import design_history as dh
from sddlib import design_history_import as imp

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CLI = SCRIPTS / "design-history"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PYTHON = sys.executable


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "base")
    (repo / ".gitignore").write_text(".sdd/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "ignore")
    return repo


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(CLI), *args], cwd=cwd, text=True, capture_output=True
    )


def write_log(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def log_document(*questions: dict, title: str = "Past interview") -> dict:
    return {
        "format": imp.FORMAT_NAME,
        "version": imp.FORMAT_VERSION,
        "title": title,
        "questions": list(questions),
    }


def question(text: str, answer, **extra) -> dict:
    return {"question": text, "answer": answer, **extra}


def db_of(repo: Path) -> Path:
    return repo / ".sdd" / "design-history.sqlite3"


def row_counts(repo: Path) -> dict[str, int]:
    with sqlite3.connect(db_of(repo)) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("design_form", "design_question", "design_answer", "design_omission")
        }


# --- Format and question IDs ---------------------------------------------


def test_example_fixture_is_the_documented_format() -> None:
    document = json.loads((FIXTURES / "design-history-import.example.json").read_text(encoding="utf-8"))
    assert document["format"] == imp.FORMAT_NAME
    assert document["version"] == imp.FORMAT_VERSION
    assert len(document["questions"]) == 3
    assert set(document["questions"][0]) <= set(imp.PAIR_KEYS)


def test_question_ids_match_the_live_adapter_shape() -> None:
    explicit = imp.question_id_for("checkout-cancel", "削除は取り消せますか", 0, "checkout-cancel.q1")
    assert explicit == "checkout-cancel.q1"
    derived = imp.question_id_for("checkout-cancel", "削除は取り消せますか", 0)
    assert derived == "checkout-cancel.q1-削除は取り消せますか"
    # NFKC + punctuation collapse: full-width and ASCII punctuation agree.
    assert imp.question_id_for("c", "Is it OK？", 1) == imp.question_id_for("c", "Is it OK?", 1)
    assert imp.question_id_for("c", "とても長い質問" * 20, 2).count("q3-") == 1


def test_question_ids_agree_with_the_adapter_test_vectors() -> None:
    """The same vectors the OpenCode adapter pins in TypeScript.

    Keep this in step with ``adapters/opencode/design_history_plugin.test.ts``
    (``questionIDFor``); a mismatch would make an imported pair unaddressable
    by the ID a live presentation would have used.
    """

    assert imp.question_id_for("case-a", "配信方法は?", 0) == "case-a.q1-配信方法は"
    assert imp.question_id_for("case-a", "Rollout strategy?", 1) == "case-a.q2-rollout-strategy"
    assert imp.question_id_for("case-a", "x", 0, "explicit") == "explicit"
    # The adapter truncates with JS String#slice, which counts UTF-16 code
    # units; astral plane letters must truncate identically (after lowercasing).
    astral = "\U00010400" * 30
    astral_slug = astral.lower()[:20]
    assert imp.question_id_for("c", astral, 0) == "c.q1-" + astral_slug
    assert len(imp.question_id_for("c", astral, 0)) == len("c.q1-") + 20


# --- Preview -------------------------------------------------------------


def test_preview_writes_nothing_and_reports_pairs(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"]),
            question("対象外はありますか", "監査ログだけ残す"),
        ),
    )
    result = run_cli(repo, "import-preview", "--log", str(log), "--case", "checkout-cancel")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["action"] == "preview"
    assert payload["status"] == "ok"
    assert [pair["questionID"] for pair in payload["importable"]] == [
        "checkout-cancel.q1-削除は取り消せますか",
        "checkout-cancel.q2-対象外はありますか",
    ]
    assert payload["excluded"] == []
    assert payload["database"]["exists"] is False
    assert not (repo / ".sdd").exists()
    assert payload["log"]["sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()


def test_preview_excludes_ambiguous_and_states_the_reason(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            # The answer is not one of the listed options: correspondence unknown.
            question("削除の確認は必要ですか", "たぶん必要", options=["必要", "不要"]),
            # The same explicit ID is used for two different questions.
            question("最初の質問", "はい", id="case.q1", options=["はい", "いいえ"]),
            question("別の質問", "いいえ", id="case.q1", options=["はい", "いいえ"]),
            # One option label appears twice, so the selection is not provable.
            question("どちらですか", "A", options=["A", "A", "B"]),
            # State that is an absence, not an answer.
            question("未回答の質問", "x", state="unanswered"),
            # An extra field is unsupported rather than silently dropped.
            {**question("余分な項目", "はい"), "transcript": "full chat log"},
        ),
    )
    result = run_cli(repo, "import-preview", "--log", str(log), "--case", "case")
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["status"] == imp.STATUS_NOTHING_TO_IMPORT
    reasons = [(entry["index"], entry["reason"]) for entry in payload["excluded"]]
    assert reasons == [
        (0, "answer-not-in-options"),
        (1, "ambiguous-question-id"),
        (2, "ambiguous-question-id"),
        (3, "ambiguous-options"),
        (4, "unsupported-state"),
        (5, "unsupported-field"),
    ]
    assert all(entry["detail"] for entry in payload["excluded"])
    assert "not one of the listed options" in payload["excluded"][0]["detail"]
    # The offending field is named so a person can fix the log, but its value
    # (a transcript excerpt) is never echoed.
    assert "unsupported field(s): transcript" in payload["excluded"][5]["detail"]
    assert "full chat log" not in json.dumps(payload, ensure_ascii=False)
    assert not (repo / ".sdd").exists()


def test_preview_reports_secret_pairs_without_storing_their_text(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"]),
            question(f"API key は {secret} ですか", "はい", options=["はい", "いいえ"]),
            question("接続先はどこですか", f"password: {secret}"),
        ),
    )
    result = run_cli(repo, "import-preview", "--log", str(log), "--case", "case")
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert len(payload["importable"]) == 1
    secret_entries = [entry for entry in payload["excluded"] if entry["reason"] == "secret-detected"]
    assert [entry["index"] for entry in secret_entries] == [1, 2]
    assert secret not in json.dumps(payload, ensure_ascii=False)
    assert not (repo / ".sdd").exists()


def test_preview_distinguishes_unsupported_formats(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    markdown = tmp_path / "chat.md"
    markdown.write_text("# Session\n\nQ: 削除は取り消せますか\nA: 取り消せる\n", encoding="utf-8")
    result = run_cli(repo, "import-preview", "--log", str(markdown), "--case", "case")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid"
    assert payload["reason"] == "log-not-json"
    assert "not the JSON import format" in payload["detail"]
    assert "chat transcript is not a supported format" in payload["detail"]

    wrong_version = write_log(
        tmp_path / "v2.json",
        {"format": imp.FORMAT_NAME, "version": 2, "questions": [question("q", "a")]},
    )
    result = run_cli(repo, "import-preview", "--log", str(wrong_version), "--case", "case")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "unsupported-version"
    assert "unsupported import log version 2" in json.loads(result.stdout)["detail"]

    other_format = write_log(
        tmp_path / "other.json",
        {"format": "chat-log", "version": 1, "questions": [question("q", "a")]},
    )
    result = run_cli(repo, "import-preview", "--log", str(other_format), "--case", "case")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "unsupported-format"
    assert "not the documented format" in json.loads(result.stdout)["detail"]

    missing = run_cli(repo, "import-preview", "--log", str(tmp_path / "nope.json"), "--case", "case")
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["reason"] == "log-unreadable"
    assert "not a readable file" in json.loads(missing.stdout)["detail"]
    assert not (repo / ".sdd").exists()


def test_preview_requires_a_named_log_and_case(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    no_case = run_cli(repo, "import-preview", "--log", str(tmp_path / "log.json"))
    assert no_case.returncode == 2
    assert "--case" in json.loads(no_case.stdout)["detail"]
    no_log = run_cli(repo, "import-preview", "--case", "case")
    assert no_log.returncode == 2
    assert "--log" in json.loads(no_log.stdout)["detail"]
    unexpected = run_cli(repo, "import-preview", "--case", "case", "--log", "x", "extra")
    assert unexpected.returncode == 2
    assert not (repo / ".sdd").exists()


def test_preview_and_confirm_agree_on_the_same_pairs(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        json.loads((FIXTURES / "design-history-import.mixed.json").read_text(encoding="utf-8")),
    )
    preview = json.loads(run_cli(repo, "import-preview", "--log", str(log), "--case", "checkout-cancel").stdout)
    confirmed = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "checkout-cancel").stdout)
    assert [pair["questionID"] for pair in confirmed["recorded"]] == [
        pair["questionID"] for pair in preview["importable"]
    ]
    assert confirmed["counts"]["recorded"] == preview["counts"]["importable"]
    assert confirmed["counts"]["importable"] == preview["counts"]["importable"]
    assert confirmed["counts"]["excluded"] == preview["counts"]["excluded"]


# --- Confirm -------------------------------------------------------------


def test_confirm_writes_and_runs_through_normal_search(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"]),
            question("対象外はありますか", "監査ログだけ残す"),
        ),
    )
    assert not db_of(repo).exists()
    result = run_cli(repo, "import-confirm", "--log", str(log), "--case", "checkout-cancel")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["action"] == "confirm"
    assert [pair["questionID"] for pair in payload["recorded"]] == [
        "checkout-cancel.q1-削除は取り消せますか",
        "checkout-cancel.q2-対象外はありますか",
    ]

    search = run_cli(repo, "search")
    assert search.returncode == 0
    found = json.loads(search.stdout)
    assert found["status"] == "ok"
    assert len(found["results"]) == 2
    first = found["results"][0]
    assert first["case"] == "checkout-cancel"
    assert first["question"]["questionID"] == "checkout-cancel.q1-削除は取り消せますか"
    assert [option["label"] for option in first["question"]["options"]] == ["取り消せる", "取り消せない"]
    assert first["answers"][0]["value"] == "取り消せる"

    by_keyword = json.loads(run_cli(repo, "search", "--query", "監査").stdout)
    assert [pair["answers"][0]["text"] for pair in by_keyword["results"]] == ["監査ログだけ残す"]
    by_id = json.loads(
        run_cli(repo, "search", "--question-id", "checkout-cancel.q1-削除は取り消せますか").stdout
    )
    assert len(by_id["results"]) == 1


def test_imported_records_are_marked_as_import_derived(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(tmp_path / "log.json", log_document(question("削除は取り消せますか", "取り消せる")))
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "checkout-cancel")
    pair = json.loads(run_cli(repo, "search").stdout)["results"][0]
    assert pair["source"] == dh.IMPORT_SOURCE
    assert pair["host"] == dh.IMPORT_HOST
    assert pair["answers"][0]["source"] == dh.IMPORT_SOURCE
    assert pair["answers"][0]["delivery"] == "import"
    assert pair["source"] != "opencode.form.created"


def test_reimport_does_not_duplicate_pairs(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"]),
            question("対象外はありますか", "監査ログだけ残す"),
        ),
    )
    first = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "case").stdout)
    assert first["counts"]["recorded"] == 2
    after_first = row_counts(repo)

    again = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "case").stdout)
    assert again["status"] == "ok"
    assert again["counts"]["recorded"] == 0
    assert again["counts"]["alreadyRecorded"] == 2
    assert "already recorded" in again["detail"]
    assert row_counts(repo) == after_first

    preview = json.loads(run_cli(repo, "import-preview", "--log", str(log), "--case", "case").stdout)
    assert preview["importable"] == []
    assert len(preview["alreadyRecorded"]) == 2
    assert row_counts(repo) == after_first


def test_reimport_of_a_changed_answer_is_a_new_revision(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(tmp_path / "log.json", log_document(question("削除は取り消せますか", "取り消せる", id="case.q1")))
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    write_log(tmp_path / "log.json", log_document(question("削除は取り消せますか", "取り消せない", id="case.q1")))
    second = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "case").stdout)
    assert second["counts"]["recorded"] == 1
    answers = json.loads(run_cli(repo, "search", "--question-id", "case.q1").stdout)["results"][0]["answers"]
    assert [answer["value"] for answer in answers] == ["取り消せる", "取り消せない"]
    assert [answer["revision"] for answer in answers] == [1, 2]


def test_reimport_cannot_silently_change_a_question(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(question("削除は取り消せますか", "取り消せる", id="case.q1", options=["取り消せる", "取り消せない"])),
    )
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    write_log(
        tmp_path / "log.json",
        log_document(question("別の質問に変わった", "取り消せる", id="case.q1", options=["取り消せる"])),
    )
    preview = json.loads(run_cli(repo, "import-preview", "--log", str(log), "--case", "case").stdout)
    assert preview["status"] == imp.STATUS_NOTHING_TO_IMPORT
    assert preview["excluded"][0]["reason"] == "changed-question"
    confirmed = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "case").stdout)
    assert confirmed["counts"]["recorded"] == 0
    pair = json.loads(run_cli(repo, "search", "--question-id", "case.q1").stdout)["results"][0]
    assert pair["question"]["text"] == "削除は取り消せますか"


def test_secret_pair_is_omitted_and_its_text_is_never_stored(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"]),
            question("接続先はどこですか", f"password: {secret}"),
            question(f"API key は {secret} ですか", "はい", options=["はい", "いいえ"]),
        ),
    )
    result = json.loads(run_cli(repo, "import-confirm", "--log", str(log), "--case", "case").stdout)
    assert result["counts"]["recorded"] == 1
    assert [entry["index"] for entry in result["excluded"] if entry["reason"] == "secret-detected"] == [1, 2]
    assert secret not in json.dumps(result, ensure_ascii=False)

    search = json.loads(run_cli(repo, "search").stdout)
    assert len(search["results"]) == 1
    assert secret.encode() not in db_of(repo).read_bytes()
    assert secret not in json.dumps(search, ensure_ascii=False)


def test_only_excerpts_are_stored(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question(
                "削除は取り消せますか",
                "取り消せる",
                header="削除",
                options=["取り消せる", "取り消せない"],
            ),
        ),
    )
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    with sqlite3.connect(db_of(repo)) as connection:
        form = connection.execute(
            "SELECT design_case, title, host, source, state, metadata_json FROM design_form"
        ).fetchall()
        questions = connection.execute(
            "SELECT question_id, text, header, description, options_json, field_key "
            "FROM design_question"
        ).fetchall()
        answers = connection.execute(
            "SELECT state, answer_json, answer_text, source, delivery, event_id "
            "FROM design_answer"
        ).fetchall()
        omissions = connection.execute("SELECT COUNT(*) FROM design_omission").fetchone()[0]

    import json as _json

    assert form == [
        (
            "case",
            "Past interview",
            dh.IMPORT_HOST,
            dh.IMPORT_SOURCE,
            "answered",
            _json.dumps(
                {
                    "import": {
                        "log": "log.json",
                        "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                        "bytes": log.stat().st_size,
                    }
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    ]
    assert questions == [
        (
            "case.q1-削除は取り消せますか",
            "削除は取り消せますか",
            "削除",
            None,
            _json.dumps(
                [
                    {"ordinal": 0, "value": "取り消せる", "label": "取り消せる"},
                    {"ordinal": 1, "value": "取り消せない", "label": "取り消せない"},
                ],
                ensure_ascii=False,
            ),
            None,
        )
    ]
    # The provenance token is the log's own digest — an ID, not transcript text.
    assert answers == [
        (
            "answered",
            '"取り消せる"',
            "取り消せる",
            dh.IMPORT_SOURCE,
            "import",
            f"import:{hashlib.sha256(log.read_bytes()).hexdigest()}",
        )
    ]
    assert omissions == 0

    raw = db_of(repo).read_bytes()
    for marker in (b"system-reminder", b"tool_use", b"tool_result", b"attachment"):
        assert marker not in raw


def test_preview_leaves_an_existing_database_byte_identical(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("削除は取り消せますか", "取り消せる"),
            question("対象外はありますか", "監査ログだけ残す"),
        ),
    )
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    before = db_of(repo).read_bytes()
    # A second named log with new pairs must still write nothing on preview.
    other = write_log(tmp_path / "other.json", log_document(question("別の質問", "はい")))
    preview = run_cli(repo, "import-preview", "--log", str(other), "--case", "other")
    assert preview.returncode == 0
    assert json.loads(preview.stdout)["counts"]["importable"] == 1
    assert db_of(repo).read_bytes() == before
    assert len(json.loads(run_cli(repo, "search").stdout)["results"]) == 2


def test_source_log_is_byte_identical_after_preview_and_confirm(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"])),
    )
    before = hashlib.sha256(log.read_bytes()).hexdigest()
    stat_before = log.stat().st_mtime_ns
    run_cli(repo, "import-preview", "--log", str(log), "--case", "case")
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    assert hashlib.sha256(log.read_bytes()).hexdigest() == before
    assert log.stat().st_mtime_ns == stat_before


# --- Store-level behaviour and failure states ----------------------------


def test_import_respects_the_git_precheck(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".gitignore").write_text("")
    log = write_log(tmp_path / "log.json", log_document(question("削除は取り消せますか", "取り消せる")))
    preview = json.loads(run_cli(repo, "import-preview", "--log", str(log), "--case", "case").stdout)
    assert preview["git"]["ok"] is False
    assert preview["git"]["reason"] == "not-ignored"
    assert preview["importable"]
    confirmed = run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    assert confirmed.returncode == 6
    assert json.loads(confirmed.stdout)["reason"] == "not-ignored"
    assert not (repo / ".sdd").exists()


def test_unreadable_database_reports_unavailable_not_nothing_to_import(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    db_of(repo).parent.mkdir()
    db_of(repo).write_bytes(b"not a sqlite database")
    log = write_log(tmp_path / "log.json", log_document(question("削除は取り消せますか", "取り消せる")))
    preview = run_cli(repo, "import-preview", "--log", str(log), "--case", "case")
    assert preview.returncode == 5
    payload = json.loads(preview.stdout)
    assert payload["status"] == "unavailable"
    assert "cannot be read" in payload["detail"]
    confirmed = run_cli(repo, "import-confirm", "--log", str(log), "--case", "case")
    assert confirmed.returncode == 5
    assert db_of(repo).read_bytes() == b"not a sqlite database"


def test_excerpt_limits_refuse_a_transcript_shaped_field(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(
            question("Q" * (imp.EXCERPT_LIMITS["question"] + 1), "a"),
            question("短い質問", "a" * (imp.EXCERPT_LIMITS["answer"] + 1)),
        ),
    )
    payload = json.loads(run_cli(repo, "import-preview", "--log", str(log), "--case", "case").stdout)
    assert [entry["reason"] for entry in payload["excluded"]] == [
        "excerpt-too-long",
        "excerpt-too-long",
    ]
    assert "stores excerpts, not transcripts" in payload["excluded"][0]["detail"]


def test_import_store_refuses_another_checkout(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "main")
    (other / ".gitignore").write_text(".sdd/\n")
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.record_import(
            {
                "checkout": str(other),
                "db": str(db_of(repo)),
                "sessionID": "import:case",
                "formID": "import:case:x",
                "case": "case",
                "pairs": [{"questionID": "case.q1", "text": "q", "value": "a"}],
            }
        )
    assert excinfo.value.reason == "outside-checkout"
    assert not (other / ".sdd").exists()


def test_store_refuses_to_rewrite_an_imported_question(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_import(
        {
            "checkout": str(repo),
            "sessionID": "import:case",
            "formID": "import:case:x",
            "case": "case",
            "pairs": [
                {"questionID": "case.q1", "text": "最初の質問", "options": ["はい", "いいえ"], "value": "はい"}
            ],
        }
    )
    with pytest.raises(dh.DesignHistoryError, match="must not change it"):
        dh.record_import(
            {
                "checkout": str(repo),
                "sessionID": "import:case",
                "formID": "import:case:x",
                "case": "case",
                "pairs": [
                    {"questionID": "case.q1", "text": "書き換えた質問", "options": ["はい"], "value": "はい"}
                ],
            }
        )
    pair = dh.search(checkout=repo)["results"][0]
    assert pair["question"]["text"] == "最初の質問"


def test_two_logs_in_one_case_keep_per_answer_provenance(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    first = write_log(
        tmp_path / "a.json", log_document(question("削除は取り消せますか", "取り消せる", id="case.q1"))
    )
    second = write_log(
        tmp_path / "b.json", log_document(question("対象外はありますか", "監査ログだけ残す", id="case.q2"))
    )
    run_cli(repo, "import-confirm", "--log", str(first), "--case", "case")
    run_cli(repo, "import-confirm", "--log", str(second), "--case", "case")
    pairs = json.loads(run_cli(repo, "search").stdout)["results"]
    tokens = {
        pair["question"]["questionID"]: pair["answers"][0]["eventID"] for pair in pairs
    }
    assert tokens == {
        "case.q1": f"import:{hashlib.sha256(first.read_bytes()).hexdigest()}",
        "case.q2": f"import:{hashlib.sha256(second.read_bytes()).hexdigest()}",
    }
    # A repeat of the first log adds nothing to the second log's pair.
    again = json.loads(run_cli(repo, "import-confirm", "--log", str(first), "--case", "case").stdout)
    assert again["counts"]["recorded"] == 0
    assert again["counts"]["alreadyRecorded"] == 1
    assert len(json.loads(run_cli(repo, "search").stdout)["results"]) == 2


def test_imported_pairs_are_visible_through_the_search_module(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    log = write_log(
        tmp_path / "log.json",
        log_document(question("削除は取り消せますか", "取り消せる", options=["取り消せる", "取り消せない"])),
    )
    run_cli(repo, "import-confirm", "--log", str(log), "--case", "checkout-cancel")
    result = dh.search(checkout=repo, query="取り消せ")
    assert result["status"] == "ok"
    assert result["results"][0]["question"]["text"] == "削除は取り消せますか"
    assert dh.search(checkout=repo, source=dh.IMPORT_SOURCE)["status"] == "ok"
    assert dh.search(checkout=repo, source="opencode.form.created")["status"] == "no-matches"


def test_import_help_documents_the_format_and_the_write_split() -> None:
    result = run_cli(Path(__file__).resolve().parents[1], "--help")
    assert result.returncode == 0
    for expected in (
        "import-preview --log FILE --case CASE",
        "import-confirm --log FILE --case CASE",
        imp.FORMAT_NAME,
        '"version": 1',
        "a preview is not consent",
        "never modified",
        "credential",
    ):
        assert expected in result.stdout
