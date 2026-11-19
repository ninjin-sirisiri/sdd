from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from sddlib import design_history as dh

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CLI = SCRIPTS / "design-history"
PYTHON = sys.executable


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "base")
    (repo / ".gitignore").write_text(".sdd/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "ignore")
    return repo


def run_cli(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(CLI), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        input=stdin,
    )


def register_payload(
    *,
    checkout: Path,
    session="ses_live",
    form="frm_live",
    case="checkout-cancel",
    questions=None,
) -> dict:
    return {
        "action": "register",
        "checkout": str(checkout),
        "sessionID": session,
        "formID": form,
        "case": case,
        "title": "設計の確認",
        "source": "opencode.form.created",
        "questions": questions
        if questions is not None
        else [
            {
                "questionID": "checkout-cancel.q1",
                "fieldKey": "q0",
                "ordinal": 0,
                "text": "削除は取り消せますか",
                "header": "削除",
                "options": [
                    {"value": "取り消せる", "label": "取り消せる"},
                    {"value": "取り消せない", "label": "取り消せない"},
                ],
                "allowsFreeText": True,
            },
            {
                "questionID": "checkout-cancel.q2",
                "fieldKey": "q1",
                "ordinal": 1,
                "text": "対象外はありますか",
                "header": "対象外",
                "options": [],
                "allowsFreeText": True,
            },
        ],
    }


def reply_payload(
    *,
    checkout: Path,
    session="ses_live",
    form="frm_live",
    case="checkout-cancel",
    answers=None,
    record_missing=True,
) -> dict:
    return {
        "action": "reply",
        "checkout": str(checkout),
        "sessionID": session,
        "formID": form,
        "case": case,
        "answers": answers if answers is not None else {"checkout-cancel.q1": "取り消せる", "checkout-cancel.q2": "監査ログのみ"},
        "recordMissing": record_missing,
        "source": "opencode.form.replied",
        "delivery": "event",
    }


# --- Git precheck ---------------------------------------------------------


def test_git_precheck_requires_ignored_and_untracked(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    precheck = dh.git_precheck(repo)
    assert precheck.ok is True
    assert precheck.ignored is True
    assert precheck.tracked is False
    assert precheck.database == repo / ".sdd" / "design-history.sqlite3"


def test_git_precheck_refuses_an_unignored_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".gitignore").write_text("")
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.git_precheck(repo)
    assert excinfo.value.reason == "not-ignored"
    assert not (repo / ".sdd").exists()


def test_git_precheck_refuses_a_tracked_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".gitignore").write_text("")
    database = repo / ".sdd" / "design-history.sqlite3"
    database.parent.mkdir()
    database.write_bytes(b"")
    _git(repo, "add", "-f", str(database.relative_to(repo)))
    _git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "tracked")
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.git_precheck(repo)
    assert excinfo.value.reason == "tracked"


def test_git_precheck_refuses_a_non_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.git_precheck(plain)
    assert excinfo.value.reason == "not-a-git-repository"


def test_git_precheck_refuses_a_database_outside_the_checkout(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    outside = tmp_path / "outside.sqlite3"
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.git_precheck(repo, outside)
    assert excinfo.value.reason == "outside-checkout"


def test_write_refuses_before_creating_the_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".gitignore").write_text("")
    with pytest.raises(dh.GitPrecheckError):
        dh.record_payload(register_payload(checkout=repo))
    assert not (repo / ".sdd").exists()


# --- Recording ------------------------------------------------------------


