from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sddlib.html_policy import parse_html, validate_html
from sddlib.html_semantic import (
    SEMANTIC_LIMITATION,
    detect_contract,
    validate_semantic_companion,
)
from sddlib.html_units import scan_markdown, strict_requirements


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

GLOSSARY_MARKDOWN = (
    "# Ordering\n"
    "\n"
    "Tracks customer orders.\n"
    "\n"
    "## Terms\n"
    "\n"
    "**Order**:\n"
    "A customer's request for goods.\n"
    "\n"
    "_Avoid_: Purchase, transaction\n"
)

GLOSSARY_BODY = """\
<h1 id="ordering">Ordering</h1>
<p id="intro">Tracks customer orders.</p>
<aside aria-label="Document outline">
<details open>
<summary>On this page</summary>
<nav aria-label="On this page"><a href="#terms">Terms</a></nav>
</details>
</aside>
<section>
<h2 id="terms">Terms</h2>
<dl>
<div class="term-entry">
<dt id="term-order">Order</dt>
<dd id="def-order">A customer's request for goods.
<p class="avoid-terms"><strong>Avoid:</strong> Purchase, transaction</p></dd>
</div>
</dl>
</section>
"""

GLOSSARY_TARGETS = {
    "heading": ["ordering", "terms"],
    "paragraph": ["intro"],
    "glossary_term": ["term-order"],
    "glossary_avoid": ["def-order"],
}

PLAN_MARKDOWN = (
    "# Example plan\n"
    "\n"
    "Intro.\n"
    "\n"
    "## Task 1: First\n"
    "\n"
    "First body.\n"
    "\n"
    "## Task 2: Second\n"
    "\n"
    "Second body.\n"
)

PLAN_BODY = """\
<h1 id="example-plan">Example plan</h1>
<aside aria-label="Document outline">
<details open>
<summary>On this page</summary>
<nav aria-label="On this page">
<a href="#task-1-first">Task 1: First</a>
<a href="#task-2-second">Task 2: Second</a>
</nav>
</details>
</aside>
<p id="intro">Intro.</p>
<article class="task-article" data-task-number="1">
<h2 id="task-1-first">Task 1: First</h2>
<p id="first">First body.</p>
</article>
<article class="task-article" data-task-number="2">
<h2 id="task-2-second">Task 2: Second</h2>
<p id="second">Second body.</p>
</article>
"""

PLAN_TARGETS = {
    "heading": ["example-plan", "task-1-first", "task-2-second"],
    "paragraph": ["intro", "first", "second"],
}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _target_map(
    markdown: str, by_kind: dict[str, list[str]]
) -> dict[str, str]:
    counters: dict[str, int] = {}
    targets: dict[str, str] = {}
    for unit in scan_markdown(markdown).units:
        index = counters.get(unit.kind, 0)
        counters[unit.kind] = index + 1
        values = by_kind.get(unit.kind, [])
        if index < len(values):
            targets[unit.id] = values[index]
    return targets


def _unit_id(markdown: str, kind: str, index: int = 0) -> str:
    return [
        unit.id for unit in scan_markdown(markdown).units if unit.kind == kind
    ][index]


def _mappings(
    markdown: str, targets: dict[str, str | list[str]]
) -> list[dict[str, object]]:
    mappings: list[dict[str, object]] = []
    for unit in scan_markdown(markdown).units:
        value = targets.get(unit.id)
        if value is None:
            continue
        mappings.append(
            {
                "unit": unit.id,
                "representation": "paraphrase",
                "targets": value if isinstance(value, list) else [value],
            }
        )
    return mappings


def _strict(
    markdown: str, mappings: list[dict[str, object]]
) -> list[dict[str, object]]:
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


