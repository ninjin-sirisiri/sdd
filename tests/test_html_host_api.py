from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from sddlib.html_host_api import (
    DEFAULT_TIMEOUT_MS,
    MAX_CANDIDATE_BYTES,
    MAX_SOURCE_BYTES,
    POLICY_VERSION,
    PROTOCOL_VERSION,
    policy_identity,
)
from sddlib.html_units import scan_markdown, strict_requirements


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "html-docs"
FIXTURES = ROOT / "tests" / "fixtures"

CSP = (
    "default-src &#x27;none&#x27;; img-src &#x27;self&#x27; data:; "
    "style-src &#x27;self&#x27;; base-uri &#x27;none&#x27;; "
    "form-action &#x27;none&#x27;; frame-ancestors &#x27;none&#x27;"
)

ADR_MARKDOWN = (
    "# Queue choice\n"
    "\n"
    "Use `FIFO` with a 750 ms window and at most 2 MiB.\n"
    "\n"
    "Adopt the queue. Avoid `LIFO`. See "
    "[the plan](../plans/2026-01-01-plan.md).\n"
)

ADR_BODY = """\
<article class="decision-article">
<h1 id="queue-choice">Choosing a queue</h1>
<p id="summary">We use <code id="fifo">FIFO</code>; the window is 750 ms and the limit is at most 2 MiB.</p>
<p id="decision">Adopt the queue; <code id="lifo">LIFO</code> is the avoided option. Follow <a id="plan-link" href="../plans/2026-01-01-plan.md">the plan</a>.</p>
</article>
"""

ADR_TARGETS = {
    "heading": ["queue-choice"],
    "paragraph": ["summary", "decision"],
    "inline_code": ["fifo", "lifo"],
    "link": ["plan-link"],
}

SEMANTIC_SOURCE = "docs/adr/0001-choice.md"
SEMANTIC_HTML = "docs/adr/0001-choice.html"
CSS_PATH = "docs/sdd/assets/sdd.css"
RECEIPT_PATH = "docs/sdd/html-evidence/run-1/receipt.json"


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def run_host_api(
    repo: Path,
    payload: object | None = None,
    *,
    raw: str | None = None,
) -> subprocess.CompletedProcess[str]:
    input_text = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [str(CLI), "host-api"],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
    )


def run_host_api_bytes(repo: Path, data: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(CLI), "host-api"],
        cwd=repo,
        input=data,
        capture_output=True,
    )


def envelope(process: subprocess.CompletedProcess[object]) -> dict[str, object]:
    if isinstance(process.stdout, bytes):
        output = process.stdout.decode("utf-8")
    else:
        output = str(process.stdout)
    assert output.endswith("\n")
    return json.loads(output)


def assert_error(process: subprocess.CompletedProcess[object], code: str) -> dict[str, object]:
    result = envelope(process)
    assert process.returncode == 2
    assert result["ok"] is False
    assert result["error"]["code"] == code  # type: ignore[index]
    assert code in str(process.stderr)
    return result


def assert_denied(process: subprocess.CompletedProcess[object], code: str) -> dict[str, object]:
    result = envelope(process)
    assert process.returncode == 1
    assert result["ok"] is True
    assert result["result"]["decision"] == "deny"  # type: ignore[index]
    codes = {item["code"] for item in result["result"]["violations"]}  # type: ignore[index]
    assert code in codes
    return result


def glossary_pair() -> tuple[bytes, bytes]:
    source = FIXTURES / "glossary" / "CONTEXT.md"
    companion = FIXTURES / "glossary" / "CONTEXT.html"
    return source.read_bytes(), companion.read_bytes()


def _target_map(markdown: str, by_kind: dict[str, list[str]]) -> dict[str, str]:
    counters: dict[str, int] = {}
    targets: dict[str, str] = {}
    for unit in scan_markdown(markdown).units:
        index = counters.get(unit.kind, 0)
        counters[unit.kind] = index + 1
        values = by_kind.get(unit.kind, [])
        if index < len(values):
            targets[unit.id] = values[index]
    return targets


