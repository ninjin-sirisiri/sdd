"""Static ``semantic-v1`` coverage and exact-preservation validation.

The strict HTML contract in :mod:`sddlib.html_policy` remains the default and
unchanged.  A companion that declares ``sdd-html-contract: semantic-v1`` is
validated against a fresh scan from :mod:`sddlib.html_units` instead of the
strict source-text order check.

This module checks what static inspection can check:

* the provenance unit set equals the fresh source scan by ID, kind, range,
  digest, and parent (never by array position),
* every source unit maps to at least one visible representation target,
* target IDs resolve to exactly one visible element in ``main`` and are not
  hidden behind ``hidden``, ``aria-hidden``, ``template``, ``head``, ``aside``,
  or ``nav``,
* code, paths, identifiers, link destinations, glossary canonical names,
  Avoid entries, numbers, units, comparison operators, and thresholds survive,
* calculations use only ``sum``, ``count``, ``ratio``, and ``scale`` and
  recompute from their explicit inputs without evaluating the formula text.

A passing result is explicitly labelled ``static-only``.  It is not proof of
semantic preservation: paraphrase quality, information sufficiency, and the
meaning of a mapped region still require human or model assessment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
import re

from sddlib.html_policy import (
    HTMLDocument,
    HTMLNode,
    _ancestor,
    _attr,
    _attrs,
    _class_names,
    _descendants,
    _markdown_visible_text,
    _source_task_headings,
    _under,
)
from sddlib.html_units import (
    SEMANTIC_CONTRACT,
    STRICT_CONTRACT,
    SourceScan,
    SourceScanError,
    SourceUnit,
    UnitSchemaError,
    scan_markdown,
    strict_requirements,
    validate_provenance,
)


CONTRACT_META_NAME = "sdd-html-contract"
PROVENANCE_TEMPLATE_ID = "sdd-provenance"
STATIC_ASSURANCE = "static-only"
SEMANTIC_LIMITATION = (
    "Static checks verify unit coverage, target references, and exact-value "
    "presence only; they do not prove that paraphrased or reordered content "
    "preserves the source meaning."
)

_BLOCK_TAGS = {
    "article",
    "blockquote",
    "caption",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "main",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
_HIDDEN_CONTAINER_TAGS = {"head", "template", "aside", "nav"}
_CODE_TAGS = {"code", "pre", "kbd", "samp"}
_MEDIA_TAGS = {"img", "svg", "video", "audio", "canvas"}
_TARGET_CONTAINER_TAGS = {"html", "body", "main"}

_TEMPLATE_START_RE = re.compile(r"<template\b[^>]*>", re.IGNORECASE)
_TEMPLATE_END_RE = re.compile(r"</template\s*>", re.IGNORECASE)
_TAG_ID_RE = re.compile(
    r"""\bid\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE
)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_VERSION_RE = re.compile(r"\b[A-Za-z]?\d+(?:\.\d+){2,}\b")
_NUMBER_RE = re.compile(r"(?<![\w.,/#:+-])(\d+(?:\.\d+)?)(?![\w.])")
_UNIT_RE = re.compile(
    r"[ \t]*(%|‰|[A-Za-zµμ°]+|[\u3040-\u30ff\u4e00-\u9fff]{1,2})"
)
_OPERATOR_BEFORE_RE = re.compile(r"(<=|>=|≤|≥|≠|!=|≈|=|<|>)\s*$")
_OPERATOR_AFTER_RE = re.compile(r"^\s*(<=|>=|≤|≥|≠|!=|≈|=|<|>)")
_PATH_RE = re.compile(
    r"(?<![\w/.-])(?:\.\.?/)?(?:[\w.-]+/)+[\w.-]*"
    r"|(?<![\w/.-])[\w.-]+\.(?:md|html?|css|json|py|toml|ya?ml|sh|tsx?|jsx?"
    r"|svg|png|jpe?g|gif|txt|lock)\b"
)
_IDENTIFIER_RE = re.compile(
    r"(?<![\w-])(?:"
    r"--[A-Za-z][A-Za-z0-9-]*"
    r"|[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*"
    r"|[a-z][a-z0-9]*(?:_[a-z0-9]+)+"
    r"|[a-z]+[A-Z][A-Za-z0-9]*"
    r"|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+"
    r"|[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d[a-z0-9]*"
    r")(?![\w-])"
)
_FORMULA_FORBIDDEN_RE = re.compile(
    r"__|eval|exec|import|lambda|;|[{}\[\]\"'`#]", re.IGNORECASE
)
_KNOWN_LONG_UNITS = {
    "byte",
    "bytes",
    "character",
    "characters",
    "column",
    "columns",
    "day",
    "days",
    "document",
    "documents",
    "element",
    "elements",
    "file",
    "files",
    "hour",
    "hours",
    "item",
    "items",
    "line",
    "lines",
    "microsecond",
    "microseconds",
    "millisecond",
    "milliseconds",
    "minute",
    "minutes",
    "nanosecond",
    "nanoseconds",
    "page",
    "pages",
    "percent",
    "point",
    "points",
    "request",
    "requests",
    "row",
    "rows",
    "run",
    "runs",
    "second",
    "seconds",
    "token",
    "tokens",
}