def _provenance(
    markdown: str,
    mappings: list[dict[str, object]],
    *,
    source_path: str,
    strict: list[dict[str, object]] | None = None,
    supplementary: list[dict[str, object]] | None = None,
    calculations: list[dict[str, object]] | None = None,
    digest: str | None = None,
    units: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    scan = scan_markdown(markdown)
    document_digest = digest or scan.digest
    compact = (
        units
        if units is not None
        else [
            {
                "id": unit.id,
                "kind": unit.kind,
                "source_digest": unit.digest,
                "range": {"start": unit.start, "end": unit.end},
                "parent": unit.parent,
            }
            for unit in scan.units
        ]
    )
    if digest is not None:
        compact = [{**unit, "source_digest": digest} for unit in compact]
    return {
        "schema": "sdd-provenance",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": source_path, "digest": document_digest},
        "units": compact,
        "mappings": mappings,
        "strict": strict if strict is not None else _strict(markdown, mappings),
        "supplementary": supplementary or [],
        "calculations": calculations or [],
    }


def _build_provenance(
    markdown: str,
    by_kind: dict[str, list[str]],
    *,
    source_path: str,
    **kwargs: object,
) -> dict[str, object]:
    return _provenance(
        markdown,
        _mappings(markdown, _target_map(markdown, by_kind)),
        source_path=source_path,
        **kwargs,  # type: ignore[arg-type]
    )


def _companion(
    markdown: str,
    body: str,
    provenance: dict[str, object],
    *,
    contract: str | None = "semantic-v1",
    css_href: str = "docs/sdd/assets/sdd.css",
    head_extra: str = "",
    template: bool = True,
) -> str:
    contract_meta = (
        f'<meta name="sdd-html-contract" content="{contract}">\n'
        if contract is not None
        else ""
    )
    provenance_template = (
        '<template id="sdd-provenance">'
        + json.dumps(provenance, ensure_ascii=False)
        + "</template>\n"
        if template
        else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
        f'<meta name="sdd-source-digest" content="{_digest(markdown.encode("utf-8"))}">\n'
        f"{contract_meta}"
        f"{head_extra}"
        "<title>Example document</title>\n"
        f'<link rel="stylesheet" href="{css_href}">\n'
        "</head>\n"
        "<body>\n"
        '<a class="skip-link" href="#content">Skip to content</a>\n'
        '<header class="document-header"><p class="document-kind">ADR</p></header>\n'
        '<main id="content" tabindex="-1">\n'
        f"{body}"
        f"{provenance_template}"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def _write_pair(
    root: Path,
    markdown: str,
    html: str,
    *,
    relative: str = "docs/adr/0001-choice.md",
) -> Path:
    source = root / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(markdown, encoding="utf-8")
    source.with_suffix(".html").write_text(html, encoding="utf-8")
    css = root / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* fixture stylesheet */\n", encoding="utf-8")
    return source


def _adr_companion(
    markdown: str = ADR_MARKDOWN,
    body: str = ADR_BODY,
    provenance: dict[str, object] | None = None,
) -> str:
    if provenance is None:
        provenance = _build_provenance(
            markdown, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
        )
    return _companion(
        markdown, body, provenance, css_href="../sdd/assets/sdd.css"
    )


def _semantic(html: str, markdown: str, *, kind: str | None = None, source_path: str = "docs/adr/0001-choice.md"):
    return validate_semantic_companion(
        parse_html(html),
        html.encode("utf-8"),
        markdown.encode("utf-8"),
        source_path=source_path,
        document_kind=kind,
    )


def _violation_codes(result: dict[str, object]) -> set[str]:
    return {item["code"] for item in result["violations"]}  # type: ignore[index]


def _issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_correct_reconstruction_passes_static_semantic_coverage(
    tmp_path: Path,
) -> None:
    source = _write_pair(tmp_path, ADR_MARKDOWN, _adr_companion())

    result = validate_html(tmp_path, source)

    assert result["decision"] == "allow", result
    assert result["contract"] == "semantic-v1"
    assert result["assurance"] == "static-only"
    assert result["semantic"]["assurance"] == "static-only"  # type: ignore[index]
    assert SEMANTIC_LIMITATION in result["semantic"]["limitations"]  # type: ignore[index]
    assert result["violations"] == []
    assert result["semantic"]["counts"] == {  # type: ignore[index]
        "units": 6,
        "mappings": 6,
        "strict_targets": 3,
        "supplementary": 0,
        "calculations": 0,
    }


def test_paraphrase_and_dom_reordering_pass_but_strict_rejects_the_same_html(
    tmp_path: Path,
) -> None:
    summary = (
        '<p id="summary">We use <code id="fifo">FIFO</code>; the window is '
        "750 ms and the limit is at most 2 MiB.</p>\n"
    )
    reordered = ADR_BODY.replace(summary, "").replace(
        "</article>", summary + "</article>"
    )
    source = _write_pair(tmp_path, ADR_MARKDOWN, _adr_companion(body=reordered))
    assert validate_html(tmp_path, source)["decision"] == "allow"

    strict_html = _adr_companion(body=reordered).replace(
        '<meta name="sdd-html-contract" content="semantic-v1">\n', ""
    )
    source.with_suffix(".html").write_text(strict_html, encoding="utf-8")
    strict = validate_html(tmp_path, source)
    assert strict["decision"] == "deny"
    assert {"heading-structure", "source-text"} & _violation_codes(strict)


def test_unknown_contract_is_rejected_without_strict_fallback(
    tmp_path: Path,
) -> None:
    html = _adr_companion().replace(
        'content="semantic-v1"', 'content="semantic-v2"'
    )
    source = _write_pair(tmp_path, ADR_MARKDOWN, html)

    result = validate_html(tmp_path, source)

    assert result["decision"] == "deny"
    assert "contract-unknown" in _violation_codes(result)
    assert "source-text" not in _violation_codes(result)


def test_missing_contract_falls_back_to_strict_and_duplicate_is_rejected(
    tmp_path: Path,
) -> None:
    missing = _adr_companion().replace(
        '<meta name="sdd-html-contract" content="semantic-v1">\n', ""
    )
    source = _write_pair(tmp_path, ADR_MARKDOWN, missing)
    strict = validate_html(tmp_path, source)
    assert strict["contract"] == "strict"
    assert strict["decision"] == "deny"
    assert {"heading-structure", "source-text"} & _violation_codes(strict)

    duplicate = _adr_companion().replace(
        '<meta name="sdd-html-contract" content="semantic-v1">',
        '<meta name="sdd-html-contract" content="semantic-v1">'
        '<meta name="sdd-html-contract" content="semantic-v1">',
    )
    source.with_suffix(".html").write_text(duplicate, encoding="utf-8")
    result = validate_html(tmp_path, source)
    assert "contract-duplicate" in _violation_codes(result)


def test_provenance_units_are_compared_by_definition_not_array_order() -> None:
    html = _adr_companion()
    provenance_text = html.split('<template id="sdd-provenance">', 1)[1].split(
        "</template>", 1
    )[0]
    provenance = json.loads(provenance_text)
    provenance["units"] = list(reversed(provenance["units"]))
    reordered = (
        html.split('<template id="sdd-provenance">', 1)[0]
        + '<template id="sdd-provenance">'
        + json.dumps(provenance)
        + "</template>"
        + html.split("</template>", 1)[1]
    )

    result = _semantic(reordered, ADR_MARKDOWN)

    assert result.ok, result.issues


def test_missing_and_unknown_units_are_reported() -> None:
    provenance = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    missing_id = provenance["mappings"][0]["unit"]  # type: ignore[index]
    provenance["mappings"] = provenance["mappings"][1:]  # type: ignore[index]
    provenance["units"] = [
        unit for unit in provenance["units"] if unit["id"] != missing_id  # type: ignore[index]
    ]
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "unit-missing" in _issue_codes(result)

    scan = scan_markdown(ADR_MARKDOWN)
    extra_unit = {
        "id": "paragraph-999999",
        "kind": "paragraph",
        "source_digest": scan.digest,
        "range": {"start": 0, "end": 0},
        "parent": None,
    }
    fresh = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    provenance = _build_provenance(
        ADR_MARKDOWN,
        ADR_TARGETS,
        source_path="docs/adr/0001-choice.md",
        units=[*fresh["units"], extra_unit],  # type: ignore[misc]
    )
    provenance["mappings"].append(  # type: ignore[union-attr]
        {
            "unit": "paragraph-999999",
            "representation": "summary",
            "targets": ["summary"],
        }
    )
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "unit-unknown" in _issue_codes(result)


def test_unit_definition_mismatch_is_reported() -> None:
    provenance = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    provenance["units"][1]["range"]["end"] += 1  # type: ignore[index]
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "unit-mismatch" in _issue_codes(result)


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (
            lambda html: html.replace(
                'href="../plans/2026-01-01-plan.md"',
                'href="https://evil.example/phish"',
            ),
            "link-missing",
        ),
        (
            lambda html: html.replace('id="summary"', 'id="missing"'),
            "target-missing",
        ),
        (
            lambda html: html.replace(
                '<p id="summary">', '<p id="summary" hidden>'
            ),
            "target-hidden",
        ),
        (
            lambda html: html.replace(
                '<p id="summary">We use',
                '<template id="hidden-body"><p id="summary">We use',
            ).replace("2 MiB.</p>", "2 MiB.</p></template>"),
            "target-hidden",
        ),
        (
            lambda html: html.replace(
                '<p id="decision">',
                '<p id="summary">duplicate summary</p><p id="decision">',
            ),
            "target-duplicate",
        ),
    ),
)
def test_mappings_need_a_unique_visible_target(mutate, code: str) -> None:
    result = _semantic(mutate(_adr_companion()), ADR_MARKDOWN)
    assert code in _issue_codes(result), result.issues