def _mappings(markdown: str, targets: dict[str, str]) -> list[dict[str, object]]:
    mappings: list[dict[str, object]] = []
    for unit in scan_markdown(markdown).units:
        target = targets.get(unit.id)
        if target is None:
            continue
        mappings.append(
            {
                "unit": unit.id,
                "representation": "paraphrase",
                "targets": [target],
            }
        )
    return mappings


def _strict(markdown: str, mappings: list[dict[str, object]]) -> list[dict[str, object]]:
    targets = {item["unit"]: item["targets"] for item in mappings}
    return [
        {
            "unit": requirement["unit"],
            "category": requirement["category"],
            "value": requirement["value"],
            "targets": targets[requirement["unit"]],
        }
        for requirement in strict_requirements(scan_markdown(markdown))
        if requirement["unit"] in targets
    ]


def semantic_pair() -> tuple[bytes, bytes]:
    mappings = _mappings(ADR_MARKDOWN, _target_map(ADR_MARKDOWN, ADR_TARGETS))
    scan = scan_markdown(ADR_MARKDOWN)
    provenance = {
        "schema": "sdd-provenance",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": SEMANTIC_SOURCE, "digest": scan.digest},
        "units": [
            {
                "id": unit.id,
                "kind": unit.kind,
                "source_digest": unit.digest,
                "range": {"start": unit.start, "end": unit.end},
                "parent": unit.parent,
            }
            for unit in scan.units
        ],
        "mappings": mappings,
        "strict": _strict(ADR_MARKDOWN, mappings),
        "supplementary": [],
        "calculations": [],
    }
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
        f'<meta name="sdd-source-digest" content="{digest_bytes(ADR_MARKDOWN.encode("utf-8"))}">\n'
        '<meta name="sdd-html-contract" content="semantic-v1">\n'
        "<title>Example document</title>\n"
        f'<link rel="stylesheet" href="../sdd/assets/sdd.css">\n'
        "</head>\n"
        "<body>\n"
        '<a class="skip-link" href="#content">Skip to content</a>\n'
        '<header class="document-header"><p class="document-kind">ADR</p></header>\n'
        '<main id="content" tabindex="-1">\n'
        f"{ADR_BODY}"
        '<template id="sdd-provenance">'
        + json.dumps(provenance, ensure_ascii=False)
        + "</template>\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )
    return ADR_MARKDOWN.encode("utf-8"), html.encode("utf-8")


def build_receipt(
    *,
    source_path: str,
    source_bytes: bytes,
    html_path: str,
    html_bytes: bytes,
    css_bytes: bytes = b"/* fixture stylesheet */\n",
    resources: list[dict[str, object]] | None = None,
    policy: dict[str, object] | None = None,
    conditions: list[dict[str, object]] | None = None,
    verification: dict[str, object] | None = None,
) -> dict[str, object]:
    identity = policy or policy_identity()
    if verification is None:
        verification = {
            "result": "pass",
            "checks": [
                {
                    "name": "static",
                    "decision": "pass",
                    "evidence": ["docs/sdd/html-evidence/run-1/static.json"],
                }
            ],
        }
    if conditions is None:
        conditions = [
            {
                "id": condition,
                "decision": "met",
                "evidence": [f"docs/sdd/html-evidence/run-1/{condition}.json"],
            }
            for condition in ("information", "support", "usability", "render")
        ]
    return {
        "schema": "sdd-html-receipt",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": source_path, "digest": digest_bytes(source_bytes)},
        "html": {"path": html_path, "digest": digest_bytes(html_bytes)},
        "inputs": {
            "css": [{"path": CSS_PATH, "digest": digest_bytes(css_bytes)}],
            "resources": resources or [],
            "policy": {
                "version": identity["version"],
                "digest": identity["digest"],
            },
        },
        "versions": {"settings": "settings-1", "rubric": "rubric-1", "profile": "profile-1"},
        "generation": {
            "id": "generation-1",
            "revision": 1,
            "parent": None,
            "job": "job-1",
            "cycle": "cycle-1",
        },
        "h2": {"reference": "h2-run-1", "purpose": "Html"},
        "verification": verification,
        "conditions": conditions,
    }