@dataclass(frozen=True)
class SemanticIssue:
    """One static semantic defect, independent of any host path context."""

    code: str
    message: str
    unit: str | None = None


@dataclass(frozen=True)
class ContractDetection:
    """The contract declared by the companion head."""

    contract: str
    issues: tuple[SemanticIssue, ...] = ()


@dataclass(frozen=True)
class SemanticResult:
    """The outcome of static ``semantic-v1`` inspection.

    ``assurance`` is always ``static-only``.  Callers must not present an
    empty ``issues`` tuple as proof of semantic preservation.
    """

    contract: str
    issues: tuple[SemanticIssue, ...]
    units_checked: int = 0
    mappings_checked: int = 0
    strict_targets_checked: int = 0
    supplementary_checked: int = 0
    calculations_checked: int = 0
    assurance: str = STATIC_ASSURANCE
    limitations: tuple[str, ...] = (SEMANTIC_LIMITATION,)

    @property
    def ok(self) -> bool:
        return not self.issues

    def evidence(self) -> dict[str, object]:
        return {
            "assurance": self.assurance,
            "limitations": list(self.limitations),
            "counts": {
                "units": self.units_checked,
                "mappings": self.mappings_checked,
                "strict_targets": self.strict_targets_checked,
                "supplementary": self.supplementary_checked,
                "calculations": self.calculations_checked,
            },
        }


def detect_contract(document: HTMLDocument) -> ContractDetection:
    """Read ``sdd-html-contract`` without falling back from an unknown value.

    No declaration means the unchanged strict contract.  A declaration other
    than ``strict`` or ``semantic-v1`` is rejected; it never switches to strict
    inspection silently.
    """

    declarations: list[HTMLNode] = []
    for node in document.nodes:
        if node.tag != "meta":
            continue
        if _ancestor(node, {"template"}) is not None:
            continue
        if any(
            value is not None and value.strip().casefold() == CONTRACT_META_NAME
            for name, value in node.attrs
            if name == "name"
        ):
            declarations.append(node)
    if not declarations:
        return ContractDetection(STRICT_CONTRACT)
    if len(declarations) > 1:
        return ContractDetection(
            "unknown",
            (
                SemanticIssue(
                    "contract-duplicate",
                    "The companion declares sdd-html-contract more than once; "
                    "the contract is ambiguous and was not validated.",
                ),
            ),
        )
    content = (_attr(declarations[0], "content") or "").strip()
    if content == SEMANTIC_CONTRACT:
        return ContractDetection(SEMANTIC_CONTRACT)
    if content == STRICT_CONTRACT:
        return ContractDetection(STRICT_CONTRACT)
    return ContractDetection(
        "unknown",
        (
            SemanticIssue(
                "contract-unknown",
                f"Unknown sdd-html-contract value {content!r}; refusing to fall "
                "back to strict validation.",
            ),
        ),
    )