def test_duplicate_target_reference_and_missing_mapping_are_rejected() -> None:
    provenance = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    provenance["mappings"][0]["targets"] = [  # type: ignore[index]
        "queue-choice",
        "queue-choice",
    ]
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "target-duplicate-reference" in _issue_codes(result)

    provenance = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    provenance["mappings"] = provenance["mappings"][1:]  # type: ignore[index]
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "mapping-missing" in _issue_codes(result)


def test_code_value_change_is_rejected(tmp_path: Path) -> None:
    html = _adr_companion().replace(
        '<code id="fifo">FIFO</code>', '<code id="fifo">FILO</code>'
    )
    source = _write_pair(tmp_path, ADR_MARKDOWN, html)
    result = validate_html(tmp_path, source)
    assert "strict-value-missing" in _violation_codes(result)


def test_paths_and_identifiers_must_survive_exactly() -> None:
    markdown = (
        "# Tools\n"
        "\n"
        "Call parse_html for docs/sdd/specs/example.md.\n"
    )
    body = (
        '<article><h1 id="tools">Tools</h1>'
        '<p id="body">Call parseHtml for docs/sdd/specs/other.md.</p>'
        "</article>"
    )
    provenance = _build_provenance(
        markdown,
        {"heading": ["tools"], "paragraph": ["body"]},
        source_path="docs/adr/0001-choice.md",
    )
    result = _semantic(_companion(markdown, body, provenance), markdown)
    codes = _issue_codes(result)
    assert "path-missing" in codes
    assert "identifier-missing" in codes