def test_capabilities_describes_protocol_limits_and_stage_semantics(tmp_path: Path) -> None:
    process = run_host_api(tmp_path, {"version": 1, "operation": "capabilities"})

    assert process.returncode == 0
    assert process.stderr == ""
    result = envelope(process)
    assert result["ok"] is True
    assert result["version"] == PROTOCOL_VERSION
    assert result["operation"] == "capabilities"
    capabilities = result["result"]  # type: ignore[index]
    assert capabilities["protocol"]["version"] == PROTOCOL_VERSION  # type: ignore[index]
    assert capabilities["operations"] == [  # type: ignore[index]
        "capabilities",
        "discover",
        "source-units",
        "candidate-check",
    ]
    assert capabilities["stages"]["structural"]["final"] is False  # type: ignore[index]
    assert "never a final pass" in capabilities["stages"]["structural"]["message"]  # type: ignore[index]
    assert capabilities["stages"]["final"]["final"] is True  # type: ignore[index]
    assert capabilities["limits"]["source_bytes"] == MAX_SOURCE_BYTES  # type: ignore[index]
    assert capabilities["limits"]["candidate_html_bytes"] == MAX_CANDIDATE_BYTES  # type: ignore[index]
    assert capabilities["limits"]["timeout_ms_default"] == DEFAULT_TIMEOUT_MS  # type: ignore[index]
    assert capabilities["bootstrap"] == {"implicit": False, "operation": "html-docs bootstrap"}  # type: ignore[index]
    assert capabilities["writes"] == {"files": False, "html": False}  # type: ignore[index]
    assert capabilities["policy"]["version"] == POLICY_VERSION  # type: ignore[index]
    assert capabilities["policy"]["digest"] == policy_identity()["digest"]  # type: ignore[index]
    assert "semantic-v1" in capabilities["policy"]["accepted_versions"]  # type: ignore[index]
    assert capabilities["receipt"]["derived"] is False  # type: ignore[index]
    assert sorted(path.name for path in tmp_path.iterdir()) == []


def test_discover_resolves_target_pairs_and_unrelated_paths(tmp_path: Path) -> None:
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "discover",
            "paths": [
                "CONTEXT.md",
                "CONTEXT.html",
                "README.md",
                "docs/adr/0001-use-postgres.md",
            ],
        },
    )

    assert process.returncode == 0
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["targets"] == [  # type: ignore[index]
        {
            "source": "CONTEXT.md",
            "html": "CONTEXT.html",
            "kind": "context",
            "input_paths": ["CONTEXT.md", "CONTEXT.html"],
        },
        {
            "source": "docs/adr/0001-use-postgres.md",
            "html": "docs/adr/0001-use-postgres.html",
            "kind": "adr",
            "input_paths": ["docs/adr/0001-use-postgres.md"],
        },
    ]
    assert result["unrelated"] == ["README.md"]  # type: ignore[index]
    assert list(tmp_path.iterdir()) == []


def test_source_units_scan_in_memory_and_report_strict_requirements(tmp_path: Path) -> None:
    source_bytes, _html_bytes = glossary_pair()
    extra = b"notes\n"
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "source-units",
            "path": "CONTEXT.md",
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "notes.txt": encoded(extra),
            },
        },
    )

    assert process.returncode == 0
    assert process.stderr == ""
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["path"] == "CONTEXT.md"
    assert result["status"] == "complete"
    assert result["coverage"]["complete"] is True  # type: ignore[index]
    assert result["source"]["digest"] == digest_bytes(source_bytes)  # type: ignore[index]
    assert result["source"]["byte_length"] == len(source_bytes)  # type: ignore[index]
    assert result["units"]
    assert {item["kind"] for item in result["units"]} >= {"heading", "paragraph", "glossary_term"}
    assert {item["category"] for item in result["strict"]} >= {"glossary_term", "avoid"}
    assert result["input_digests"] == {  # type: ignore[index]
        "CONTEXT.md": digest_bytes(source_bytes),
        "notes.txt": digest_bytes(extra),
    }
    roles = {item["path"]: item["role"] for item in result["inputs"]}  # type: ignore[index]
    assert roles == {"CONTEXT.md": "source", "notes.txt": "resource"}
    assert list(tmp_path.iterdir()) == []


