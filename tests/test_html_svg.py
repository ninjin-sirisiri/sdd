from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

import pytest

from sddlib.html_policy import parse_html, validate_html
from sddlib.html_svg import (
    MAX_SVG_ELEMENTS,
    inspect_svg,
    validate_diagram_representations,
)
from sddlib.html_units import (
    UnitSchemaError,
    scan_markdown,
    strict_requirements,
    validate_provenance,
)


CSP = (
    "default-src &#x27;none&#x27;; img-src &#x27;self&#x27; data:; "
    "style-src &#x27;self&#x27;; base-uri &#x27;none&#x27;; "
    "form-action &#x27;none&#x27;; frame-ancestors &#x27;none&#x27;"
)
DIGEST = "sha256:" + "a" * 64
FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _codes(issues) -> set[str]:
    return {issue.code for issue in issues}


def _main(body: str):
    document = parse_html(f'<main id="content">{body}</main>')
    main = next(node for node in document.nodes if node.tag == "main")
    return document, main


def _provenance(supplementary: list[dict[str, object]]) -> dict[str, object]:
    unit_id = "paragraph-000000"
    return {
        "schema": "sdd-provenance",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": "docs/adr/0001-flow.md", "digest": DIGEST},
        "units": [
            {
                "id": unit_id,
                "kind": "paragraph",
                "source_digest": DIGEST,
                "range": {"start": 0, "end": 16},
                "parent": None,
            }
        ],
        "mappings": [
            {
                "unit": unit_id,
                "representation": "paraphrase",
                "targets": ["body"],
            }
        ],
        "strict": [],
        "supplementary": supplementary,
        "calculations": [],
    }


def _diagram(
    *,
    node_ids: tuple[str, str] = ("node-plan", "node-verify"),
    labels: tuple[str, str] = ("Plan", "Verify"),
    edge_label: str = "then",
    units: tuple[str, ...] = ("paragraph-000000",),
) -> dict[str, object]:
    return {
        "id": "diagram-flow",
        "kind": "diagram",
        "units": list(units),
        "targets": ["fig-flow"],
        "description": "Plan then verify.",
        "diagram": {
            "nodes": [
                {"id": node_ids[0], "label": labels[0], "units": list(units)},
                {"id": node_ids[1], "label": labels[1], "units": list(units)},
            ],
            "edges": [
                {
                    "id": "edge-plan-verify",
                    "label": edge_label,
                    "from": node_ids[0],
                    "to": node_ids[1],
                    "units": list(units),
                }
            ],
        },
    }


def _graph(
    *,
    series_label: str = "Latency",
    series_unit: str | None = "ms",
    axis_labels: tuple[str, str] = ("Run", "Latency"),
    values: tuple[tuple[int, int, int], ...] = ((1, 1, 750), (2, 2, 820)),
) -> dict[str, object]:
    return {
        "id": "graph-latency",
        "kind": "graph",
        "units": ["paragraph-000000"],
        "targets": ["fig-graph"],
        "description": "Latency by run.",
        "graph": {
            "series": [
                {
                    "id": "series-latency",
                    "label": series_label,
                    "unit": series_unit,
                    "units": ["paragraph-000000"],
                    "values": [
                        {"id": f"value-{value[0]}", "x": value[1], "y": value[2]}
                        for value in values
                    ],
                }
            ],
            "axes": [
                {
                    "id": "axis-x",
                    "dimension": "x",
                    "label": axis_labels[0],
                    "unit": None,
                    "units": ["paragraph-000000"],
                },
                {
                    "id": "axis-y",
                    "dimension": "y",
                    "label": axis_labels[1],
                    "unit": "ms",
                    "units": ["paragraph-000000"],
                },
            ],
        },
    }