def test_strict_entry_cannot_be_removed_or_invented() -> None:
    provenance = _build_provenance(
        ADR_MARKDOWN, ADR_TARGETS, source_path="docs/adr/0001-choice.md"
    )
    provenance["strict"] = provenance["strict"][:-1]  # type: ignore[index]
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "strict-missing" in _issue_codes(result)

    provenance["strict"].append(  # type: ignore[union-attr]
        {
            "unit": _unit_id(ADR_MARKDOWN, "paragraph"),
            "category": "code",
            "value": "not in the source",
            "targets": ["summary"],
        }
    )
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert "strict-unknown" in _issue_codes(result)


def test_number_unit_and_operator_mismatches_are_rejected(tmp_path: Path) -> None:
    unit_html = _adr_companion().replace("750 ms", "750 s")
    source = _write_pair(tmp_path, ADR_MARKDOWN, unit_html)
    assert "unit-mismatch" in _violation_codes(validate_html(tmp_path, source))

    missing_html = _adr_companion().replace(" at most 2 MiB", "")
    source.with_suffix(".html").write_text(missing_html, encoding="utf-8")
    assert "number-missing" in _violation_codes(validate_html(tmp_path, source))


def test_comparison_operator_must_survive() -> None:
    markdown = "# Limits\n\nLatency <= 750 ms is required.\n"
    body = (
        '<article><h1 id="limits">Limits</h1>'
        '<p id="limit">Latency is 750 ms.</p></article>'
    )
    provenance = _build_provenance(
        markdown,
        {"heading": ["limits"], "paragraph": ["limit"]},
        source_path="docs/adr/0001-choice.md",
    )
    result = _semantic(
        _companion(markdown, body, provenance), markdown
    )
    assert "operator-mismatch" in _issue_codes(result)