def test_source_units_reports_unsupported_constructs_without_dropping(tmp_path: Path) -> None:
    markdown = (
        b"Title\n"
        b"=====\n"
        b"\n"
        b"[ref]: https://example.test\n"
        b"\n"
        b"Body [ref].\n"
    )
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "source-units",
            "path": "docs/sdd/specs/example.md",
            "inputs": {"docs/sdd/specs/example.md": encoded(markdown)},
        },
    )

    assert process.returncode == 0
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["status"] == "incomplete"
    assert result["coverage"]["complete"] is False  # type: ignore[index]
    assert {item["kind"] for item in result["unsupported"]} >= {  # type: ignore[index]
        "setext_heading",
        "reference_definition",
    }
    assert result["assurance"] == "lossless-byte-scan"


def test_structural_candidate_check_uses_supplied_bytes_and_does_not_write(
    tmp_path: Path,
) -> None:
    source_bytes, html_bytes = glossary_pair()
    (tmp_path / "CONTEXT.md").write_text("# Different on disk\n", encoding="utf-8")
    (tmp_path / "CONTEXT.html").write_text("<html>stale disk candidate</html>\n", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(html_bytes),
            },
        },
    )

    assert process.returncode == 0
    assert process.stderr == ""
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["decision"] == "allow"
    assert result["stage"] == "structural"
    assert result["final"] is False
    assert result["final_binding"] is False
    assert result["receipt"] is None
    assert "not a final pass" in result["message"]
    assert "not a final pass" in result["limitations"][0]
    assert result["contract"] == "strict"
    assert result["digests"] == {  # type: ignore[index]
        "source": digest_bytes(source_bytes),
        "candidate": digest_bytes(html_bytes),
        "receipt": None,
    }
    assert result["input_digests"] == {  # type: ignore[index]
        "CONTEXT.html": digest_bytes(html_bytes),
        "CONTEXT.md": digest_bytes(source_bytes),
    }
    roles = {item["path"]: item["role"] for item in result["inputs"]}  # type: ignore[index]
    assert roles == {"CONTEXT.html": "candidate", "CONTEXT.md": "source"}
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before
    assert (tmp_path / "CONTEXT.md").read_text(encoding="utf-8") == "# Different on disk\n"
    assert (tmp_path / "CONTEXT.html").read_text(encoding="utf-8") == "<html>stale disk candidate</html>\n"


def test_structural_candidate_check_reports_static_denial_without_final_claim(
    tmp_path: Path,
) -> None:
    source_bytes, _html_bytes = glossary_pair()
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(b"<html><body>incomplete</body></html>"),
            },
        },
    )

    assert process.returncode == 1
    assert process.stderr
    result = assert_denied(process, "digest-metadata")
    assert result["result"]["stage"] == "structural"  # type: ignore[index]
    assert result["result"]["final"] is False  # type: ignore[index]
    assert "no final binding was checked" in result["result"]["message"]  # type: ignore[index]


def test_structural_stage_rejects_a_receipt(tmp_path: Path) -> None:
    source_bytes, html_bytes = glossary_pair()
    receipt = build_receipt(
        source_path="CONTEXT.md",
        source_bytes=source_bytes,
        html_path="CONTEXT.html",
        html_bytes=html_bytes,
    )
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "receipt": RECEIPT_PATH,
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(html_bytes),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    assert_error(process, "receipt-not-allowed")


def test_final_stage_requires_a_receipt_and_its_bytes(tmp_path: Path) -> None:
    source_bytes, html_bytes = glossary_pair()
    base_inputs = {
        "CONTEXT.md": encoded(source_bytes),
        "CONTEXT.html": encoded(html_bytes),
    }

    missing = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "final",
            "inputs": base_inputs,
        },
    )
    assert_error(missing, "missing-input")

    unbound = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": base_inputs,
        },
    )
    assert_error(unbound, "missing-input")
    assert not (tmp_path / "CONTEXT.html").exists()