def validate_semantic_companion(
    document: HTMLDocument,
    html_bytes: bytes,
    source_bytes: bytes,
    *,
    source_path: str,
    document_kind: str | None = None,
) -> SemanticResult:
    """Validate one semantic-v1 companion against the exact source bytes."""

    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (SemanticIssue("source-encoding", f"Markdown source is not UTF-8: {exc}"),),
        )
    try:
        scan = scan_markdown(source_bytes)
    except SourceScanError as exc:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (SemanticIssue("source-encoding", str(exc)),),
        )
    if not scan.complete:
        kinds = sorted(item.kind for item in scan.unsupported)
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "source-incomplete",
                    "Source scan is incomplete ("
                    + ", ".join(kinds)
                    + "); information extraction is unavailable, so coverage "
                    "cannot pass.",
                ),
            ),
        )

    main = next((node for node in document.nodes if node.tag == "main"), None)
    if main is None:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (SemanticIssue("main-missing", "A main element is required."),),
        )

    try:
        html_text = html_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (SemanticIssue("html-encoding", f"HTML is not UTF-8: {exc}"),),
        )

    payloads, template_issue = _provenance_payloads(html_text)
    if template_issue is not None:
        return SemanticResult(SEMANTIC_CONTRACT, (template_issue,))
    templates = [
        node
        for node in document.nodes
        if node.tag == "template" and _attr(node, "id") == PROVENANCE_TEMPLATE_ID
    ]
    if not templates:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "provenance-missing",
                    "semantic-v1 requires one template#sdd-provenance JSON map.",
                ),
            ),
        )
    if len(templates) > 1 or len(payloads) > 1:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "provenance-duplicate",
                    "Exactly one template#sdd-provenance map is required.",
                ),
            ),
        )
    if not payloads:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "provenance-missing",
                    "semantic-v1 requires one template#sdd-provenance JSON map.",
                ),
            ),
        )
    try:
        payload = json.loads(payloads[0])
    except (TypeError, json.JSONDecodeError) as exc:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "provenance-json",
                    f"template#sdd-provenance is not valid JSON: {exc}",
                ),
            ),
        )
    try:
        provenance = validate_provenance(payload)
    except UnitSchemaError as exc:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (SemanticIssue("provenance-schema", str(exc)),),
        )

    issues: list[SemanticIssue] = []
    declared_source = provenance["source"]  # type: ignore[assignment]
    declared_digest = declared_source["digest"]  # type: ignore[index]
    if declared_digest != scan.digest:
        return SemanticResult(
            SEMANTIC_CONTRACT,
            (
                SemanticIssue(
                    "source-stale",
                    "The provenance source digest does not match the exact "
                    f"Markdown bytes (expected {scan.digest}).",
                ),
            ),
        )
    if declared_source["path"] != source_path:  # type: ignore[index]
        issues.append(
            SemanticIssue(
                "source-path",
                "The provenance source path does not match the Target "
                f"Markdown path {source_path!r}.",
            )
        )

    fresh_by_id = {unit.id: unit for unit in scan.units}
    declared_units = provenance["units"]  # type: ignore[assignment]
    declared_by_id = {unit["id"]: unit for unit in declared_units}  # type: ignore[index]
    for unit_id in sorted(set(fresh_by_id) | set(declared_by_id)):
        fresh = fresh_by_id.get(unit_id)
        declared = declared_by_id.get(unit_id)
        if declared is None:
            issues.append(
                SemanticIssue(
                    "unit-missing",
                    f"Source unit {unit_id!r} is absent from the provenance units.",
                    unit_id,
                )
            )
        elif fresh is None:
            issues.append(
                SemanticIssue(
                    "unit-unknown",
                    f"Provenance unit {unit_id!r} does not exist in the fresh scan.",
                    unit_id,
                )
            )
        else:
            mismatches = _unit_mismatches(fresh, declared)
            if mismatches:
                issues.append(
                    SemanticIssue(
                        "unit-mismatch",
                        f"Provenance unit {unit_id!r} differs from the fresh "
                        "scan in " + ", ".join(mismatches) + ".",
                        unit_id,
                    )
                )

    target_map: dict[str, list[HTMLNode]] = {}
    visible_main_ids: set[str] = set()
    for node in document.nodes:
        for value in _attrs(node, "id"):
            if not value:
                continue
            target_map.setdefault(value, []).append(node)
            if _under(node, main) and _visible_reason(node, main) is None:
                visible_main_ids.add(value)
    for value in _attrs(main, "id"):
        if value and value not in target_map:
            target_map[value] = [main]

    mappings = provenance["mappings"]  # type: ignore[assignment]
    mappings_by_unit = {mapping["unit"]: mapping for mapping in mappings}  # type: ignore[index]
    mappings_checked = 0
    for unit in scan.units:
        mapping = mappings_by_unit.get(unit.id)
        if mapping is None:
            issues.append(
                SemanticIssue(
                    "mapping-missing",
                    f"Source unit {unit.id!r} has no visible representation mapping.",
                    unit.id,
                )
            )
            continue
        mappings_checked += 1
        seen_targets: set[str] = set()
        for target_id in mapping["targets"]:  # type: ignore[index]
            if target_id in seen_targets:
                issues.append(
                    SemanticIssue(
                        "target-duplicate-reference",
                        f"Mapping for {unit.id!r} lists target {target_id!r} "
                        "more than once.",
                        unit.id,
                    )
                )
                continue
            seen_targets.add(target_id)
            _resolve_target(target_id, target_map, main, issues, unit=unit.id)

    for unit in scan.units:
        if unit.kind != "heading":
            continue
        slug = str(unit.fields.get("slug", ""))
        if slug and slug not in visible_main_ids:
            issues.append(
                SemanticIssue(
                    "fragment-missing",
                    f"Source heading fragment {slug!r} is not preserved on a "
                    "visible element in main.",
                    unit.id,
                )
            )

    issues.extend(_link_destination_issues(scan, target_map, main))
    issues.extend(_exact_token_issues(source_text, main))
    calculations_checked, calculation_issues, verified_results = _calculation_issues(
        provenance, {unit.id: unit for unit in scan.units}, main
    )
    issues.extend(_number_issues(source_text, main, verified_results))
    issues.extend(_strict_issues(scan, provenance, target_map, main))
    issues.extend(_supplementary_issues(provenance, target_map, main))
    issues.extend(calculation_issues)
    if document_kind == "plan":
        issues.extend(_plan_order_issues(source_text, document, main))

    return SemanticResult(
        SEMANTIC_CONTRACT,
        tuple(issues),
        units_checked=len(scan.units),
        mappings_checked=mappings_checked,
        supplementary_checked=len(provenance["supplementary"]),  # type: ignore[arg-type]
        calculations_checked=calculations_checked,
        strict_targets_checked=len(provenance["strict"]),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Provenance extraction and target resolution


def _provenance_payloads(html: str) -> tuple[list[str], SemanticIssue | None]:
    payloads: list[str] = []
    for match in _TEMPLATE_START_RE.finditer(html):
        identifier = _TAG_ID_RE.search(match.group(0))
        value = None
        if identifier is not None:
            value = next(
                (group for group in identifier.groups() if group is not None), None
            )
        if value != PROVENANCE_TEMPLATE_ID:
            continue
        closing = _TEMPLATE_END_RE.search(html, match.end())
        if closing is None:
            return [], SemanticIssue(
                "provenance-malformed",
                "template#sdd-provenance is not closed.",
            )
        payloads.append(html[match.end() : closing.start()])
    return payloads, None


def _unit_mismatches(fresh: SourceUnit, declared: dict[str, object]) -> list[str]:
    mismatches: list[str] = []
    if declared.get("kind") != fresh.kind:
        mismatches.append("kind")
    if declared.get("source_digest") != fresh.digest:
        mismatches.append("source_digest")
    range_value = declared.get("range")
    if not isinstance(range_value, dict) or (
        range_value.get("start") != fresh.start
        or range_value.get("end") != fresh.end
    ):
        mismatches.append("range")
    if declared.get("parent") != fresh.parent:
        mismatches.append("parent")
    return mismatches


def _is_hidden_container(node: HTMLNode) -> bool:
    if node.tag in _HIDDEN_CONTAINER_TAGS:
        return True
    if any(name == "hidden" for name, _value in node.attrs):
        return True
    return any(
        name == "aria-hidden" and (value or "").strip().casefold() == "true"
        for name, value in node.attrs
    )


def _visible_reason(node: HTMLNode, main: HTMLNode) -> str | None:
    """Return why ``node`` cannot count as a visible representation target."""

    if node.tag in _TARGET_CONTAINER_TAGS:
        return "the element is a document container, not a representation"
    if node is not main and not _under(node, main):
        return "the element is outside main"
    current: HTMLNode | None = node
    while current is not None:
        if _is_hidden_container(current):
            if current.tag in _HIDDEN_CONTAINER_TAGS:
                return f"the element is inside <{current.tag}>"
            if any(name == "hidden" for name, _value in current.attrs):
                return "the element is hidden"
            return "the element is aria-hidden"
        current = current.parent
    return None


def _media_below(node: HTMLNode) -> bool:
    return any(child.tag in _MEDIA_TAGS for child in _descendants(node))


def _has_visible_content(node: HTMLNode) -> bool:
    return (
        bool(_visible_text(node).strip())
        or node.tag in _MEDIA_TAGS
        or _media_below(node)
    )


def _resolve_target(
    target_id: str,
    target_map: dict[str, list[HTMLNode]],
    main: HTMLNode,
    issues: list[SemanticIssue],
    *,
    unit: str | None = None,
) -> HTMLNode | None:
    nodes = target_map.get(target_id)
    if not nodes:
        issues.append(
            SemanticIssue(
                "target-missing",
                f"Representation target {target_id!r} does not resolve to an "
                "element id in the HTML.",
                unit,
            )
        )
        return None
    if len(nodes) > 1:
        issues.append(
            SemanticIssue(
                "target-duplicate",
                f"Representation target {target_id!r} resolves to "
                f"{len(nodes)} elements; ids must be unique.",
                unit,
            )
        )
        return None
    node = nodes[0]
    reason = _visible_reason(node, main)
    if reason is not None:
        issues.append(
            SemanticIssue(
                "target-hidden",
                f"Representation target {target_id!r} is not visible: {reason}.",
                unit,
            )
        )
        return None
    if not _has_visible_content(node):
        issues.append(
            SemanticIssue(
                "target-empty",
                f"Representation target {target_id!r} has no visible content.",
                unit,
            )
        )
        return None
    return node


def _visible_text(node: HTMLNode, *, include_code: bool = True) -> str:
    parts: list[str] = []

    def visit(current: HTMLNode) -> None:
        if _is_hidden_container(current):
            return
        if not include_code and current.tag in _CODE_TAGS:
            parts.append(" ")
            return
        if "skip-link" in _class_names(current) or "task-number" in _class_names(
            current
        ):
            return
        if current.tag in _BLOCK_TAGS and parts:
            parts.append(" ")
        for item in current.content:
            if isinstance(item, str):
                parts.append(item)
            else:
                visit(item)
        if current.tag in _BLOCK_TAGS:
            parts.append(" ")

    visit(node)
    return "".join(parts)


def _prose(node: HTMLNode) -> str:
    return " ".join(_visible_text(node).split())


# ---------------------------------------------------------------------------
# Exact-token checks


def _link_destination_issues(
    scan: SourceScan,
    target_map: dict[str, list[HTMLNode]],
    main: HTMLNode,
) -> list[SemanticIssue]:
    source: Counter[str] = Counter(
        str(unit.fields.get("destination", ""))
        for unit in scan.units
        if unit.kind in {"link", "image"}
    )
    for destination in [value for value in source if not value]:
        del source[destination]
    visible: Counter[str] = Counter()
    for node in _descendants(main):
        if _visible_reason(node, main) is not None:
            continue
        if node.tag == "a":
            value = _attr(node, "href")
        elif node.tag == "img":
            value = _attr(node, "src")
        else:
            continue
        if value:
            visible[value] += 1
    issues: list[SemanticIssue] = []
    for destination, expected in source.items():
        if visible[destination] < expected:
            issues.append(
                SemanticIssue(
                    "link-missing",
                    f"Link destination {destination!r} must remain visible "
                    f"{expected} time(s); found {visible[destination]}.",
                )
            )
    return issues


def _exact_token_issues(
    source_text: str,
    main: HTMLNode,
) -> list[SemanticIssue]:
    prose = _prose(main)
    source_prose = _markdown_visible_text(
        source_text,
        include_fenced_code=False,
        include_inline_code=True,
    )
    issues: list[SemanticIssue] = []
    for value in _paths(source_prose):
        if value not in prose:
            issues.append(
                SemanticIssue(
                    "path-missing",
                    f"Path {value!r} from the Markdown source is not visible "
                    "in main.",
                )
            )
    for value in _identifiers(source_prose):
        if value not in prose:
            issues.append(
                SemanticIssue(
                    "identifier-missing",
                    f"Identifier {value!r} from the Markdown source is not "
                    "visible in main.",
                )
            )
    return issues


def _paths(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in _PATH_RE.finditer(text):
        value = match.group(0)
        if len(value) < 3 or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _identifiers(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in _IDENTIFIER_RE.finditer(text):
        value = match.group(0)
        if value in seen:
            continue
        if "." in value:
            first = value.split(".", 1)[0]
            if len(first) < 3:
                continue
        if "_" in value and not re.search(r"[A-Za-z]", value):
            continue
        if "-" in value and not re.search(r"\d", value):
            continue
        seen.add(value)
        values.append(value)
    return values


def _strict_issues(
    scan: SourceScan,
    provenance: dict[str, object],
    target_map: dict[str, list[HTMLNode]],
    main: HTMLNode,
) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    units = {unit.id: unit for unit in scan.units}
    required = {
        (str(item["unit"]), str(item["category"]), str(item["value"]))
        for item in strict_requirements(scan)
    }
    declared = provenance["strict"]  # type: ignore[assignment]
    declared_keys = {
        (str(item["unit"]), str(item["category"]), str(item["value"]))
        for item in declared  # type: ignore[index]
    }
    for unit_id, category, value in sorted(required - declared_keys):
        issues.append(
            SemanticIssue(
                "strict-missing",
                f"Strict {category} value {value!r} for {unit_id!r} is absent "
                "from the provenance strict list.",
                unit_id,
            )
        )
    for item in declared:  # type: ignore[index]
        unit_id = item["unit"]
        category = item["category"]
        value = str(item["value"])
        key = (str(unit_id), str(category), str(value))
        if category in {"code", "link", "glossary_term", "avoid"} and key not in required:
            issues.append(
                SemanticIssue(
                    "strict-unknown",
                    f"Provenance declares an unsupported {category} target "
                    f"{value!r} for {unit_id!r}.",
                    unit_id,
                )
            )
        if category in {"path", "identifier"}:
            unit = units.get(unit_id)  # type: ignore[arg-type]
            if unit is None or value not in unit.text:
                issues.append(
                    SemanticIssue(
                        "strict-substitution",
                        f"Strict {category} value {value!r} does not occur in "
                        f"source unit {unit_id!r}.",
                        unit_id,
                    )
                )
        resolved: list[HTMLNode] = []
        for target_id in item["targets"]:
            node = _resolve_target(
                target_id, target_map, main, issues, unit=unit_id  # type: ignore[arg-type]
            )
            if node is not None:
                resolved.append(node)
        if not resolved:
            continue
        if not any(_strict_value_visible(category, value, node) for node in resolved):
            issues.append(
                SemanticIssue(
                    "strict-value-missing",
                    f"Strict {category} value {value!r} for {unit_id!r} is not "
                    "visible in its declared target(s).",
                    unit_id,
                )
            )
    return issues


def _strict_value_visible(category: str, value: str, node: HTMLNode) -> bool:
    if category == "link":
        for current in [node, *_descendants(node)]:
            if current.tag in {"a", "img"} and value in {
                _attr(current, "href"),
                _attr(current, "src"),
            }:
                return True
        return False
    if category == "code":
        actual = _visible_text(node).replace("\r\n", "\n").replace("\r", "\n")
        expected = value.replace("\r\n", "\n").replace("\r", "\n")
        return expected in actual
    prose = _prose(node)
    if category in {"glossary_term", "avoid"}:
        return (
            re.search(
                r"(?<![\w])" + re.escape(value) + r"(?![\w])", prose
            )
            is not None
        )
    return " ".join(value.split()) in prose


def _supplementary_issues(
    provenance: dict[str, object],
    target_map: dict[str, list[HTMLNode]],
    main: HTMLNode,
) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    for item in provenance["supplementary"]:  # type: ignore[index]
        for target_id in item["targets"]:
            _resolve_target(
                target_id,
                target_map,
                main,
                issues,
                unit=str(item["id"]),
            )
    return issues


# ---------------------------------------------------------------------------
# Numbers, units, comparison operators, and thresholds


def _normalize_measure(text: str) -> str:
    text = _DATE_RE.sub(" ", text)
    text = _VERSION_RE.sub(" ", text)
    text = _TIME_RE.sub(" ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    return text


@dataclass(frozen=True)
class _Measurement:
    number: str
    unit: str | None
    operator: str | None
    operator_before: bool


def _measurements(text: str) -> list[_Measurement]:
    normalized = _normalize_measure(text)
    values: list[_Measurement] = []
    for match in _NUMBER_RE.finditer(normalized):
        unit_match = _UNIT_RE.match(normalized, match.end())
        unit = unit_match.group(1) if unit_match is not None else None
        if (
            unit is not None
            and unit.isascii()
            and unit.isalpha()
            and unit.islower()
            and len(unit) > 3
            and unit not in _KNOWN_LONG_UNITS
        ):
            # Long lower-case words after a number are usually nouns, not
            # units ("3 options").  True units such as ms, px, MiB, and the
            # known count/time units above stay.
            unit = None
        before = _OPERATOR_BEFORE_RE.search(normalized[max(0, match.start() - 4) : match.start()])
        after = _OPERATOR_AFTER_RE.search(normalized[match.end() : match.end() + 4])
        operator = None
        operator_before = False
        if before is not None:
            operator = before.group(1)
            operator_before = True
        elif after is not None:
            operator = after.group(1)
        values.append(
            _Measurement(match.group(1), unit, operator, operator_before)
        )
    return values


def _number_present(number: str, text: str) -> bool:
    return (
        re.search(
            r"(?<![\d.])" + re.escape(number) + r"(?!\d)(?!\.\d)", text
        )
        is not None
    )


def _operator_present(measurement: _Measurement, text: str) -> bool:
    if measurement.operator is None:
        return True
    if measurement.operator_before:
        pattern = (
            re.escape(measurement.operator)
            + r"\s*"
            + re.escape(measurement.number)
        )
    else:
        pattern = (
            re.escape(measurement.number)
            + r"\s*"
            + re.escape(measurement.operator)
        )
    return re.search(r"(?<![\d.])" + pattern, text) is not None


def _measurement_present(measurement: _Measurement, text: str) -> bool:
    pattern = r"(?<![\d.])"
    if measurement.operator and measurement.operator_before:
        pattern += re.escape(measurement.operator) + r"\s*"
    pattern += re.escape(measurement.number)
    if measurement.operator and not measurement.operator_before:
        pattern += r"\s*" + re.escape(measurement.operator)
    if measurement.unit:
        pattern += r"\s*" + re.escape(measurement.unit) + r"(?!\w)"
    else:
        pattern += r"(?![\d.])"
    return re.search(pattern, text) is not None


def _number_issues(
    source_text: str,
    main: HTMLNode,
    verified_results: set[str],
) -> list[SemanticIssue]:
    source_measurements = _measurements(
        _markdown_visible_text(
            source_text,
            include_fenced_code=False,
            include_inline_code=False,
        )
    )
    visible_source = _normalize_measure(_visible_text(main))
    visible_numbers = _normalize_measure(_visible_text(main, include_code=False))
    issues: list[SemanticIssue] = []
    for measurement in source_measurements:
        if _measurement_present(measurement, visible_source):
            continue
        number_text = measurement.number
        if not _number_present(number_text, visible_source):
            issues.append(
                SemanticIssue(
                    "number-missing",
                    f"Number {number_text!r} is not visible in main.",
                )
            )
        elif measurement.operator and not _operator_present(
            measurement, visible_source
        ):
            issues.append(
                SemanticIssue(
                    "operator-mismatch",
                    f"Number {number_text!r} must keep comparison operator "
                    f"{measurement.operator!r} in the visible representation.",
                )
            )
        elif measurement.unit and not _measurement_present(
            _Measurement(number_text, measurement.unit, None, False),
            visible_source,
        ):
            issues.append(
                SemanticIssue(
                    "unit-mismatch",
                    f"Number {number_text!r} must keep unit "
                    f"{measurement.unit!r} in the visible representation.",
                )
            )
        else:
            issues.append(
                SemanticIssue(
                    "number-missing",
                    f"Number {number_text!r} is not preserved in main.",
                )
            )

    allowed = {measurement.number for measurement in source_measurements}
    allowed.update(verified_results)
    for match in _NUMBER_RE.finditer(visible_numbers):
        if match.group(1) not in allowed:
            issues.append(
                SemanticIssue(
                    "number-invented",
                    f"Number {match.group(1)!r} is visible in main but is "
                    "neither a source value nor a verified calculation result.",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Calculations


def _number_variants(value: int | float) -> list[str]:
    if isinstance(value, int):
        return [str(value)]
    variants = [repr(value), format(value, "g")]
    if float(value).is_integer():
        variants.append(str(int(value)))
    return list(dict.fromkeys(variants))


def _close(first: float, second: float) -> bool:
    return math.isclose(first, second, rel_tol=1e-9, abs_tol=1e-9)


def _calculation_issues(
    provenance: dict[str, object],
    units_by_id: dict[str, SourceUnit],
    main: HTMLNode,
) -> tuple[int, list[SemanticIssue], set[str]]:
    issues: list[SemanticIssue] = []
    calculations = provenance["calculations"]  # type: ignore[assignment]
    verified: set[str] = set()
    visible = _normalize_measure(_visible_text(main))
    checked = 0
    for calculation in calculations:  # type: ignore[index]
        checked += 1
        start_issues = len(issues)
        identifier = calculation["id"]
        operation = calculation["operation"]
        inputs = calculation["inputs"]
        result = calculation["result"]
        values = [item["value"] for item in inputs]
        units = [item["unit"] for item in inputs]
        formula = str(calculation["formula"])
        if _FORMULA_FORBIDDEN_RE.search(formula):
            issues.append(
                SemanticIssue(
                    "calculation-formula",
                    f"Calculation {identifier!r} contains a formula outside "
                    "the restricted arithmetic notation.",
                )
            )
        expected_value: float | None = None
        expected_unit: str | None = None
        if operation == "sum":
            expected_value = float(sum(values))
            distinct_units = {unit for unit in units if unit is not None}
            if len(distinct_units) > 1:
                issues.append(
                    SemanticIssue(
                        "calculation-unit",
                        f"Calculation {identifier!r} sums inputs with "
                        "different units.",
                    )
                )
            expected_unit = next(iter(distinct_units), None)
        elif operation == "count":
            expected_value = float(len(inputs))
            expected_unit = None
            if any(unit is not None for unit in units):
                issues.append(
                    SemanticIssue(
                        "calculation-unit",
                        f"Calculation {identifier!r} counts values with units; "
                        "count inputs must be dimensionless.",
                    )
                )
        elif operation == "ratio":
            if len(inputs) != 2:
                issues.append(
                    SemanticIssue(
                        "calculation-inputs",
                        f"Calculation {identifier!r} ratio needs exactly two inputs.",
                    )
                )
            else:
                first, second = (float(value) for value in values)
                if second == 0:
                    issues.append(
                        SemanticIssue(
                            "calculation-zero",
                            f"Calculation {identifier!r} divides by zero.",
                        )
                    )
                elif result["unit"] == "%":
                    expected_value = first / second * 100
                    expected_unit = "%"
                elif result["unit"] in {None, "ratio"}:
                    expected_value = first / second
                    expected_unit = result["unit"]
                else:
                    issues.append(
                        SemanticIssue(
                            "calculation-unit",
                            f"Calculation {identifier!r} ratio result unit must "
                            "be null, 'ratio', or '%'.",
                        )
                    )
        elif operation == "scale":
            if len(inputs) != 2:
                issues.append(
                    SemanticIssue(
                        "calculation-inputs",
                        f"Calculation {identifier!r} scale needs exactly two inputs.",
                    )
                )
            elif units[1] is not None:
                issues.append(
                    SemanticIssue(
                        "calculation-unit",
                        f"Calculation {identifier!r} scale factor must be "
                        "dimensionless.",
                    )
                )
            else:
                expected_value = float(values[0]) * float(values[1])
                expected_unit = units[0]
        if expected_value is not None:
            if expected_unit != result["unit"]:
                issues.append(
                    SemanticIssue(
                        "calculation-unit",
                        f"Calculation {identifier!r} result unit "
                        f"{result['unit']!r} does not match {expected_unit!r}.",
                    )
                )
            if not _close(float(result["value"]), expected_value):
                issues.append(
                    SemanticIssue(
                        "calculation-result",
                        f"Calculation {identifier!r} result "
                        f"{result['value']!r} does not recompute to "
                        f"{expected_value!r}.",
                    )
                )
        for item in inputs:
            source_id = item["source"]
            if source_id is None:
                continue
            unit = units_by_id.get(str(source_id))
            if unit is None:
                continue
            text = _normalize_measure(unit.text)
            if not any(
                _number_present(variant, text)
                for variant in _number_variants(item["value"])
            ):
                issues.append(
                    SemanticIssue(
                        "calculation-input",
                        f"Calculation {identifier!r} input value "
                        f"{item['value']!r} does not occur in source unit "
                        f"{source_id!r}.",
                        str(source_id),
                    )
                )
        result_unit = result["unit"]
        if result_unit == "ratio":
            result_unit = None
        if result_unit is None:
            visible_result = any(
                _number_present(variant, visible)
                for variant in _number_variants(result["value"])
            )
        else:
            visible_result = any(
                _measurement_present(
                    _Measurement(variant, result_unit, None, False), visible
                )
                for variant in _number_variants(result["value"])
            )
        if not visible_result:
            issues.append(
                SemanticIssue(
                    "calculation-result-missing",
                    f"Calculation {identifier!r} result "
                    f"{result['value']!r} is not visible in main.",
                )
            )
        if len(issues) == start_issues:
            verified.update(_number_variants(result["value"]))
    return checked, issues, verified


def _plan_order_issues(
    source_text: str,
    document: HTMLDocument,
    main: HTMLNode,
) -> list[SemanticIssue]:
    expected = [number for number, _title in _source_task_headings(source_text)]
    articles = [
        node
        for node in document.nodes
        if node.tag == "article"
        and _attr(node, "data-task-number")
        and _under(node, main)
    ]
    actual = [int(_attr(node, "data-task-number") or "0") for node in articles]
    if actual != expected:
        return [
            SemanticIssue(
                "plan-task-order",
                "Plan Task articles must keep the source Task numbers and "
                f"logical order; expected {expected}, found {actual}.",
            )
        ]
    return []