def test_invented_visible_number_is_rejected() -> None:
    html = _adr_companion().replace(
        "</article>", '<p id="invented">Throughput is 42 items.</p></article>'
    )
    result = _semantic(html, ADR_MARKDOWN)
    assert "number-invented" in _issue_codes(result)


def test_verified_sum_calculation_passes_and_wrong_result_is_rejected() -> None:
    calculation = {
        "id": "window-total",
        "operation": "sum",
        "inputs": [
            {
                "value": 750,
                "unit": "ms",
                "source": _unit_id(ADR_MARKDOWN, "paragraph"),
            },
            {"value": 250, "unit": "ms", "source": None},
        ],
        "formula": "750 + 250",
        "result": {"value": 1000, "unit": "ms"},
    }
    body = ADR_BODY.replace(
        "</article>", '<p id="total">Total window: 1000 ms.</p></article>'
    )
    provenance = _build_provenance(
        ADR_MARKDOWN,
        ADR_TARGETS,
        source_path="docs/adr/0001-choice.md",
        calculations=[calculation],
    )
    result = _semantic(
        _companion(ADR_MARKDOWN, body, provenance), ADR_MARKDOWN
    )
    assert result.ok, result.issues

    provenance["calculations"][0]["result"]["value"] = 1001  # type: ignore[index]
    result = _semantic(
        _companion(ADR_MARKDOWN, body, provenance), ADR_MARKDOWN
    )
    assert "calculation-result" in _issue_codes(result)
    assert "calculation-result-missing" in _issue_codes(result)
    assert "number-invented" in _issue_codes(result)


def test_ratio_scale_and_count_recompute_from_explicit_inputs() -> None:
    calculations = [
        {
            "id": "ratio",
            "operation": "ratio",
            "inputs": [
                {"value": 750, "unit": "ms", "source": None},
                {"value": 250, "unit": "ms", "source": None},
            ],
            "formula": "750 / 250",
            "result": {"value": 3, "unit": None},
        },
        {
            "id": "scale",
            "operation": "scale",
            "inputs": [
                {"value": 750, "unit": "ms", "source": None},
                {"value": 2, "unit": None, "source": None},
            ],
            "formula": "750 * 2",
            "result": {"value": 1500, "unit": "ms"},
        },
        {
            "id": "count",
            "operation": "count",
            "inputs": [
                {"value": 1, "unit": None, "source": None},
                {"value": 1, "unit": None, "source": None},
            ],
            "formula": "count(inputs)",
            "result": {"value": 2, "unit": None},
        },
    ]
    body = ADR_BODY.replace(
        "</article>",
        '<p id="computed">Ratio 3. Scaled 1500 ms. Count 2.</p></article>',
    )
    provenance = _build_provenance(
        ADR_MARKDOWN,
        ADR_TARGETS,
        source_path="docs/adr/0001-choice.md",
        calculations=calculations,
    )
    result = _semantic(_companion(ADR_MARKDOWN, body, provenance), ADR_MARKDOWN)
    assert result.ok, result.issues