def test_structural_semantic_pass_is_explicitly_not_final(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "structural",
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
            },
        },
    )

    assert process.returncode == 0
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["decision"] == "allow"
    assert result["contract"] == "semantic-v1"
    assert result["stage"] == "structural"
    assert result["final"] is False
    assert result["final_binding"] is False
    assert result["receipt"] is None
    assert "not a final pass" in result["message"]
    assert list(tmp_path.iterdir()) == []


def test_final_stage_binds_semantic_candidate_receipt_and_all_inputs(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    css_bytes = b"/* fixture stylesheet */\n"
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
    )
    receipt_bytes = json.dumps(receipt, ensure_ascii=False).encode("utf-8")
    inputs = {
        SEMANTIC_SOURCE: encoded(source_bytes),
        SEMANTIC_HTML: encoded(html_bytes),
        CSS_PATH: encoded(css_bytes),
        RECEIPT_PATH: encoded(receipt_bytes),
    }
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": inputs,
        },
    )

    assert process.returncode == 0
    assert process.stderr == ""
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["decision"] == "allow"
    assert result["stage"] == "final"
    assert result["final"] is True
    assert result["final_binding"] is True
    assert result["receipt"]["path"] == RECEIPT_PATH  # type: ignore[index]
    assert result["receipt"]["digest"] == digest_bytes(receipt_bytes)  # type: ignore[index]
    assert result["digests"] == {  # type: ignore[index]
        "source": digest_bytes(source_bytes),
        "candidate": digest_bytes(html_bytes),
        "receipt": digest_bytes(receipt_bytes),
    }
    binding = result["receipt"]["binding"]  # type: ignore[index]
    assert binding["bound"] is True  # type: ignore[index]
    assert binding["source"]["match"] is True  # type: ignore[index]
    assert binding["html"]["match"] is True  # type: ignore[index]
    assert binding["css"][0]["match"] is True  # type: ignore[index]
    assert binding["policy"]["match"] is True  # type: ignore[index]
    assert binding["conditions"] == {  # type: ignore[index]
        "information": "met",
        "support": "met",
        "usability": "met",
        "render": "met",
    }
    assert result["input_digests"] == {  # type: ignore[index]
        SEMANTIC_SOURCE: digest_bytes(source_bytes),
        SEMANTIC_HTML: digest_bytes(html_bytes),
        CSS_PATH: digest_bytes(css_bytes),
        RECEIPT_PATH: digest_bytes(receipt_bytes),
    }
    roles = {item["path"]: item["role"] for item in result["inputs"]}  # type: ignore[index]
    assert roles == {
        SEMANTIC_SOURCE: "source",
        SEMANTIC_HTML: "candidate",
        CSS_PATH: "resource",
        RECEIPT_PATH: "receipt",
    }
    assert result["publication"] == "not-performed"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("field", "code"),
    (
        ("source", "receipt-source-digest"),
        ("html", "receipt-html-digest"),
    ),
)
def test_final_rejects_receipt_artifact_digest_mismatch(
    tmp_path: Path, field: str, code: str
) -> None:
    source_bytes, html_bytes = semantic_pair()
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
    )
    receipt[field]["digest"] = "sha256:" + "0" * 64  # type: ignore[index]
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    assert process.returncode == 1
    assert_denied(process, code)


def test_final_rejects_unmet_conditions_failed_verification_and_failed_checks(
    tmp_path: Path,
) -> None:
    source_bytes, html_bytes = semantic_pair()
    css_bytes = b"/* fixture stylesheet */\n"

    unmet = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
    )
    unmet["conditions"][1]["decision"] = "unmet"  # type: ignore[index][index]
    unmet_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(unmet).encode("utf-8")),
            },
        },
    )
    assert_denied(unmet_process, "receipt-condition")

    failed_verification = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
        verification={
            "result": "fail",
            "checks": [{"name": "static", "decision": "pass", "evidence": ["e"]}],
        },
    )
    failed_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(failed_verification).encode("utf-8")),
            },
        },
    )
    assert_denied(failed_process, "receipt-verification")

    failed_check = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
        verification={
            "result": "pass",
            "checks": [{"name": "static", "decision": "not_run", "evidence": []}],
        },
    )
    check_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(failed_check).encode("utf-8")),
            },
        },
    )
    assert_denied(check_process, "receipt-check")