def test_records_multiple_questions_and_keeps_them_distinct(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(
        reply_payload(
            checkout=repo,
            answers={
                "checkout-cancel.q1": "取り消せる",
                "checkout-cancel.q2": "監査ログのみ",
            },
        )
    )
    result = dh.search(checkout=repo)
    assert result["status"] == "ok"
    assert len(result["results"]) == 2
    first, second = result["results"]
    assert first["question"]["questionID"] == "checkout-cancel.q1"
    assert first["question"]["options"][0] == {"ordinal": 0, "value": "取り消せる", "label": "取り消せる"}
    assert [option["label"] for option in first["question"]["options"]] == ["取り消せる", "取り消せない"]
    assert first["answers"][0]["value"] == "取り消せる"
    assert second["question"]["questionID"] == "checkout-cancel.q2"
    assert second["answers"][0]["value"] == "監査ログのみ"


def test_same_option_label_in_two_questions_stays_distinct(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(
        reply_payload(
            checkout=repo,
            answers={"checkout-cancel.q1": "取り消せる", "checkout-cancel.q2": "取り消せる"},
        )
    )
    result = dh.search(checkout=repo)
    assert [pair["answers"][0]["value"] for pair in result["results"]] == ["取り消せる", "取り消せる"]
    assert result["results"][0]["question"]["text"] != result["results"][1]["question"]["text"]


def test_cancel_does_not_overwrite_an_earlier_answer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(
        reply_payload(checkout=repo, answers={"checkout-cancel.q1": "取り消せる"})
    )
    dh.record_payload(
        {
            "action": "cancel",
            "checkout": str(repo),
            "sessionID": "ses_live",
            "formID": "frm_live",
            "case": "checkout-cancel",
            "source": "opencode.form.cancelled",
        }
    )
    result = dh.search(checkout=repo)
    by_id = {pair["question"]["questionID"]: pair for pair in result["results"]}
    assert dh.pair_state(by_id["checkout-cancel.q1"]) == "answered"
    assert dh.pair_state(by_id["checkout-cancel.q2"]) == "cancelled"
    assert by_id["checkout-cancel.q1"]["answers"][0]["value"] == "取り消せる"


def test_unanswered_question_is_not_an_agreement(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(
        reply_payload(checkout=repo, answers={"checkout-cancel.q1": "取り消せる"}, record_missing=True)
    )
    result = dh.search(checkout=repo)
    by_id = {pair["question"]["questionID"]: pair for pair in result["results"]}
    assert dh.pair_state(by_id["checkout-cancel.q1"]) == "answered"
    assert dh.pair_state(by_id["checkout-cancel.q2"]) == "unanswered"
    states = {pair["question"]["questionID"]: [answer["state"] for answer in pair["answers"]] for pair in result["results"]}
    assert states["checkout-cancel.q2"] == ["unanswered"]
    assert by_id["checkout-cancel.q2"]["answers"][0]["value"] is None


def test_correction_keeps_the_original_revision(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo, answers={"checkout-cancel.q1": "取り消せる"}))
    dh.record_payload(reply_payload(checkout=repo, answers={"checkout-cancel.q1": "取り消せない"}))
    result = dh.search(checkout=repo, question_id="checkout-cancel.q1")
    answers = result["results"][0]["answers"]
    assert [answer["value"] for answer in answers] == ["取り消せる", "取り消せない"]
    assert [answer["revision"] for answer in answers] == [1, 2]
    assert dh.pair_state(result["results"][0]) == "answered"


def test_redelivery_does_not_duplicate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = register_payload(checkout=repo)
    dh.record_payload(payload)
    dh.record_payload(payload)
    reply = reply_payload(checkout=repo)
    dh.record_payload(reply)
    dh.record_payload(reply)
    with sqlite3.connect(repo / ".sdd" / "design-history.sqlite3") as connection:
        forms = connection.execute("SELECT COUNT(*) FROM design_form").fetchone()[0]
        questions = connection.execute("SELECT COUNT(*) FROM design_question").fetchone()[0]
        answers = connection.execute("SELECT COUNT(*) FROM design_answer").fetchone()[0]
    assert (forms, questions, answers) == (1, 2, 2)


def test_unregistered_form_is_refused(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    with pytest.raises(dh.DesignHistoryError):
        dh.record_payload(reply_payload(checkout=repo, form="frm_other"))
    result = dh.search(checkout=repo)
    # No database was created by the refused write.
    assert result["status"] == "no-database"


def test_another_checkout_cannot_write_into_this_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "main")
    (other / ".gitignore").write_text(".sdd/\n")
    dh.record_payload(register_payload(checkout=repo))
    # A payload naming another checkout while pointing at this database must be
    # refused: mixing two repositories in one history is not allowed.
    stray = register_payload(checkout=other)
    stray["db"] = str(repo / ".sdd" / "design-history.sqlite3")
    with pytest.raises(dh.GitPrecheckError) as excinfo:
        dh.record_payload(stray)
    assert excinfo.value.reason == "outside-checkout"
    result = dh.search(checkout=repo)
    assert {pair["checkout"] for pair in result["results"]} == {str(repo)}
    # The other checkout keeps its own database when it records normally.
    assert not (other / ".sdd").exists()


def test_database_with_another_checkout_metadata_is_refused(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    # Force the escape past the Git precheck by naming the same checkout but
    # writing with different metadata through the low-level writer.
    with dh.write_session(repo) as connection:
        connection.execute("UPDATE meta SET value = '/somewhere/else' WHERE key = 'checkout'")
    with pytest.raises(dh.DesignHistoryError, match="belongs to"):
        dh.record_payload(register_payload(checkout=repo))


def test_secret_answer_is_omitted_and_never_stored(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
    result = dh.record_payload(
        reply_payload(checkout=repo, answers={"checkout-cancel.q1": secret, "checkout-cancel.q2": "ok"})
    )
    assert result["omitted"] == ["checkout-cancel.q1"]
    search = dh.search(checkout=repo)
    by_id = {pair["question"]["questionID"]: pair for pair in search["results"]}
    assert by_id["checkout-cancel.q1"]["answers"] == []
    assert by_id["checkout-cancel.q1"]["question"]["omitted"] == "secret-detected"
    assert search["omissions"][0]["reason"] == "secret-detected"
    raw = (repo / ".sdd" / "design-history.sqlite3").read_bytes()
    assert secret.encode() not in raw


def test_secret_question_is_omitted(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = register_payload(
        checkout=repo,
        questions=[
            {
                "questionID": "checkout-cancel.q1",
                "fieldKey": "q0",
                "text": "API key は ghp_abcdefghijklmnopqrstuvwxyz0123456789 ですか",
                "options": [],
            }
        ],
    )
    dh.record_payload(payload)
    result = dh.search(checkout=repo)
    assert result["results"] == []
    assert result["omissions"][0]["reason"] == "secret-detected"


def test_recorder_status_distinguishes_stopped_from_empty(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(
        {
            "action": "status",
            "checkout": str(repo),
            "status": "stopped",
            "detail": "plugin not loaded",
        }
    )
    result = dh.search(checkout=repo, query="no such question")
    assert result["status"] == "recording-unavailable"
    assert result["recorder"]["status"] == "stopped"
    assert "empty result does not mean" in result["detail"]


def test_no_matches_differs_from_no_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert dh.search(checkout=repo)["status"] == "no-database"
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo))
    assert dh.search(checkout=repo, query="存在しない")["status"] == "no-matches"


def test_search_does_not_create_or_modify_the_database(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo))
    database = repo / ".sdd" / "design-history.sqlite3"
    before = database.read_bytes()
    dh.search(checkout=repo, query="取り消せる")
    assert database.read_bytes() == before
    # A search in a checkout with no database must not create one.
    empty = init_repo(tmp_path / "second")
    dh.search(checkout=empty, query="x")
    assert not (empty / ".sdd").exists()


# --- Search filtering ----------------------------------------------------


def test_search_filters_by_case_question_and_japanese_partial_match(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo))
    dh.record_payload(
        register_payload(checkout=repo, session="ses_two", form="frm_two", case="audit-log")
    )
    dh.record_payload(
        reply_payload(
            checkout=repo,
            session="ses_two",
            form="frm_two",
            case="audit-log",
            answers={
                "checkout-cancel.q1": "監査ログを残す",
                "checkout-cancel.q2": "なし",
            },
        )
    )
    assert dh.search(checkout=repo, case="audit-log")["status"] == "ok"
    assert {pair["case"] for pair in dh.search(checkout=repo, case="audit-log")["results"]} == {"audit-log"}
    assert dh.search(checkout=repo, case="AUDIT")["status"] == "ok"
    by_question = dh.search(checkout=repo, question_id="checkout-cancel.q2")
    assert len(by_question["results"]) == 2
    by_keyword = dh.search(checkout=repo, query="取り消せ")
    assert by_keyword["status"] == "ok"
    assert all("取り消せ" in json.dumps(pair, ensure_ascii=False) for pair in by_keyword["results"][:1])
    answer_hit = dh.search(checkout=repo, query="監査ログを残す")
    assert len(answer_hit["results"]) == 1
    option_hit = dh.search(checkout=repo, query="取り消せない")
    assert len(option_hit["results"]) == 2


def test_search_state_filter(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo, answers={"checkout-cancel.q1": "取り消せる"}))
    answered = dh.search(checkout=repo, state="answered")
    assert {pair["question"]["questionID"] for pair in answered["results"]} == {"checkout-cancel.q1"}
    unanswered = dh.search(checkout=repo, state="unanswered")
    assert {pair["question"]["questionID"] for pair in unanswered["results"]} == {"checkout-cancel.q2"}


# --- CLI -----------------------------------------------------------------


def test_cli_search_returns_json_with_question_options_and_answer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo))
    result = run_cli(repo, "search", "--case", "checkout-cancel", "--query", "削除")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    pair = payload["results"][0]
    assert pair["case"] == "checkout-cancel"
    assert pair["source"] == "opencode.form.created"
    assert pair["question"]["questionID"] == "checkout-cancel.q1"
    assert [option["label"] for option in pair["question"]["options"]] == ["取り消せる", "取り消せない"]
    assert pair["answers"][0]["value"] == "取り消せる"