DIAGRAM_SVG = """\
<svg class="sdd-figure-svg" role="img" aria-labelledby="fig-flow-caption" viewBox="0 0 400 160">
<title>Plan then verify</title>
<desc>A two-step flow from Plan to Verify.</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z"/></marker></defs>
<g id="node-plan" class="sdd-node"><rect class="sdd-node-shape" x="20" y="40" width="120" height="60" rx="8"/><text x="80" y="75" text-anchor="middle">Plan</text></g>
<g id="node-verify" class="sdd-node"><rect class="sdd-node-shape" x="260" y="40" width="120" height="60" rx="8"/><text x="320" y="75" text-anchor="middle">Verify</text></g>
<g id="edge-plan-verify" class="sdd-edge"><line class="sdd-edge-line" x1="140" y1="70" x2="260" y2="70" marker-end="url(#arrow)"/><text x="200" y="58" text-anchor="middle">then</text></g>
</svg>
"""

GRAPH_SVG = """\
<svg class="sdd-figure-svg" role="img" aria-labelledby="fig-graph-caption" viewBox="0 0 480 240">
<title>Latency by run</title>
<g id="axis-x" class="sdd-axis"><line class="sdd-axis-line" x1="60" y1="200" x2="440" y2="200"/><text x="250" y="230" text-anchor="middle">Run</text></g>
<g id="axis-y" class="sdd-axis"><line class="sdd-axis-line" x1="60" y1="20" x2="60" y2="200"/><text x="90" y="24">Latency (ms)</text></g>
<g id="series-latency" class="sdd-series sdd-series-1"><polyline points="120,120 220,90"/><text x="330" y="60">Latency</text></g>
</svg>
"""


def _figure(
    svg: str,
    *,
    figure_id: str = "fig-flow",
    caption: str = "Plan then verify.",
    caption_id: str = "fig-flow-caption",
    explanation: str = "The plan step runs before verification.",
    table: str | None = None,
    figure_class: str = "sdd-figure",
    extra: str = "",
) -> str:
    if table is None:
        table = (
            '<table class="sdd-data-table">'
            "<caption>Flow steps</caption>"
            "<thead><tr><th scope=\"col\">From</th>"
            "<th scope=\"col\">Relation</th><th scope=\"col\">To</th></tr></thead>"
            "<tbody><tr><td>Plan</td><td>then</td><td>Verify</td></tr></tbody>"
            "</table>"
        )
    caption_html = (
        f'<figcaption id="{caption_id}">{caption}</figcaption>'
        if caption
        else ""
    )
    return (
        f'<figure class="{figure_class}" id="{figure_id}">'
        f"{svg}{caption_html}"
        f'<p class="sdd-figure-explanation">{explanation}</p>'
        f"{table}{extra}</figure>"
    )


# ---------------------------------------------------------------------------
# SVG allowlist and complexity


def test_allowed_static_diagram_svg_passes_allowlist() -> None:
    document = parse_html(_figure(DIAGRAM_SVG))

    assert inspect_svg(document) == ()


def test_script_event_foreign_object_and_style_are_rejected() -> None:
    document = parse_html(
        '<svg viewBox="0 0 10 10">'
        '<script>alert(1)</script>'
        '<style>rect { fill: red; }</style>'
        '<rect width="10" height="10" onclick="run()" style="fill:red"/>'
        '<foreignObject><div>html</div></foreignObject>'
        "</svg>"
    )

    codes = _codes(inspect_svg(document))

    assert {
        "svg-script",
        "svg-style",
        "svg-event-attribute",
        "svg-foreign-object",
    } <= codes


def test_external_urls_animation_and_unknown_attributes_are_rejected() -> None:
    document = parse_html(
        '<svg viewBox="0 0 10 10">'
        '<rect width="10" height="10" fill="url(https://example.com/paint)"/>'
        '<path d="M0,0 L10,10" marker-end="url(https://example.com/arrow)"/>'
        '<animate attributeName="x" from="0" to="10" dur="1s"/>'
        '<animateTransform attributeName="transform" type="rotate" from="0" to="90"/>'
        '<circle cx="5" cy="5" r="2" font-size="20" data-extra="x"/>'
        "</svg>"
    )

    codes = _codes(inspect_svg(document))

    assert "svg-external-reference" in codes
    assert "svg-animation" in codes
    assert "svg-attribute" in codes