def test_final_rejects_css_and_policy_fingerprint_mismatch(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    css_bytes = b"/* fixture stylesheet */\n"
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
    )

    wrong_css = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* changed stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )
    assert_denied(wrong_css, "receipt-css-digest")

    wrong_policy = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
        policy={"version": "other-policy", "digest": "sha256:" + "0" * 64},
    )
    policy_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(wrong_policy).encode("utf-8")),
            },
        },
    )
    result = assert_denied(policy_process, "receipt-policy-version")
    codes = {item["code"] for item in result["result"]["violations"]}  # type: ignore[index]
    assert "receipt-policy-digest" in codes


def test_final_rejects_receipt_path_mismatch(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
    )
    receipt["source"]["path"] = "docs/adr/other.md"  # type: ignore[index]
    receipt["html"]["path"] = "docs/adr/other.html"  # type: ignore[index]
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    result = assert_denied(process, "receipt-source-path")
    codes = {item["code"] for item in result["result"]["violations"]}  # type: ignore[index]
    assert "receipt-html-path" in codes


def test_final_accepts_the_legacy_semantic_v1_policy_version_alias(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    css_bytes = b"/* fixture stylesheet */\n"
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
    )
    receipt["inputs"]["policy"]["version"] = "semantic-v1"  # type: ignore[index]
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    assert process.returncode == 0
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["receipt"]["binding"]["policy"]["match"] is True  # type: ignore[index]


def test_final_requires_every_receipt_fingerprint_input(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
    )
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    assert_error(process, "missing-input")


def test_final_binds_resource_fingerprints(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    css_bytes = b"/* fixture stylesheet */\n"
    svg_path = "docs/sdd/assets/figure.svg"
    svg_bytes = b"<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n"
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
        resources=[{"path": svg_path, "digest": digest_bytes(svg_bytes)}],
    )
    allowed = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                svg_path: encoded(svg_bytes),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )
    assert allowed.returncode == 0
    result = envelope(allowed)["result"]  # type: ignore[index]
    assert result["receipt"]["binding"]["resources"][0]["match"] is True  # type: ignore[index]
    assert result["input_digests"][svg_path] == digest_bytes(svg_bytes)  # type: ignore[index]

    wrong = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=css_bytes,
        resources=[{"path": svg_path, "digest": digest_bytes(svg_bytes)}],
    )
    denied = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                svg_path: encoded(b"<svg>changed</svg>"),
                RECEIPT_PATH: encoded(json.dumps(wrong).encode("utf-8")),
            },
        },
    )
    assert_denied(denied, "receipt-resource-digest")

    missing = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(css_bytes),
                RECEIPT_PATH: encoded(json.dumps(wrong).encode("utf-8")),
            },
        },
    )
    assert_error(missing, "missing-input")


def test_final_requires_the_shared_stylesheet_fingerprint(tmp_path: Path) -> None:
    source_bytes, html_bytes = semantic_pair()
    other_css = b"/* other stylesheet */\n"
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
        css_bytes=other_css,
    )
    receipt["inputs"]["css"] = [  # type: ignore[index]
        {"path": "docs/sdd/assets/other.css", "digest": digest_bytes(other_css)}
    ]
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                "docs/sdd/assets/other.css": encoded(other_css),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    assert_denied(process, "receipt-css-missing")