def test_calculation_rejects_eval_formula_and_unlisted_operation() -> None:
    calculation = {
        "id": "unverifiable",
        "operation": "sum",
        "inputs": [{"value": 1, "unit": None, "source": None}],
        "formula": "eval('1')",
        "result": {"value": 1, "unit": None},
    }
    body = ADR_BODY.replace(
        "</article>", '<p id="computed">Computed: 1.</p></article>'
    )
    provenance = _build_provenance(
        ADR_MARKDOWN,
        ADR_TARGETS,
        source_path="docs/adr/0001-choice.md",
        calculations=[calculation],
    )
    result = _semantic(
        _companion(ADR_MARKDOWN, body, provenance), ADR_MARKDOWN
    )
    assert "calculation-formula" in _issue_codes(result)

    provenance["calculations"][0]["operation"] = "sqrt"  # type: ignore[index]
    result = _semantic(
        _companion(ADR_MARKDOWN, body, provenance), ADR_MARKDOWN
    )
    assert "provenance-schema" in _issue_codes(result)


def test_stale_provenance_digest_is_reported_as_information_unavailable() -> None:
    provenance = _build_provenance(
        ADR_MARKDOWN,
        ADR_TARGETS,
        source_path="docs/adr/0001-choice.md",
        digest="sha256:" + "0" * 64,
    )
    result = _semantic(
        _companion(ADR_MARKDOWN, ADR_BODY, provenance), ADR_MARKDOWN
    )
    assert _issue_codes(result) == {"source-stale"}


def test_incomplete_source_scan_does_not_pass_coverage() -> None:
    markdown = (
        "# Limits\n"
        "\n"
        "See [the reference][ref].\n"
        "\n"
        "[ref]: https://example.com\n"
    )
    body = (
        '<article><h1 id="limits">Limits</h1>'
        '<p id="reference">See the reference.</p></article>'
    )
    provenance = _build_provenance(
        markdown,
        {"heading": ["limits"], "paragraph": ["reference"]},
        source_path="docs/adr/0001-choice.md",
    )
    result = _semantic(_companion(markdown, body, provenance), markdown)
    assert _issue_codes(result) == {"source-incomplete"}


def test_glossary_canonical_term_and_avoid_entries_are_preserved() -> None:
    provenance = _build_provenance(
        GLOSSARY_MARKDOWN,
        GLOSSARY_TARGETS,
        source_path="CONTEXT.md",
    )
    html = _companion(
        GLOSSARY_MARKDOWN,
        GLOSSARY_BODY,
        provenance,
    ).replace(
        '<header class="document-header"><p class="document-kind">ADR</p></header>',
        '<header class="document-header"><p class="document-kind">Glossary</p></header>',
    )
    result = _semantic(
        html, GLOSSARY_MARKDOWN, kind="context", source_path="CONTEXT.md"
    )
    assert result.ok, result.issues

    changed = html.replace(
        '<dt id="term-order">Order</dt>',
        '<dt id="term-order">Ordering</dt>',
    )
    result = _semantic(
        changed, GLOSSARY_MARKDOWN, kind="context", source_path="CONTEXT.md"
    )
    assert "strict-value-missing" in _issue_codes(result)


def test_plan_task_order_is_preserved() -> None:
    provenance = _build_provenance(
        PLAN_MARKDOWN,
        PLAN_TARGETS,
        source_path="docs/sdd/plans/2026-01-01-example.md",
    )
    result = _semantic(
        _companion(PLAN_MARKDOWN, PLAN_BODY, provenance),
        PLAN_MARKDOWN,
        kind="plan",
        source_path="docs/sdd/plans/2026-01-01-example.md",
    )
    assert result.ok, result.issues

    first_start = PLAN_BODY.index(
        '<article class="task-article" data-task-number="1">'
    )
    second_start = PLAN_BODY.index(
        '<article class="task-article" data-task-number="2">'
    )
    first = PLAN_BODY[first_start:second_start]
    second = PLAN_BODY[second_start:]
    reordered = PLAN_BODY[:first_start] + second + first
    result = _semantic(
        _companion(PLAN_MARKDOWN, reordered, provenance),
        PLAN_MARKDOWN,
        kind="plan",
        source_path="docs/sdd/plans/2026-01-01-example.md",
    )
    assert "plan-task-order" in _issue_codes(result)


def test_contract_detection_returns_strict_without_meta() -> None:
    document = parse_html("<html><head></head><body></body></html>")
    assert detect_contract(document).contract == "strict"