def test_marker_and_aria_references_must_resolve() -> None:
    broken = parse_html(
        '<svg aria-labelledby="missing" viewBox="0 0 10 10">'
        '<path d="M0,0 L10,10" marker-end="url(#missing-marker)"/>'
        "</svg>"
    )
    assert _codes(inspect_svg(broken)) >= {"svg-reference"}

    allowed = parse_html(
        '<svg aria-labelledby="caption" viewBox="0 0 10 10">'
        '<title id="caption">Arrow</title>'
        '<defs><marker id="arrow" markerWidth="4" markerHeight="4" refX="2" refY="2"><path d="M0,0 L4,2 L0,4 z"/></marker></defs>'
        '<path d="M0,0 L10,10" marker-end="url(#arrow)"/>'
        "</svg>"
    )
    assert inspect_svg(allowed) == ()


def test_complexity_limit_is_a_failure_that_asks_for_simplification() -> None:
    at_limit = parse_html(
        '<svg viewBox="0 0 10 10">'
        + '<circle cx="1" cy="1" r="1"/>' * (MAX_SVG_ELEMENTS - 1)
        + "</svg>"
    )
    assert inspect_svg(at_limit) == ()

    over_limit = parse_html(
        '<svg viewBox="0 0 10 10">'
        + '<circle cx="1" cy="1" r="1"/>' * MAX_SVG_ELEMENTS
        + "</svg>"
    )
    issues = inspect_svg(over_limit)

    assert [issue.code for issue in issues] == ["svg-complexity"]
    assert str(MAX_SVG_ELEMENTS + 1) in issues[0].message
    assert "Simplify" in issues[0].message
    assert "truncat" in issues[0].message


def test_complexity_counts_across_every_svg_in_the_document() -> None:
    half = MAX_SVG_ELEMENTS // 2
    document = parse_html(
        '<svg viewBox="0 0 10 10">'
        + '<circle cx="1" cy="1" r="1"/>' * (half - 1)
        + "</svg>"
        '<svg viewBox="0 0 10 10">'
        + '<circle cx="1" cy="1" r="1"/>' * (half + 5)
        + "</svg>"
    )

    assert "svg-complexity" in _codes(inspect_svg(document))


def test_checked_in_browser_fixture_uses_only_allowed_static_svg() -> None:
    fixture = FIXTURE_ROOT / "svg" / "figure.html"
    document = parse_html(fixture.read_text(encoding="utf-8"))

    assert inspect_svg(document) == ()


# ---------------------------------------------------------------------------
# Diagram and graph provenance schema


def test_provenance_schema_accepts_diagram_and_graph_structures() -> None:
    provenance = _provenance([_diagram(), _graph()])
    provenance["supplementary"][1]["targets"] = ["fig-graph"]

    validated = validate_provenance(provenance)

    assert [item["kind"] for item in validated["supplementary"]] == [
        "diagram",
        "graph",
    ]


@pytest.mark.parametrize(
    "mutate",
    (
        lambda item: item["diagram"].pop("diagram"),
        lambda item: item["diagram"]["diagram"]["edges"][0].__setitem__(
            "from", "missing"
        ),
        lambda item: item["diagram"]["diagram"]["nodes"][0].__setitem__(
            "units", ["heading-000000"]
        ),
        lambda item: item["graph"]["graph"]["axes"].pop(),
        lambda item: item["graph"]["graph"]["series"][0]["values"][0].__setitem__(
            "x", "one"
        ),
        lambda item: item["graph"]["graph"]["series"][0].__setitem__(
            "values", []
        ),
        lambda item: item["graph"]["graph"]["axes"][1].__setitem__(
            "dimension", "x"
        ),
        lambda item: item["diagram"].__setitem__(
            "graph", item["graph"]["graph"]
        ),
    ),
)
def test_provenance_schema_rejects_dangling_diagram_and_graph_evidence(
    mutate,
) -> None:
    diagram = _diagram()
    graph = _graph()
    graph["targets"] = ["fig-graph"]
    provenance = _provenance([diagram, graph])
    mutate({"diagram": diagram, "graph": graph})

    with pytest.raises(UnitSchemaError):
        validate_provenance(provenance)