def test_source_units_accepts_a_companion_path_and_names_the_source_path(tmp_path: Path) -> None:
    source_bytes, _html_bytes = glossary_pair()
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "source-units",
            "path": "CONTEXT.html",
            "inputs": {"CONTEXT.md": encoded(source_bytes)},
        },
    )

    assert process.returncode == 0
    result = envelope(process)["result"]  # type: ignore[index]
    assert result["path"] == "CONTEXT.md"
    assert result["target"] == {  # type: ignore[index]
        "source": "CONTEXT.md",
        "html": "CONTEXT.html",
        "kind": "context",
    }
    assert result["input_digests"] == {"CONTEXT.md": digest_bytes(source_bytes)}  # type: ignore[index]


def test_duplicate_resolved_input_aliases_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    assets = root / "docs" / "sdd" / "assets"
    assets.mkdir(parents=True)
    stylesheet = assets / "sdd.css"
    stylesheet.write_text("/* css */\n", encoding="utf-8")
    try:
        (root / "alias.css").symlink_to(stylesheet)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    process = run_host_api(
        root,
        {
            "version": 1,
            "operation": "source-units",
            "path": "CONTEXT.md",
            "inputs": {
                "docs/sdd/assets/sdd.css": encoded(b"/* css */\n"),
                "alias.css": encoded(b"/* css */\n"),
            },
        },
    )

    assert_error(process, "duplicate-input")


def test_candidate_check_never_falls_back_to_disk_or_bootstraps(tmp_path: Path) -> None:
    source_bytes, html_bytes = glossary_pair()
    (tmp_path / "CONTEXT.md").write_bytes(source_bytes)
    (tmp_path / "CONTEXT.html").write_bytes(html_bytes)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    missing_html = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {"CONTEXT.md": encoded(source_bytes)},
        },
    )
    assert_error(missing_html, "missing-input")

    missing_source = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {"CONTEXT.html": encoded(html_bytes)},
        },
    )
    assert_error(missing_source, "missing-input")
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before


def test_final_rejects_a_strict_companion_even_with_a_valid_receipt(tmp_path: Path) -> None:
    source_bytes, html_bytes = glossary_pair()
    receipt = build_receipt(
        source_path="CONTEXT.md",
        source_bytes=source_bytes,
        html_path="CONTEXT.html",
        html_bytes=html_bytes,
    )
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(receipt).encode("utf-8")),
            },
        },
    )

    result = assert_denied(process, "receipt-contract")
    assert result["result"]["contract"] == "strict"  # type: ignore[index]


@pytest.mark.parametrize(
    ("payload", "code"),
    (
        ({"version": 2, "operation": "capabilities"}, "unsupported-version"),
        ({"version": "1", "operation": "capabilities"}, "unsupported-version"),
        ({"operation": "capabilities"}, "unsupported-version"),
        ({"version": 1, "operation": "unknown"}, "unknown-operation"),
        ({"version": 1, "operation": "capabilities", "extra": True}, "unknown-field"),
        ({"version": 1, "operation": "source-units"}, "missing-field"),
        (
            {"version": 1, "operation": "discover", "paths": ["../outside.md"]},
            "path-escape",
        ),
        ({"version": 1, "operation": "discover", "paths": ["/absolute.md"]}, "path-escape"),
        ({"version": 1, "operation": "discover", "paths": ["./CONTEXT.md"]}, "path-invalid"),
        ({"version": 1, "operation": "discover", "paths": ["a\\b.md"]}, "path-invalid"),
        (
            {
                "version": 1,
                "operation": "source-units",
                "path": "CONTEXT.md",
                "inputs": {"CONTEXT.md": "not base64!!"},
            },
            "invalid-base64",
        ),
        ({"version": 1, "operation": "capabilities", "timeout_ms": -1}, "invalid-timeout"),
        ({"version": 1, "operation": "capabilities", "timeout_ms": 0}, "timeout"),
    ),
)
def test_protocol_errors_are_machine_readable(
    tmp_path: Path, payload: object, code: str
) -> None:
    process = run_host_api(tmp_path, payload)

    result = assert_error(process, code)
    assert result["ok"] is False
    assert result["version"] == PROTOCOL_VERSION
    assert result["root"] == str(tmp_path)