def test_cli_search_no_database_is_distinct_exit_code(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    result = run_cli(repo, "search")
    assert result.returncode == 4
    assert json.loads(result.stdout)["status"] == "no-database"
    assert not (repo / ".sdd").exists()


def test_cli_search_no_matches_exit_code(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    result = run_cli(repo, "search", "--query", "not present")
    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "no-matches"


def test_cli_record_round_trip_from_stdin(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = register_payload(checkout=repo)
    result = run_cli(repo, "record", stdin=json.dumps(payload))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["action"] == "register"
    reply = run_cli(repo, "record", stdin=json.dumps(reply_payload(checkout=repo)))
    assert reply.returncode == 0, reply.stderr
    search = run_cli(repo, "search", "--case", "checkout-cancel")
    assert search.returncode == 0
    assert len(json.loads(search.stdout)["results"]) == 2


def test_cli_record_refuses_git_violation_with_exit_code(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".gitignore").write_text("")
    result = run_cli(repo, "record", stdin=json.dumps(register_payload(checkout=repo)))
    assert result.returncode == 6
    payload = json.loads(result.stdout)
    assert payload["status"] == "refused"
    assert payload["reason"] == "not-ignored"
    assert not (repo / ".sdd").exists()


def test_cli_git_check_reports_without_writing(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    result = run_cli(repo, "git-check")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ignored"] is True
    assert payload["tracked"] is False
    assert not (repo / ".sdd").exists()


def test_cli_status_reports_recorder_state(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    dh.record_payload(register_payload(checkout=repo))
    dh.record_payload(reply_payload(checkout=repo))
    result = run_cli(repo, "status")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["git"]["ok"] is True
    assert payload["counts"]["forms"] == 1
    assert payload["counts"]["answers"] == 2


def test_unreadable_database_is_reported_not_raised(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    database = repo / ".sdd" / "design-history.sqlite3"
    database.parent.mkdir()
    database.write_bytes(b"not a sqlite database")
    result = dh.search(checkout=repo)
    assert result["status"] == "unavailable"
    assert "unreadable" in result["detail"]


def test_secret_detection_patterns() -> None:
    assert dh.contains_secret("sk-proj-abcdefghijklmnopqrstuvwxyz")
    assert dh.contains_secret("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert dh.contains_secret("password: hunter2hunter2")
    assert not dh.contains_secret("削除は取り消せる")
    assert not dh.contains_secret("")