def test_provenance_schema_requires_the_matching_supplementary_kind() -> None:
    summary = {
        "id": "summary-1",
        "kind": "summary",
        "units": ["paragraph-000000"],
        "targets": ["summary"],
        "diagram": _diagram()["diagram"],
    }

    with pytest.raises(UnitSchemaError, match="matching kind"):
        validate_provenance(_provenance([summary]))


def test_existing_provenance_fixture_still_validates() -> None:
    fixture = json.loads(
        (FIXTURE_ROOT / "units" / "provenance.valid.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_provenance(fixture) == fixture


# ---------------------------------------------------------------------------
# Figure, caption, explanation, and data-table contract


def test_valid_diagram_figure_passes_static_binding() -> None:
    document, main = _main(_figure(DIAGRAM_SVG))
    provenance = _provenance([_diagram()])

    assert validate_diagram_representations(document, provenance, main) == ()


def test_valid_graph_figure_passes_static_binding() -> None:
    svg = GRAPH_SVG
    table = (
        '<table class="sdd-data-table">'
        "<caption>Latency values</caption>"
        "<thead><tr><th scope=\"col\">Run</th>"
        "<th scope=\"col\">Latency (ms)</th></tr></thead>"
        "<tbody><tr><td>1</td><td>750</td></tr>"
        "<tr><td>2</td><td>820</td></tr></tbody></table>"
    )
    document, main = _main(
        _figure(svg, figure_id="fig-graph", caption_id="fig-graph-caption", table=table)
    )
    provenance = _provenance([_graph()])

    assert validate_diagram_representations(document, provenance, main) == ()


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (
            lambda html: html.replace("<figcaption", "<p").replace(
                "</figcaption>", "</p>"
            ),
            "figure-caption",
        ),
        (
            lambda html: html.replace(
                '<p class="sdd-figure-explanation">', '<p class="other">'
            ),
            "figure-explanation",
        ),
        (
            lambda html: re.sub(r"<table.*?</table>", "", html, flags=re.S),
            "figure-table",
        ),
        (
            lambda html: html.replace('class="sdd-figure"', ""),
            "figure-class",
        ),
        (
            lambda html: html.replace('class="sdd-data-table"', ""),
            "figure-table-class",
        ),
        (
            lambda html: html.replace('class="sdd-figure-svg"', ""),
            "figure-svg-class",
        ),
    ),
)
def test_diagram_requires_caption_explanation_table_and_shared_classes(
    mutate, code
) -> None:
    document, main = _main(mutate(_figure(DIAGRAM_SVG)))
    provenance = _provenance([_diagram()])

    assert code in _codes(
        validate_diagram_representations(document, provenance, main)
    )


def test_figure_target_must_be_a_visible_figure() -> None:
    document, main = _main(
        _figure(DIAGRAM_SVG).replace('id="fig-flow"', 'id="not-a-figure"')
    )
    provenance = _provenance([_diagram()])
    assert "figure-target" in _codes(
        validate_diagram_representations(document, provenance, main)
    )

    outside = parse_html(
        f'<main id="content"></main>{_figure(DIAGRAM_SVG)}'
    )
    outside_main = next(node for node in outside.nodes if node.tag == "main")
    assert "figure-visible" in _codes(
        validate_diagram_representations(outside, provenance, outside_main)
    )

    hidden, hidden_main = _main(
        _figure(DIAGRAM_SVG).replace(
            '<figure class="sdd-figure"', '<figure hidden class="sdd-figure"'
        )
    )
    assert "figure-visible" in _codes(
        validate_diagram_representations(hidden, provenance, hidden_main)
    )


def test_diagram_nodes_and_edges_need_visible_elements_labels_and_table_rows() -> None:
    broken = (
        _figure(DIAGRAM_SVG)
        .replace('id="node-plan"', 'id="missing-node"')
        .replace(">Verify</text>", ">Review</text>")
        .replace("<td>then</td>", "<td>before</td>")
    )
    document, main = _main(broken)
    provenance = _provenance([_diagram()])

    codes = _codes(validate_diagram_representations(document, provenance, main))

    assert {
        "diagram-node-target",
        "diagram-node-label",
        "diagram-edge-table",
    } <= codes