def test_invalid_json_and_non_json_requests_fail_cleanly(tmp_path: Path) -> None:
    invalid = run_host_api(tmp_path, raw="{")
    assert_error(invalid, "invalid-json")
    assert envelope(invalid)["operation"] is None
    assert envelope(invalid)["error"]["message"]  # type: ignore[index]

    array = run_host_api(tmp_path, raw="[]")
    assert_error(array, "invalid-request")


def test_non_utf8_request_and_non_utf8_input_are_explicit(tmp_path: Path) -> None:
    request = run_host_api_bytes(tmp_path, b'{"version":1,"operation":"\xff"}')
    assert_error(request, "invalid-encoding")

    source_bytes, _html_bytes = glossary_pair()
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {
                "CONTEXT.md": encoded(b"\xff\xfe"),
                "CONTEXT.html": encoded(b"<html></html>"),
            },
        },
    )
    assert_error(process, "invalid-encoding")

    html_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(b"\xff\xfe"),
            },
        },
    )
    assert_error(html_process, "invalid-encoding")


def test_oversize_source_and_symlink_escape_are_explicit(tmp_path: Path) -> None:
    oversize = b"a" * (MAX_SOURCE_BYTES + 1)
    process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "structural",
            "inputs": {
                "CONTEXT.md": encoded(oversize),
                "CONTEXT.html": encoded(b"<html></html>"),
            },
        },
    )
    result = assert_error(process, "input-too-large")
    assert result["error"]["details"]["role"] == "source"  # type: ignore[index]

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")
    escaped = run_host_api(
        root,
        {
            "version": 1,
            "operation": "discover",
            "paths": ["linked/CONTEXT.md"],
        },
    )
    assert_error(escaped, "path-escape")


def test_candidate_check_rejects_non_target_paths_and_bad_stage(tmp_path: Path) -> None:
    source_bytes, html_bytes = glossary_pair()
    non_target = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "README.md",
            "stage": "structural",
            "inputs": {
                "README.md": encoded(b"# Readme\n"),
            },
        },
    )
    assert_error(non_target, "not-target")

    bad_stage = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": "CONTEXT.md",
            "stage": "publish",
            "inputs": {
                "CONTEXT.md": encoded(source_bytes),
                "CONTEXT.html": encoded(html_bytes),
            },
        },
    )
    assert_error(bad_stage, "invalid-stage")


def test_final_receipt_path_is_confined_and_schema_errors_are_explicit(
    tmp_path: Path,
) -> None:
    source_bytes, html_bytes = semantic_pair()
    receipt = build_receipt(
        source_path=SEMANTIC_SOURCE,
        source_bytes=source_bytes,
        html_path=SEMANTIC_HTML,
        html_bytes=html_bytes,
    )
    bad_path = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": "docs/adr/receipt.json",
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
            },
        },
    )
    assert_error(bad_path, "invalid-receipt-path")

    invalid_json = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(b"{"),
            },
        },
    )
    assert_error(invalid_json, "receipt-invalid-json")

    unsupported = dict(receipt)
    unsupported["version"] = 2
    unsupported_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(unsupported).encode("utf-8")),
            },
        },
    )
    assert_error(unsupported_process, "unsupported-version")

    missing_field = dict(receipt)
    del missing_field["verification"]
    schema_process = run_host_api(
        tmp_path,
        {
            "version": 1,
            "operation": "candidate-check",
            "path": SEMANTIC_SOURCE,
            "stage": "final",
            "receipt": RECEIPT_PATH,
            "inputs": {
                SEMANTIC_SOURCE: encoded(source_bytes),
                SEMANTIC_HTML: encoded(html_bytes),
                CSS_PATH: encoded(b"/* fixture stylesheet */\n"),
                RECEIPT_PATH: encoded(json.dumps(missing_field).encode("utf-8")),
            },
        },
    )
    assert_error(schema_process, "receipt-schema")


def test_host_api_rejects_command_line_arguments(tmp_path: Path) -> None:
    process = subprocess.run(
        [str(CLI), "host-api", "capabilities"],
        cwd=tmp_path,
        input="",
        text=True,
        capture_output=True,
    )

    assert_error(process, "invalid-request")
