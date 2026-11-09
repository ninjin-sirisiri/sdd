"""Static SVG allowlist and diagram / graph evidence validation.

The policy in :mod:`sddlib.html_policy` remains the default HTML contract.
This module adds the authored-SVG subset used by figures:

* every SVG element, attribute, and reference is checked against a fixed
  allowlist; script, event attributes, ``foreignObject``, animation, style
  attributes, style elements, hyperlinks, and external URLs are rejected,
* SVG complexity is bounded per document.  An over-limit document fails and
  asks the author to simplify; it is never truncated,
* a ``semantic-v1`` supplementary ``diagram`` or ``graph`` must be carried by
  a visible ``figure`` with a caption, a visible text explanation, and a data
  table whose text contains the same labels and values.

The checks are static.  This module does not render, rasterise, lay out, or
generate a diagram, and it does not judge visual quality or contrast.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from sddlib.html_policy import (
    HTMLDocument,
    HTMLNode,
    _attr,
    _attrs,
    _class_names,
    _descendants,
    _under,
    _SCOPE_VALUES,
)


MAX_SVG_ELEMENTS = 5_000

SVG_ALLOWED_TAGS = frozenset(
    {
        "svg",
        "g",
        "title",
        "desc",
        "defs",
        "marker",
        "rect",
        "circle",
        "ellipse",
        "line",
        "path",
        "polyline",
        "polygon",
        "text",
        "tspan",
    }
)

_ANIMATION_TAGS = frozenset(
    {"animate", "animatetransform", "animatemotion", "set", "discard"}
)

_SVG_COMMON_ATTRS = frozenset(
    {
        "id",
        "class",
        "role",
        "aria-label",
        "aria-labelledby",
        "aria-describedby",
        "aria-hidden",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "opacity",
        "transform",
        "marker-start",
        "marker-mid",
        "marker-end",
    }
)

_SVG_TAG_ATTRS = {
    "svg": {"xmlns", "viewbox", "preserveaspectratio", "width", "height"},
    "g": set(),
    "title": set(),
    "desc": set(),
    "defs": set(),
    "marker": {
        "markerwidth",
        "markerheight",
        "refx",
        "refy",
        "orient",
        "markerunits",
        "viewbox",
    },
    "rect": {"x", "y", "width", "height", "rx", "ry"},
    "circle": {"cx", "cy", "r"},
    "ellipse": {"cx", "cy", "rx", "ry"},
    "line": {"x1", "y1", "x2", "y2"},
    "path": {"d"},
    "polyline": {"points"},
    "polygon": {"points"},
    "text": {"x", "y", "dx", "dy", "text-anchor", "dominant-baseline"},
    "tspan": {"x", "y", "dx", "dy", "text-anchor", "dominant-baseline"},
}

_SVG_MARKER_ATTRS = frozenset({"marker-start", "marker-mid", "marker-end"})
_SVG_LINK_ATTRS = frozenset({"href", "xlink:href", "src", "srcset", "poster", "data"})
_SVG_ARIA_REF_ATTRS = frozenset({"aria-labelledby", "aria-describedby"})
_SVG_MARKER_URL_RE = re.compile(r"\s*url\(\s*#([A-Za-z_][\w:.-]*)\s*\)\s*")
_SCHEME_RE = re.compile(r"(?i)(?:https?|ftp|file|javascript|vbscript|data):")

_FIGURE_CLASS = "sdd-figure"
_FIGURE_SVG_CLASS = "sdd-figure-svg"
_FIGURE_EXPLANATION_CLASS = "sdd-figure-explanation"
_DATA_TABLE_CLASS = "sdd-data-table"


@dataclass(frozen=True)
class SvgIssue:
    """One static SVG or figure-evidence defect."""

    code: str
    message: str


def inspect_svg(document: HTMLDocument) -> tuple[SvgIssue, ...]:
    """Check every SVG element in ``document`` against the static allowlist."""

    svg_nodes = [node for node in document.nodes if _inside_svg(node)]
    if not svg_nodes:
        return ()
    issues: list[SvgIssue] = []
    id_map = _id_map(document)
    marker_refs: list[tuple[str, str]] = []
    aria_refs: list[str] = []

    for node in svg_nodes:
        if node.tag not in SVG_ALLOWED_TAGS:
            code = "svg-element"
            if node.tag == "script":
                code = "svg-script"
            elif node.tag == "style":
                code = "svg-style"
            elif node.tag == "foreignobject":
                code = "svg-foreign-object"
            elif node.tag in _ANIMATION_TAGS:
                code = "svg-animation"
            issues.append(
                SvgIssue(
                    code,
                    f"SVG element <{node.tag}> is outside the static allowlist.",
                )
            )
            continue

        allowed = _SVG_COMMON_ATTRS | _SVG_TAG_ATTRS.get(node.tag, set())
        for name, value in node.attrs:
            if name.startswith("on"):
                issues.append(
                    SvgIssue(
                        "svg-event-attribute",
                        f"SVG event attribute {name} is not allowed.",
                    )
                )
                continue
            if name == "style":
                issues.append(
                    SvgIssue(
                        "svg-style",
                        "Inline SVG style attributes are not allowed; use the shared classes.",
                    )
                )
                continue
            if name in _SVG_LINK_ATTRS:
                issues.append(
                    SvgIssue(
                        "svg-external-reference",
                        f"SVG attribute {name} is an external reference and is not allowed.",
                    )
                )
                continue
            if name not in allowed:
                issues.append(
                    SvgIssue(
                        "svg-attribute",
                        f"Attribute {name} on <{node.tag}> is outside the static allowlist.",
                    )
                )
                continue
            if name in _SVG_ARIA_REF_ATTRS and value:
                aria_refs.extend(value.split())
            if value is None or not value.strip():
                continue
            if name in _SVG_MARKER_ATTRS:
                match = _SVG_MARKER_URL_RE.fullmatch(value)
                if match is None:
                    issues.append(
                        SvgIssue(
                            "svg-external-reference",
                            f"{name} must reference one local marker as url(#id); "
                            f"found {value!r}.",
                        )
                    )
                else:
                    marker_refs.append((match.group(1), name))
                continue
            if _SCHEME_RE.search(value) or value.strip().startswith("//"):
                issues.append(
                    SvgIssue(
                        "svg-external-reference",
                        f"SVG attribute {name} contains an external URL.",
                    )
                )
                continue
            if "url(" in value.casefold():
                issues.append(
                    SvgIssue(
                        "svg-external-reference",
                        f"SVG attribute {name} uses a paint or reference URL; "
                        "only local marker references are allowed.",
                    )
                )

    for marker_id, name in marker_refs:
        targets = id_map.get(marker_id, [])
        if len(targets) != 1 or targets[0].tag != "marker":
            issues.append(
                SvgIssue(
                    "svg-reference",
                    f"{name} references {marker_id!r}, which is not one local "
                    "<marker> element.",
                )
            )
    for reference in aria_refs:
        if reference not in id_map:
            issues.append(
                SvgIssue(
                    "svg-reference",
                    f"SVG ARIA reference {reference!r} does not resolve.",
                )
            )

    if len(svg_nodes) > MAX_SVG_ELEMENTS:
        issues.append(
            SvgIssue(
                "svg-complexity",
                f"SVG markup uses {len(svg_nodes)} elements in this document; "
                f"the limit is {MAX_SVG_ELEMENTS}. Simplify the diagram instead "
                "of truncating it.",
            )
        )
    return tuple(issues)


def validate_diagram_representations(
    document: HTMLDocument,
    provenance: dict[str, object],
    main: HTMLNode,
) -> tuple[SvgIssue, ...]:
    """Check supplementary ``diagram`` and ``graph`` figure evidence.

    ``provenance`` must already have passed
    :func:`sddlib.html_units.validate_provenance`.
    """

    issues: list[SvgIssue] = []
    id_map = _id_map(document)
    figures_seen: set[str] = set()
    for item in provenance.get("supplementary", []):  # type: ignore[union-attr]
        if not isinstance(item, dict) or item.get("kind") not in {"diagram", "graph"}:
            continue
        identifier = str(item.get("id", ""))
        structure = item.get(str(item.get("kind")))
        if not isinstance(structure, dict):
            continue

        figures: list[HTMLNode] = []
        for target in item.get("targets", []):  # type: ignore[union-attr]
            nodes = id_map.get(str(target), [])
            if len(nodes) == 1 and nodes[0].tag == "figure":
                figures.append(nodes[0])
        if len(figures) != 1:
            issues.append(
                SvgIssue(
                    "figure-target",
                    f"Supplementary {identifier!r} needs exactly one figure "
                    f"target; found {len(figures)}.",
                )
            )
            continue
        figure = figures[0]
        figure_id = _attr(figure, "id") or ""
        if figure_id in figures_seen:
            issues.append(
                SvgIssue(
                    "figure-duplicate",
                    f"Figure {figure_id!r} carries more than one supplementary "
                    "representation.",
                )
            )
        figures_seen.add(figure_id)
        if not _under(figure, main):
            issues.append(
                SvgIssue(
                    "figure-visible",
                    f"Figure {figure_id!r} is not inside main.",
                )
            )
            continue
        if _hidden(figure):
            issues.append(
                SvgIssue(
                    "figure-visible",
                    f"Figure {figure_id!r} is hidden.",
                )
            )
            continue
        if _FIGURE_CLASS not in _class_names(figure):
            issues.append(
                SvgIssue(
                    "figure-class",
                    f"Figure {figure_id!r} must use the shared "
                    f"{_FIGURE_CLASS!r} class.",
                )
            )

        captions = [node for node in _descendants(figure) if node.tag == "figcaption"]
        if len(captions) != 1 or not _visible_text(captions[0]).strip():
            issues.append(
                SvgIssue(
                    "figure-caption",
                    f"Figure {figure_id!r} needs exactly one non-empty figcaption.",
                )
            )

        explanations = [
            node
            for node in _descendants(figure)
            if _FIGURE_EXPLANATION_CLASS in _class_names(node)
        ]
        if not explanations or not any(
            _visible_text(node).strip() for node in explanations
        ):
            issues.append(
                SvgIssue(
                    "figure-explanation",
                    f"Figure {figure_id!r} needs a non-empty "
                    f".{_FIGURE_EXPLANATION_CLASS} text equivalent.",
                )
            )

        tables = [node for node in _descendants(figure) if node.tag == "table"]
        table: HTMLNode | None = None
        if len(tables) != 1:
            issues.append(
                SvgIssue(
                    "figure-table",
                    f"Figure {figure_id!r} needs exactly one data table; "
                    f"found {len(tables)}.",
                )
            )
        else:
            table = tables[0]
            if _DATA_TABLE_CLASS not in _class_names(table):
                issues.append(
                    SvgIssue(
                        "figure-table-class",
                        f"The table in figure {figure_id!r} must use the shared "
                        f"{_DATA_TABLE_CLASS!r} class.",
                    )
                )
            table_captions = [
                node for node in _descendants(table) if node.tag == "caption"
            ]
            if not table_captions or not _visible_text(table_captions[0]).strip():
                issues.append(
                    SvgIssue(
                        "figure-table-caption",
                        f"The data table in figure {figure_id!r} needs a "
                        "non-empty caption.",
                    )
                )
            headers = [node for node in _descendants(table) if node.tag == "th"]
            if not headers or any(
                (_attr(node, "scope") or "").casefold() not in _SCOPE_VALUES
                for node in headers
            ):
                issues.append(
                    SvgIssue(
                        "figure-table-header",
                        f"The data table in figure {figure_id!r} needs scoped "
                        "header cells.",
                    )
                )
            if _hidden(table):
                issues.append(
                    SvgIssue(
                        "figure-table",
                        f"The data table in figure {figure_id!r} is hidden.",
                    )
                )

        svgs = [node for node in _descendants(figure) if node.tag == "svg"]
        if len(svgs) != 1:
            issues.append(
                SvgIssue(
                    "figure-svg",
                    f"Figure {figure_id!r} needs exactly one SVG; found "
                    f"{len(svgs)}.",
                )
            )
            continue
        svg = svgs[0]
        if _hidden(svg):
            issues.append(
                SvgIssue(
                    "figure-svg",
                    f"The SVG in figure {figure_id!r} is hidden.",
                )
            )
        if _FIGURE_SVG_CLASS not in _class_names(svg):
            issues.append(
                SvgIssue(
                    "figure-svg-class",
                    f"The SVG in figure {figure_id!r} must use the shared "
                    f"{_FIGURE_SVG_CLASS!r} class.",
                )
            )
        if (_attr(svg, "role") or "").casefold() != "img":
            issues.append(
                SvgIssue(
                    "figure-svg-role",
                    f"The SVG in figure {figure_id!r} must use role=\"img\".",
                )
            )
        _accessible_name_issues(svg, figure, id_map, issues)

        svg_ids = {
            value: node
            for node in [svg, *_descendants(svg)]
            for value in _attrs(node, "id")
            if value
        }
        svg_text = _svg_visible_text(svg)
        table_text = _visible_text(table) if table is not None else ""

        if item.get("kind") == "diagram":
            _diagram_issues(
                identifier,
                structure,
                svg,
                svg_ids,
                svg_text,
                table_text,
                table is not None,
                issues,
            )
        else:
            _graph_issues(
                identifier,
                structure,
                svg,
                svg_ids,
                svg_text,
                table_text,
                table is not None,
                issues,
            )
    return tuple(issues)


def _diagram_issues(
    identifier: str,
    structure: dict[str, object],
    svg: HTMLNode,
    svg_ids: dict[str, HTMLNode],
    svg_text: str,
    table_text: str,
    has_table: bool,
    issues: list[SvgIssue],
) -> None:
    for role in ("node", "edge"):
        entries = structure.get(f"{role}s", [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            element_id = str(entry.get("id", ""))
            label = str(entry.get("label", ""))
            target = svg_ids.get(element_id)
            if target is None or not _visible_svg_element(target, svg):
                issues.append(
                    SvgIssue(
                        f"diagram-{role}-target",
                        f"Diagram {identifier!r} {role} {element_id!r} does not "
                        "resolve to one visible SVG element.",
                    )
                )
            if not _contains(label, svg_text):
                issues.append(
                    SvgIssue(
                        f"diagram-{role}-label",
                        f"Diagram {identifier!r} {role} label {label!r} is not "
                        "visible in the SVG text.",
                    )
                )
            if has_table and not _contains(label, table_text):
                issues.append(
                    SvgIssue(
                        f"diagram-{role}-table",
                        f"Diagram {identifier!r} {role} label {label!r} is not "
                        "repeated in the data table.",
                    )
                )


def _graph_issues(
    identifier: str,
    structure: dict[str, object],
    svg: HTMLNode,
    svg_ids: dict[str, HTMLNode],
    svg_text: str,
    table_text: str,
    has_table: bool,
    issues: list[SvgIssue],
) -> None:
    series_entries = structure.get("series", [])
    if isinstance(series_entries, list):
        for entry in series_entries:
            if not isinstance(entry, dict):
                continue
            element_id = str(entry.get("id", ""))
            label = str(entry.get("label", ""))
            target = svg_ids.get(element_id)
            if target is None or not _visible_svg_element(target, svg):
                issues.append(
                    SvgIssue(
                        "graph-series-target",
                        f"Graph {identifier!r} series {element_id!r} does not "
                        "resolve to one visible SVG element.",
                    )
                )
            if not _contains(label, svg_text):
                issues.append(
                    SvgIssue(
                        "graph-series-label",
                        f"Graph {identifier!r} series label {label!r} is not "
                        "visible in the SVG text; colour alone cannot encode it.",
                    )
                )
            if has_table and not _contains(label, table_text):
                issues.append(
                    SvgIssue(
                        "graph-series-table",
                        f"Graph {identifier!r} series label {label!r} is not "
                        "repeated in the data table.",
                    )
                )
            unit = entry.get("unit")
            if unit is not None and has_table and not _contains(
                str(unit), table_text
            ):
                issues.append(
                    SvgIssue(
                        "graph-series-unit",
                        f"Graph {identifier!r} series unit {unit!r} is not "
                        "visible in the data table.",
                    )
                )
            values = entry.get("values", [])
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict):
                    continue
                value_id = str(value.get("id", ""))
                if not has_table:
                    break
                missing = [
                    name
                    for name in ("x", "y")
                    if not _number_contains(value.get(name), table_text)
                ]
                if missing:
                    issues.append(
                        SvgIssue(
                            "graph-value-table",
                            f"Graph {identifier!r} value {value_id!r} is not "
                            "represented in the data table ("
                            + ", ".join(missing)
                            + ").",
                        )
                    )

    axes = structure.get("axes", [])
    if isinstance(axes, list):
        for entry in axes:
            if not isinstance(entry, dict):
                continue
            element_id = str(entry.get("id", ""))
            label = str(entry.get("label", ""))
            target = svg_ids.get(element_id)
            if target is None or not _visible_svg_element(target, svg):
                issues.append(
                    SvgIssue(
                        "graph-axis-target",
                        f"Graph {identifier!r} axis {element_id!r} does not "
                        "resolve to one visible SVG element.",
                    )
                )
            if not _contains(label, svg_text):
                issues.append(
                    SvgIssue(
                        "graph-axis-label",
                        f"Graph {identifier!r} axis label {label!r} is not "
                        "visible in the SVG text.",
                    )
                )
            if has_table and not _contains(label, table_text):
                issues.append(
                    SvgIssue(
                        "graph-axis-table",
                        f"Graph {identifier!r} axis label {label!r} is not "
                        "repeated in the data table.",
                    )
                )
            unit = entry.get("unit")
            if unit is not None and has_table and not _contains(
                str(unit), table_text
            ):
                issues.append(
                    SvgIssue(
                        "graph-axis-unit",
                        f"Graph {identifier!r} axis unit {unit!r} is not "
                        "visible in the data table.",
                    )
                )


def _accessible_name_issues(
    svg: HTMLNode,
    figure: HTMLNode,
    id_map: dict[str, list[HTMLNode]],
    issues: list[SvgIssue],
) -> None:
    label = (_attr(svg, "aria-label") or "").strip()
    references = (_attr(svg, "aria-labelledby") or "").split()
    if label:
        return
    if not references:
        issues.append(
            SvgIssue(
                "figure-svg-name",
                "The figure SVG needs an accessible name through aria-label "
                "or aria-labelledby.",
            )
        )
        return
    resolved: list[HTMLNode] = []
    for reference in references:
        nodes = id_map.get(reference, [])
        if len(nodes) != 1:
            issues.append(
                SvgIssue(
                    "figure-svg-name",
                    f"The figure SVG accessible-name reference {reference!r} "
                    "does not resolve to one element.",
                )
            )
            return
        resolved.append(nodes[0])
    if not any(node is figure or _under(node, figure) for node in resolved):
        issues.append(
            SvgIssue(
                "figure-svg-name",
                "The figure SVG accessible name must resolve inside its figure.",
            )
        )


def _id_map(document: HTMLDocument) -> dict[str, list[HTMLNode]]:
    mapping: dict[str, list[HTMLNode]] = {}
    for node in document.nodes:
        for value in _attrs(node, "id"):
            if value:
                mapping.setdefault(value, []).append(node)
    return mapping


def _inside_svg(node: HTMLNode) -> bool:
    current: HTMLNode | None = node
    while current is not None:
        if current.tag == "svg":
            return True
        current = current.parent
    return False


def _hidden(node: HTMLNode) -> bool:
    current: HTMLNode | None = node
    while current is not None:
        if current.tag in {"head", "template"}:
            return True
        if any(name == "hidden" for name, _value in current.attrs):
            return True
        if any(
            name == "aria-hidden" and (value or "").strip().casefold() == "true"
            for name, value in current.attrs
        ):
            return True
        current = current.parent
    return False


def _visible_svg_element(node: HTMLNode, svg: HTMLNode) -> bool:
    current: HTMLNode | None = node
    while current is not None and current is not svg:
        if current.tag in {"defs", "marker", "title", "desc", "script", "style"}:
            return False
        if any(name == "hidden" for name, _value in current.attrs):
            return False
        if any(
            name == "aria-hidden" and (value or "").strip().casefold() == "true"
            for name, value in current.attrs
        ):
            return False
        current = current.parent
    return True


def _visible_text(node: HTMLNode) -> str:
    parts: list[str] = []

    def visit(current: HTMLNode) -> None:
        if _hidden(current):
            return
        if current.tag in {"title", "desc", "script", "style", "template"}:
            return
        if current.tag in {
            "caption",
            "dd",
            "div",
            "dt",
            "figcaption",
            "li",
            "p",
            "table",
            "tbody",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr",
        }:
            parts.append(" ")
        for item in current.content:
            if isinstance(item, str):
                parts.append(item)
            else:
                visit(item)
        if current.tag in {
            "caption",
            "dd",
            "div",
            "dt",
            "figcaption",
            "li",
            "p",
            "table",
            "tbody",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr",
        }:
            parts.append(" ")

    visit(node)
    return "".join(parts)


def _svg_visible_text(node: HTMLNode) -> str:
    parts: list[str] = []

    def visit(current: HTMLNode) -> None:
        if current.tag in {"title", "desc", "defs", "marker", "script", "style"}:
            return
        if any(name == "hidden" for name, _value in current.attrs):
            return
        if any(
            name == "aria-hidden" and (value or "").strip().casefold() == "true"
            for name, value in current.attrs
        ):
            return
        for item in current.content:
            if isinstance(item, str):
                parts.append(item)
            else:
                visit(item)

    visit(node)
    return "".join(parts)


def _contains(needle: str, haystack: str) -> bool:
    normalized = " ".join(needle.split()).casefold()
    return bool(normalized) and normalized in " ".join(haystack.split()).casefold()


def _number_variants(value: object) -> list[str]:
    if type(value) is int:
        return [str(value)]
    if type(value) is float:
        variants = {str(value), f"{value:g}"}
        if value.is_integer():
            variants.add(str(int(value)))
        return sorted(variants)
    return []


def _number_contains(value: object, text: str) -> bool:
    for variant in _number_variants(value):
        if re.search(
            r"(?<![\d.])" + re.escape(variant) + r"(?![\d.])", text
        ):
            return True
    return False