def test_diagram_svg_needs_role_class_and_accessible_name() -> None:
    svg = (
        DIAGRAM_SVG.replace(' role="img"', "")
        .replace(' aria-labelledby="fig-flow-caption"', "")
        .replace('class="sdd-figure-svg" ', "")
    )
    document, main = _main(_figure(svg))
    provenance = _provenance([_diagram()])

    codes = _codes(validate_diagram_representations(document, provenance, main))

    assert {"figure-svg-role", "figure-svg-name", "figure-svg-class"} <= codes


def test_graph_series_axes_values_and_units_are_bound_to_evidence() -> None:
    table = (
        '<table class="sdd-data-table">'
        "<caption>Latency values</caption>"
        "<thead><tr><th scope=\"col\">Run</th>"
        "<th scope=\"col\">Latency</th></tr></thead>"
        "<tbody><tr><td>1</td><td>750</td></tr>"
        "<tr><td>2</td><td>740</td></tr></tbody></table>"
    )
    document, main = _main(
        _figure(GRAPH_SVG, figure_id="fig-graph", caption_id="fig-graph-caption", table=table)
    )
    provenance = _provenance([_graph()])

    codes = _codes(validate_diagram_representations(document, provenance, main))

    assert {
        "graph-series-unit",
        "graph-axis-unit",
        "graph-value-table",
    } <= codes


def test_graph_axes_and_series_must_have_visible_labels_and_elements() -> None:
    svg = (
        GRAPH_SVG.replace('id="axis-x"', 'id="missing-axis"')
        .replace(">Latency</text>", ">Throughput</text>")
        .replace(">Latency (ms)</text>", ">Duration (ms)</text>")
    )
    document, main = _main(
        _figure(svg, figure_id="fig-graph", caption_id="fig-graph-caption")
    )
    provenance = _provenance([_graph()])

    codes = _codes(validate_diagram_representations(document, provenance, main))

    assert {"graph-axis-target", "graph-series-label"} <= codes


def test_color_only_series_are_rejected_when_labels_are_not_visible() -> None:
    svg = (
        '<svg class="sdd-figure-svg" role="img" aria-labelledby="fig-graph-caption" viewBox="0 0 480 240">'
        '<g id="axis-x"><line x1="60" y1="200" x2="440" y2="200"/></g>'
        '<g id="axis-y"><line x1="60" y1="20" x2="60" y2="200"/></g>'
        '<g id="series-latency" class="sdd-series sdd-series-1"><polyline points="120,120 220,90" stroke="blue"/></g>'
        "</svg>"
    )
    document, main = _main(
        _figure(svg, figure_id="fig-graph", caption_id="fig-graph-caption")
    )
    provenance = _provenance([_graph()])

    codes = _codes(validate_diagram_representations(document, provenance, main))

    assert {"graph-series-label", "graph-axis-label"} <= codes


# ---------------------------------------------------------------------------
# Policy integration


def _semantic_shell(markdown: str, body: str, source_path: str, supplementary) -> str:
    scan = scan_markdown(markdown)
    targets = {
        "heading": ["flow"],
        "paragraph": ["body"],
    }
    mappings = []
    mapped_units = set()
    for unit in scan.units:
        values = targets.get(unit.kind, [])
        if not values:
            continue
        mappings.append(
            {
                "unit": unit.id,
                "representation": "paraphrase",
                "targets": values[:1],
            }
        )
        mapped_units.add(unit.id)
    strict = [
        {
            "unit": requirement["unit"],
            "category": requirement["category"],
            "value": requirement["value"],
            "targets": next(
                item["targets"] for item in mappings if item["unit"] == requirement["unit"]
            ),
        }
        for requirement in strict_requirements(scan)
        if requirement["unit"] in mapped_units
    ]
    for item in supplementary:
        for unit_id in item["units"]:
            mapped_units.add(unit_id)
    provenance = {
        "schema": "sdd-provenance",
        "version": 1,
        "contract": "semantic-v1",
        "source": {"path": source_path, "digest": _digest(markdown.encode("utf-8"))},
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
        "strict": strict,
        "supplementary": supplementary,
        "calculations": [],
    }
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
        f'<meta name="sdd-source-digest" content="{_digest(markdown.encode("utf-8"))}">\n'
        '<meta name="sdd-html-contract" content="semantic-v1">\n'
        "<title>Flow</title>\n"
        '<link rel="stylesheet" href="../sdd/assets/sdd.css">\n'
        "</head>\n"
        "<body>\n"
        '<a class="skip-link" href="#content">Skip to content</a>\n'
        '<header class="document-header"><p class="document-kind">ADR</p></header>\n'
        '<main id="content" tabindex="-1">\n'
        f"{body}\n"
        '<template id="sdd-provenance">'
        + json.dumps(provenance, ensure_ascii=False)
        + "</template>\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def _write_pair(root: Path, markdown: str, html: str) -> Path:
    source = root / "docs/adr/0001-flow.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(markdown, encoding="utf-8")
    source.with_suffix(".html").write_text(html, encoding="utf-8")
    css = root / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* fixture stylesheet */\n", encoding="utf-8")
    return source


def _flow_markdown() -> str:
    return "# Flow\n\nPlan then verify.\n"


def _flow_unit(markdown: str) -> str:
    return next(
        unit.id for unit in scan_markdown(markdown).units if unit.kind == "paragraph"
    )


def test_validate_html_accepts_semantic_document_with_bound_diagram(
    tmp_path: Path,
) -> None:
    markdown = _flow_markdown()
    body = (
        '<article class="decision-article">'
        '<h1 id="flow">Flow</h1>'
        '<p id="body">Plan then verify.</p>'
        f"{_figure(DIAGRAM_SVG)}"
        "</article>"
    )
    supplementary = [_diagram()]
    unit_id = _flow_unit(markdown)
    supplementary[0]["units"] = [unit_id]
    for entry in supplementary[0]["diagram"]["nodes"]:
        entry["units"] = [unit_id]
    for entry in supplementary[0]["diagram"]["edges"]:
        entry["units"] = [unit_id]
    html = _semantic_shell(
        markdown, body, "docs/adr/0001-flow.md", supplementary
    )
    source = _write_pair(tmp_path, markdown, html)

    result = validate_html(tmp_path, source)

    assert result["decision"] == "allow", result
    assert result["violations"] == []


def test_validate_html_rejects_semantic_diagram_without_table(
    tmp_path: Path,
) -> None:
    markdown = _flow_markdown()
    figure = _figure(DIAGRAM_SVG, table="")
    body = (
        '<article class="decision-article">'
        '<h1 id="flow">Flow</h1>'
        '<p id="body">Plan then verify.</p>'
        f"{figure}</article>"
    )
    supplementary = [_diagram()]
    unit_id = _flow_unit(markdown)
    supplementary[0]["units"] = [unit_id]
    for entry in supplementary[0]["diagram"]["nodes"]:
        entry["units"] = [unit_id]
    for entry in supplementary[0]["diagram"]["edges"]:
        entry["units"] = [unit_id]
    html = _semantic_shell(
        markdown, body, "docs/adr/0001-flow.md", supplementary
    )
    source = _write_pair(tmp_path, markdown, html)

    result = validate_html(tmp_path, source)

    assert result["decision"] == "deny"
    assert "figure-table" in {
        item["code"] for item in result["violations"]  # type: ignore[index]
    }


def test_validate_html_applies_svg_safety_to_strict_documents(
    tmp_path: Path,
) -> None:
    source = tmp_path / "docs/sdd/specs/2026-01-01-example-design.md"
    companion = source.with_suffix(".html")
    source.parent.mkdir(parents=True)
    shutil.copyfile(
        FIXTURE_ROOT / "spec/2026-01-01-example-design.md", source
    )
    html = (FIXTURE_ROOT / "spec/2026-01-01-example-design.html").read_text(
        encoding="utf-8"
    )
    html = html.replace(
        "</main>",
        '<svg><foreignobject><div>x</div></foreignobject></svg></main>',
    )
    companion.write_text(html, encoding="utf-8")
    css = tmp_path / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* fixture stylesheet */\n", encoding="utf-8")

    result = validate_html(tmp_path, source)

    assert result["decision"] == "deny"
    assert "svg-foreign-object" in {
        item["code"] for item in result["violations"]  # type: ignore[index]
    }
