"""Lossless Markdown source units and the semantic-v1 schema.

The strict HTML contract in :mod:`sddlib.html_policy` remains the default.  This
module adds the opt-in ``semantic-v1`` source contract:

* :func:`scan_markdown` splits the exact Markdown bytes into source units with
  UTF-8 byte ranges, kinds, IDs, and parent-child relationships.  Unsupported
  constructs are reported instead of being silently dropped.
* :func:`source_index` serializes a scan to the version 1 source-index schema.
* :func:`validate_source_index`, :func:`validate_provenance`, and
  :func:`validate_receipt` validate the three version 1 JSON schemas.  They
  reject unknown fields, unknown versions, duplicate IDs, missing required
  fields, and broken references.

Only the Python standard library is used.  This module does not render Markdown
and does not validate semantic HTML; later tasks build on these definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re


SEMANTIC_CONTRACT = "semantic-v1"
STRICT_CONTRACT = "strict"
SCHEMA_VERSION = 1
SOURCE_INDEX_SCHEMA = "sdd-source-index"
PROVENANCE_SCHEMA = "sdd-provenance"
RECEIPT_SCHEMA = "sdd-html-receipt"

RECEIPT_CONDITION_IDS = ("information", "support", "usability", "render")

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9._:-]+")
_NUMBER_TYPES = (int, float)

_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*$")
_HEADING_RE = re.compile(r"^( {0,3})(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_THEMATIC_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"
)
_LIST_ITEM_RE = re.compile(r"^( *)([-+*]|\d{1,9}[.)])([ \t]+)(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^( {0,3})>( ?)(.*)$")
_SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_REFERENCE_DEFINITION_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*")
_TABLE_SEPARATOR_CELL_RE = re.compile(r":?-{3,}:?")
_GLOSSARY_TERM_RE = re.compile(r"^\*\*([^*]+)\*\*[:：][ \t]*$")
_GLOSSARY_AVOID_RE = re.compile(r"^_Avoid_[:：][ \t]*(.+)$", re.IGNORECASE)
_CHECKBOX_RE = re.compile(r"^\[([ xX])\][ \t]+")
_INLINE_LINK_RE = re.compile(
    r"!?\[([^\]\n]*)\]\(\s*(?:<([^>\n]*)>|([^)\s\n]+))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
_AUTOLINK_RE = re.compile(r"<((?:https?://|mailto:)[^ >]+)>")
_REFERENCE_LINK_RE = re.compile(r"\[([^\]\n]+)\]\[([^\]\n]*)\]")
_FOOTNOTE_REFERENCE_RE = re.compile(r"\[\^([^\]\n]+)\]")

BLOCK_KINDS = frozenset(
    {
        "heading",
        "paragraph",
        "glossary_term",
        "glossary_avoid",
        "list",
        "list_item",
        "code_block",
        "table",
        "table_header",
        "table_cell",
        "block_quote",
        "thematic_break",
    }
)
INLINE_KINDS = frozenset({"inline_code", "link", "image"})
UNIT_KINDS = BLOCK_KINDS | INLINE_KINDS

_ALIGNMENTS = frozenset({"left", "center", "right", "none"})
_REPRESENTATIONS = frozenset({"verbatim", "paraphrase", "reorder", "summary"})
_STRICT_CATEGORIES = frozenset(
    {"code", "path", "identifier", "link", "glossary_term", "avoid"}
)
_SUPPLEMENTARY_KINDS = frozenset({"diagram", "graph", "table", "summary"})
_CALCULATION_OPERATIONS = frozenset({"sum", "count", "ratio", "scale"})
_VERIFICATION_DECISIONS = frozenset({"pass", "fail", "not_run"})
_CONDITION_DECISIONS = frozenset({"met", "unmet", "not_assessed"})

_UNIT_ALLOWED_FIELDS = {
    "heading": {"level", "slug"},
    "paragraph": set(),
    "glossary_term": {"term"},
    "glossary_avoid": {"avoid"},
    "list": {"ordered", "marker", "start", "depth"},
    "list_item": {"ordered", "marker", "checkbox", "depth"},
    "code_block": {"fenced", "info", "language", "closed", "content"},
    "table": {"columns", "alignments"},
    "table_header": {"row", "column", "align"},
    "table_cell": {"row", "column", "align"},
    "block_quote": set(),
    "thematic_break": {"marker"},
    "inline_code": {"value"},
    "link": {"destination", "label", "autolink"},
    "image": {"destination", "alt"},
}
_UNIT_COMMON_FIELDS = {"id", "kind", "source_digest", "range", "parent", "text"}


class SourceScanError(ValueError):
    """The Markdown bytes cannot be scanned as UTF-8 text."""


class UnitSchemaError(ValueError):
    """A source-index, provenance, or receipt object violates the schema."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


@dataclass(frozen=True)
class _Line:
    number: int
    start: int
    end: int
    next_start: int
    text: str


@dataclass(frozen=True)
class SourceUnit:
    """One lossless Markdown source unit."""

    id: str
    kind: str
    digest: str
    start: int
    end: int
    parent: str | None
    text: str
    fields: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "kind": self.kind,
            "source_digest": self.digest,
            "range": {"start": self.start, "end": self.end},
            "parent": self.parent,
            "text": self.text,
        }
        payload.update(self.fields)
        return payload


@dataclass(frozen=True)
class UnsupportedConstruct:
    """One Markdown construct the scanner cannot model losslessly."""

    kind: str
    digest: str
    start: int
    end: int
    text: str
    reason: str

    def to_json(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "source_digest": self.digest,
            "range": {"start": self.start, "end": self.end},
            "text": self.text,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SourceScan:
    """The complete scan result for one exact Markdown byte string."""

    digest: str
    byte_length: int
    units: tuple[SourceUnit, ...]
    unsupported: tuple[UnsupportedConstruct, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unsupported

    @property
    def status(self) -> str:
        return "complete" if self.complete else "incomplete"

    def to_index(self, path: str | None = None) -> dict[str, object]:
        source: dict[str, object] = {
            "digest": self.digest,
            "byte_length": self.byte_length,
        }
        if path is not None:
            source["path"] = path
        return {
            "schema": SOURCE_INDEX_SCHEMA,
            "version": SCHEMA_VERSION,
            "contract": SEMANTIC_CONTRACT,
            "source": source,
            "status": self.status,
            "units": [unit.to_json() for unit in self.units],
            "unsupported": [item.to_json() for item in self.unsupported],
        }


def _split_lines(data: bytes) -> list[_Line]:
    lines: list[_Line] = []
    start = 0
    number = 1
    total = len(data)
    while start < total:
        newline = data.find(b"\n", start)
        if newline < 0:
            content_end = total
            next_start = total
        else:
            content_end = newline
            if content_end > start and data[content_end - 1] == 0x0D:
                content_end -= 1
            next_start = newline + 1
        try:
            text = data[start:content_end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceScanError(
                f"Markdown source is not valid UTF-8 at byte {start + exc.start}"
            ) from exc
        lines.append(_Line(number, start, content_end, next_start, text))
        start = next_start
        number += 1
    return lines


def _leading_spaces(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def _byte_offset(text: str, index: int) -> int:
    return len(text[:index].encode("utf-8"))


def _slugify(text: str, used: dict[str, int]) -> str:
    slug = re.sub(r"\s+", "-", text.strip())
    slug = re.sub(r"[^\w\-]", "", slug, flags=re.UNICODE)
    slug = slug.strip("-").lower() or "section"
    occurrence = used.get(slug, 0)
    used[slug] = occurrence + 1
    return slug if occurrence == 0 else f"{slug}-{occurrence}"


def _plain_inline(text: str) -> str:
    code_spans: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        content = match.group(2)
        if (
            len(content) >= 2
            and content[0] == " "
            and content[-1] == " "
            and content.strip()
        ):
            content = content[1:-1]
        code_spans.append(content)
        return f"\x00code{len(code_spans) - 1}\x00"

    text = re.sub(r"(?<!\\)(`+)(.+?)(?<!`)\1(?!`)", protect_code, text)
    text = _AUTOLINK_RE.sub(r"\1", text)
    raw_tags: list[str] = []

    def protect_raw_tag(match: re.Match[str]) -> str:
        raw_tags.append(match.group(0))
        return f"\x00raw{len(raw_tags) - 1}\x00"

    text = re.sub(r"</?[A-Za-z][^>]*>", protect_raw_tag, text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"(?<!\w)\[([^\]]+)\]", r"\1", text)
    text = re.sub(r"\*\*|__|~~", "", text)
    text = re.sub(r"(?<!\w)[*_](?=\w)|(?<=\w)[*_](?!\w)", "", text)
    text = re.sub(r"\\([\\`*{}\[\]()#+.!_>~-])", r"\1", text)
    text = re.sub(r"\x00raw(\d+)\x00", lambda m: raw_tags[int(m.group(1))], text)
    return re.sub(
        r"\x00code(\d+)\x00",
        lambda m: code_spans[int(m.group(1))],
        text,
    )


def _split_table_cells(text: str) -> list[tuple[int, int, str]]:
    cells: list[tuple[int, int]] = []
    index = 0
    length = len(text)
    while index < length and text[index] in " \t":
        index += 1
    if index < length and text[index] == "|":
        index += 1
    cell_start = index
    while index < length:
        if text[index] == "\\" and index + 1 < length:
            index += 2
            continue
        if text[index] == "|":
            cells.append((cell_start, index))
            cell_start = index + 1
        index += 1
    cells.append((cell_start, length))
    if (
        text.rstrip().endswith("|")
        and cells
        and not text[cells[-1][0] : cells[-1][1]].strip()
    ):
        cells.pop()
    trimmed: list[tuple[int, int, str]] = []
    for start, end in cells:
        while start < end and text[start] in " \t":
            start += 1
        while end > start and text[end - 1] in " \t":
            end -= 1
        trimmed.append((start, end, text[start:end]))
    return trimmed


def _table_alignment(cell: str) -> str:
    left = cell.startswith(":")
    right = cell.endswith(":")
    if left and right:
        return "center"
    if left:
        return "left"
    if right:
        return "right"
    return "none"


class _Scanner:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.digest = "sha256:" + hashlib.sha256(data).hexdigest()
        self.lines = _split_lines(data)
        self.units: list[SourceUnit] = []
        self.unsupported: list[UnsupportedConstruct] = []
        self._heading_slugs: dict[str, int] = {}
        self._last_glossary_term: str | None = None

    def _id(self, kind: str, start: int) -> str:
        return f"{kind}-{start:06d}"

    def _unit(
        self,
        kind: str,
        start: int,
        end: int,
        parent: str | None,
        fields: dict[str, object] | None = None,
    ) -> SourceUnit:
        return SourceUnit(
            id=self._id(kind, start),
            kind=kind,
            digest=self.digest,
            start=start,
            end=end,
            parent=parent,
            text=self.data[start:end].decode("utf-8"),
            fields=dict(fields or {}),
        )

    def _unsupported(self, kind: str, start: int, end: int, reason: str) -> None:
        self.unsupported.append(
            UnsupportedConstruct(
                kind=kind,
                digest=self.digest,
                start=start,
                end=end,
                text=self.data[start:end].decode("utf-8"),
                reason=reason,
            )
        )

    def scan(self) -> SourceScan:
        index = 0
        while index < len(self.lines):
            index = self._scan_block(index)
        self._finish_coverage()
        units = tuple(
            sorted(self.units, key=lambda unit: (unit.start, -unit.end, unit.kind, unit.id))
        )
        unsupported = tuple(
            sorted(self.unsupported, key=lambda item: (item.start, item.end, item.kind))
        )
        return SourceScan(
            digest=self.digest,
            byte_length=len(self.data),
            units=units,
            unsupported=unsupported,
        )

    def _scan_block(self, index: int) -> int:
        line = self.lines[index]
        if not line.text.strip():
            return index + 1

        opened = _FENCE_OPEN_RE.match(line.text)
        if opened:
            return self._scan_fenced_code(index, opened)[0]

        if line.text.startswith("    ") or line.text.startswith("\t"):
            return self._scan_indented_code(index)

        heading = _HEADING_RE.match(line.text)
        if heading:
            return self._scan_heading(index, heading)

        if _THEMATIC_RE.match(line.text):
            self.units.append(
                self._unit(
                    "thematic_break",
                    line.start,
                    line.end,
                    None,
                    {"marker": line.text.strip()[:1]},
                )
            )
            return index + 1

        table_end = self._try_table(index)
        if table_end is not None:
            return table_end

        if _BLOCKQUOTE_RE.match(line.text):
            return self._scan_block_quote(index)

        definition = _REFERENCE_DEFINITION_RE.match(line.text)
        if definition:
            kind = (
                "footnote_definition"
                if definition.group(1).startswith("^")
                else "reference_definition"
            )
            self._unsupported(
                kind,
                line.start,
                line.end,
                "Reference and footnote definitions are not modeled as source units.",
            )
            return index + 1

        list_match = _LIST_ITEM_RE.match(line.text)
        if list_match and len(list_match.group(1)) <= 3:
            return self._scan_list(index, len(list_match.group(1)), None, 0)[1]

        return self._scan_paragraph(index)

    def _scan_fenced_code(
        self,
        index: int,
        opened: re.Match[str],
        parent: str | None = None,
    ) -> tuple[int, int]:
        line = self.lines[index]
        fence = opened.group(2)
        info = opened.group(3).strip()
        close_index: int | None = None
        cursor = index + 1
        while cursor < len(self.lines):
            close = _FENCE_CLOSE_RE.match(self.lines[cursor].text)
            if (
                close
                and close.group(2)[0] == fence[0]
                and len(close.group(2)) >= len(fence)
            ):
                close_index = cursor
                break
            cursor += 1
        if close_index is None:
            end = self.lines[-1].end
            content_end = len(self.data)
            next_index = len(self.lines)
            closed = False
        else:
            end = self.lines[close_index].end
            content_end = self.lines[close_index].start
            next_index = close_index + 1
            closed = True
        content_start = line.next_start
        content = self.data[content_start:content_end].decode("utf-8")
        language = info.split()[0] if info else None
        self.units.append(
            self._unit(
                "code_block",
                line.start,
                end,
                parent,
                {
                    "fenced": True,
                    "info": info,
                    "language": language,
                    "closed": closed,
                    "content": content,
                },
            )
        )
        return next_index, end

    def _scan_indented_code(self, index: int) -> int:
        start = self.lines[index].start
        cursor = index
        last_end = self.lines[index].end
        content_lines: list[str] = []
        while cursor < len(self.lines):
            line = self.lines[cursor]
            if not line.text.strip():
                content_lines.append("")
                cursor += 1
                continue
            if not (line.text.startswith("    ") or line.text.startswith("\t")):
                break
            stripped = line.text[4:] if line.text.startswith("    ") else line.text[1:]
            content_lines.append(stripped)
            last_end = line.end
            cursor += 1
        content = "\n".join(content_lines).rstrip("\n")
        self.units.append(
            self._unit(
                "code_block",
                start,
                last_end,
                None,
                {
                    "fenced": False,
                    "info": "",
                    "language": None,
                    "closed": True,
                    "content": content,
                },
            )
        )
        return cursor

    def _scan_heading(self, index: int, match: re.Match[str]) -> int:
        line = self.lines[index]
        level = len(match.group(2))
        content = match.group(3).strip()
        slug = _slugify(_plain_inline(content), self._heading_slugs)
        unit = self._unit(
            "heading",
            line.start,
            line.end,
            None,
            {"level": level, "slug": slug},
        )
        self.units.append(unit)
        content_start = line.start + _byte_offset(line.text, match.start(3))
        self._scan_inline(match.group(3), content_start, unit.id)
        return index + 1

    def _try_table(self, index: int) -> int | None:
        line = self.lines[index]
        if "|" not in line.text or index + 1 >= len(self.lines):
            return None
        separator = self.lines[index + 1]
        separators = _split_table_cells(separator.text)
        if not separators:
            return None
        if any(
            not _TABLE_SEPARATOR_CELL_RE.fullmatch(cell[2].strip())
            for cell in separators
        ):
            return None
        headers = _split_table_cells(line.text)
        if not headers or len(headers) != len(separators):
            return None
        columns = len(headers)
        alignments = [_table_alignment(cell[2]) for cell in separators]
        table_start = line.start
        cursor = index + 2
        last_end = separator.end
        body_rows: list[tuple[_Line, list[tuple[int, int, str]]]] = []
        while cursor < len(self.lines):
            row = self.lines[cursor]
            if not row.text.strip() or "|" not in row.text:
                break
            cells = _split_table_cells(row.text)
            if len(cells) != columns:
                self._unsupported(
                    "malformed_table",
                    row.start,
                    row.end,
                    f"Table row has {len(cells)} cell(s); expected {columns}.",
                )
                last_end = row.end
                cursor += 1
                continue
            body_rows.append((row, cells))
            last_end = row.end
            cursor += 1
        table = self._unit(
            "table",
            table_start,
            last_end,
            None,
            {"columns": columns, "alignments": alignments},
        )
        self.units.append(table)
        for column, (start_char, end_char, _text) in enumerate(headers, start=1):
            cell_start = line.start + _byte_offset(line.text, start_char)
            cell_end = line.start + _byte_offset(line.text, end_char)
            cell = self._unit(
                "table_header",
                cell_start,
                cell_end,
                table.id,
                {
                    "row": 0,
                    "column": column,
                    "align": alignments[column - 1],
                },
            )
            self.units.append(cell)
            self._scan_inline(cell.text, cell.start, cell.id)
        for row_number, (row, cells) in enumerate(body_rows, start=1):
            for column, (start_char, end_char, _text) in enumerate(cells, start=1):
                cell_start = row.start + _byte_offset(row.text, start_char)
                cell_end = row.start + _byte_offset(row.text, end_char)
                cell = self._unit(
                    "table_cell",
                    cell_start,
                    cell_end,
                    table.id,
                    {
                        "row": row_number,
                        "column": column,
                        "align": alignments[column - 1],
                    },
                )
                self.units.append(cell)
                self._scan_inline(cell.text, cell.start, cell.id)
        return cursor

    def _scan_block_quote(self, index: int) -> int:
        start = self.lines[index].start
        cursor = index
        last_end = self.lines[index].end
        content_lines: list[tuple[str, int]] = []
        while cursor < len(self.lines):
            match = _BLOCKQUOTE_RE.match(self.lines[cursor].text)
            if match is None:
                break
            line = self.lines[cursor]
            content_lines.append(
                (match.group(3), line.start + _byte_offset(line.text, match.start(3)))
            )
            last_end = line.end
            cursor += 1
        unit = self._unit("block_quote", start, last_end, None, {})
        self.units.append(unit)
        for content, content_start in content_lines:
            self._scan_inline(content, content_start, unit.id)
        return cursor

    def _scan_list(
        self, index: int, base_indent: int, parent_id: str | None, depth: int
    ) -> tuple[str, int, int]:
        first_match = _LIST_ITEM_RE.match(self.lines[index].text)
        if first_match is None:
            raise SourceScanError(f"list scan started without a list item at line {index + 1}")
        first_marker = first_match.group(2)
        ordered = first_marker[0].isdigit()
        list_id = self._id("list", self.lines[index].start)
        list_start = self.lines[index].start
        list_end = self.lines[index].end
        marker = first_marker
        start_number = int(first_marker[:-1]) if ordered else None

        while index < len(self.lines):
            line = self.lines[index]
            match = _LIST_ITEM_RE.match(line.text)
            if match is None or len(match.group(1)) != base_indent:
                break
            item_marker = match.group(2)
            if item_marker[0].isdigit() != ordered:
                break
            item_id = self._id("list_item", line.start)
            content_char = match.start(4)
            content_text = match.group(4)
            checkbox: str | None = None
            checkbox_match = _CHECKBOX_RE.match(content_text)
            if checkbox_match:
                checkbox = (
                    "checked" if checkbox_match.group(1).lower() == "x" else "unchecked"
                )
                content_char += checkbox_match.end()
            inline_lines: list[tuple[str, int]] = [
                (
                    line.text[content_char:],
                    line.start + _byte_offset(line.text, content_char),
                )
            ]
            item_start = line.start
            item_end = line.end
            index += 1
            while index < len(self.lines):
                current = self.lines[index]
                if not current.text.strip():
                    lookahead = index
                    while (
                        lookahead < len(self.lines)
                        and not self.lines[lookahead].text.strip()
                    ):
                        lookahead += 1
                    if lookahead >= len(self.lines):
                        index = lookahead
                        break
                    following = self.lines[lookahead]
                    following_match = _LIST_ITEM_RE.match(following.text)
                    following_indent = _leading_spaces(following.text)
                    if following_match and following_indent == base_indent:
                        index = lookahead
                        break
                    if following_indent > base_indent:
                        index = lookahead
                        continue
                    index = lookahead
                    break
                current_match = _LIST_ITEM_RE.match(current.text)
                current_indent = (
                    len(current_match.group(1))
                    if current_match is not None
                    else _leading_spaces(current.text)
                )
                if current_match and current_indent == base_indent:
                    break
                if current_match and current_indent > base_indent:
                    _nested_id, index, nested_end = self._scan_list(
                        index, current_indent, item_id, depth + 1
                    )
                    item_end = max(item_end, nested_end)
                    continue
                if current_indent > base_indent:
                    fence_match = _FENCE_OPEN_RE.match(current.text)
                    if fence_match is not None:
                        index, code_end = self._scan_fenced_code(
                            index, fence_match, item_id
                        )
                        item_end = max(item_end, code_end)
                        continue
                    inline_lines.append((current.text, current.start))
                    item_end = current.end
                    index += 1
                    continue
                break
            item = self._unit(
                "list_item",
                item_start,
                item_end,
                list_id,
                {
                    "ordered": ordered,
                    "marker": item_marker,
                    "checkbox": checkbox,
                    "depth": depth,
                },
            )
            self.units.append(item)
            for content, content_start in inline_lines:
                self._scan_inline(content, content_start, item_id)
            list_end = max(list_end, item_end)
        self.units.append(
            self._unit(
                "list",
                list_start,
                list_end,
                parent_id,
                {
                    "ordered": ordered,
                    "marker": marker,
                    "start": start_number,
                    "depth": depth,
                },
            )
        )
        return list_id, index, list_end

    def _scan_paragraph(self, index: int) -> int:
        start = self.lines[index].start
        cursor = index
        last_end = self.lines[index].end
        block_lines: list[_Line] = [self.lines[index]]
        cursor += 1
        while cursor < len(self.lines):
            line = self.lines[cursor]
            if not line.text.strip():
                break
            if _SETEXT_RE.match(line.text):
                end = line.end
                self._unsupported(
                    "setext_heading",
                    start,
                    end,
                    "Setext headings are not modeled; use an ATX heading.",
                )
                return cursor + 1
            if self._starts_block(line.text):
                break
            block_lines.append(line)
            last_end = line.end
            cursor += 1

        first_text = block_lines[0].text
        term_match = _GLOSSARY_TERM_RE.match(first_text)
        paragraph_text = "\n".join(item.text for item in block_lines)
        avoid_match = _GLOSSARY_AVOID_RE.match(paragraph_text)
        if term_match:
            unit = self._unit(
                "glossary_term",
                start,
                last_end,
                None,
                {"term": term_match.group(1).strip()},
            )
            self._last_glossary_term = unit.id
        elif avoid_match:
            values = [
                value.strip()
                for value in re.split(r"[,、\n]", avoid_match.group(1))
                if value.strip()
            ]
            unit = self._unit(
                "glossary_avoid",
                start,
                last_end,
                self._last_glossary_term,
                {"avoid": values},
            )
        else:
            unit = self._unit("paragraph", start, last_end, None, {})
        self.units.append(unit)
        for line in block_lines:
            self._scan_inline(line.text, line.start, unit.id)
        return cursor

    def _starts_block(self, text: str) -> bool:
        if _FENCE_OPEN_RE.match(text) or _HEADING_RE.match(text):
            return True
        if _THEMATIC_RE.match(text):
            return True
        match = _LIST_ITEM_RE.match(text)
        if match is not None and len(match.group(1)) <= 3:
            return True
        if _BLOCKQUOTE_RE.match(text):
            return True
        if _REFERENCE_DEFINITION_RE.match(text):
            return True
        return False

    def _scan_inline(self, text: str, base: int, parent: str) -> None:
        protected: list[tuple[int, int]] = []
        index = 0
        while index < len(text):
            if text[index] != "`" or (index > 0 and text[index - 1] == "\\"):
                index += 1
                continue
            run_end = index
            while run_end < len(text) and text[run_end] == "`":
                run_end += 1
            run = run_end - index
            needle = "`" * run
            search = run_end
            closing: int | None = None
            while True:
                found_at = text.find(needle, search)
                if found_at < 0:
                    break
                before_ok = found_at == 0 or text[found_at - 1] != "`"
                after_ok = (
                    found_at + run >= len(text) or text[found_at + run] != "`"
                )
                if before_ok and after_ok:
                    closing = found_at
                    break
                search = found_at + 1
            if closing is None:
                index = run_end
                continue
            inner = text[run_end:closing]
            if (
                len(inner) >= 2
                and inner[0] == " "
                and inner[-1] == " "
                and inner.strip()
            ):
                value = inner[1:-1]
            else:
                value = inner
            start = base + _byte_offset(text, index)
            end = base + _byte_offset(text, closing + run)
            unit = SourceUnit(
                id=self._id("inline_code", start),
                kind="inline_code",
                digest=self.digest,
                start=start,
                end=end,
                parent=parent,
                text=self.data[start:end].decode("utf-8"),
                fields={"value": value},
            )
            self.units.append(unit)
            protected.append((index, closing + run))
            index = closing + run

        link_spans: list[tuple[int, int]] = []
        for match in _INLINE_LINK_RE.finditer(text):
            if _overlaps(match.start(), match.end(), protected):
                continue
            if _overlaps(match.start(), match.end(), link_spans):
                continue
            label = match.group(1)
            destination = match.group(2) if match.group(2) is not None else match.group(3)
            if destination is None:
                continue
            kind = "image" if match.group(0).startswith("!") else "link"
            start = base + _byte_offset(text, match.start())
            end = base + _byte_offset(text, match.end())
            fields: dict[str, object]
            if kind == "image":
                fields = {"destination": destination, "alt": label}
            else:
                fields = {
                    "destination": destination,
                    "label": label,
                    "autolink": False,
                }
            self.units.append(
                SourceUnit(
                    id=self._id(kind, start),
                    kind=kind,
                    digest=self.digest,
                    start=start,
                    end=end,
                    parent=parent,
                    text=self.data[start:end].decode("utf-8"),
                    fields=fields,
                )
            )
            link_spans.append((match.start(), match.end()))

        for match in _AUTOLINK_RE.finditer(text):
            if _overlaps(match.start(), match.end(), protected):
                continue
            if _overlaps(match.start(), match.end(), link_spans):
                continue
            destination = match.group(1)
            start = base + _byte_offset(text, match.start())
            end = base + _byte_offset(text, match.end())
            self.units.append(
                SourceUnit(
                    id=self._id("link", start),
                    kind="link",
                    digest=self.digest,
                    start=start,
                    end=end,
                    parent=parent,
                    text=self.data[start:end].decode("utf-8"),
                    fields={
                        "destination": destination,
                        "label": destination,
                        "autolink": True,
                    },
                )
            )
            link_spans.append((match.start(), match.end()))

        for match in _REFERENCE_LINK_RE.finditer(text):
            if _overlaps(match.start(), match.end(), protected):
                continue
            if _overlaps(match.start(), match.end(), link_spans):
                continue
            start = base + _byte_offset(text, match.start())
            end = base + _byte_offset(text, match.end())
            self._unsupported(
                "reference_link",
                start,
                end,
                "Reference-style links are not modeled as source units.",
            )

        for match in _FOOTNOTE_REFERENCE_RE.finditer(text):
            if _overlaps(match.start(), match.end(), protected):
                continue
            if _overlaps(match.start(), match.end(), link_spans):
                continue
            start = base + _byte_offset(text, match.start())
            end = base + _byte_offset(text, match.end())
            self._unsupported(
                "footnote_reference",
                start,
                end,
                "Footnote references are not modeled as source units.",
            )

    def _finish_coverage(self) -> None:
        intervals = sorted(
            [(unit.start, unit.end) for unit in self.units]
            + [(item.start, item.end) for item in self.unsupported]
        )
        merged: list[tuple[int, int]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        for line in self.lines:
            if not line.text.strip():
                continue
            if not any(start <= line.start and line.end <= end for start, end in merged):
                self._unsupported(
                    "unparsed",
                    line.start,
                    line.end,
                    "The parser did not classify this content as a source unit.",
                )


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < span_end and span_start < end for span_start, span_end in spans)


def scan_markdown(markdown: bytes | str) -> SourceScan:
    """Scan exact Markdown bytes without rendering or normalization."""

    if isinstance(markdown, bytes):
        data = markdown
    elif isinstance(markdown, str):
        data = markdown.encode("utf-8")
    else:
        raise TypeError("Markdown must be text or UTF-8 bytes")
    return _Scanner(data).scan()


def source_index(markdown: bytes | str, *, path: str | None = None) -> dict[str, object]:
    """Return the version 1 source-index JSON object for one Markdown document."""

    return scan_markdown(markdown).to_index(path)


def strict_requirements(scan: SourceScan) -> list[dict[str, object]]:
    """Return the strict-preservation targets implied by a scan.

    ``path`` and ``identifier`` targets are added by later semantic validation;
    this helper fixes the code, link, glossary-term, and Avoid values that must
    be retained exactly.
    """

    requirements: list[dict[str, object]] = []
    for unit in scan.units:
        if unit.kind == "code_block":
            requirements.append(
                {
                    "unit": unit.id,
                    "category": "code",
                    "value": unit.fields["content"],
                }
            )
        elif unit.kind == "inline_code":
            requirements.append(
                {"unit": unit.id, "category": "code", "value": unit.fields["value"]}
            )
        elif unit.kind in {"link", "image"}:
            requirements.append(
                {
                    "unit": unit.id,
                    "category": "link",
                    "value": unit.fields["destination"],
                }
            )
        elif unit.kind == "glossary_term":
            requirements.append(
                {
                    "unit": unit.id,
                    "category": "glossary_term",
                    "value": unit.fields["term"],
                }
            )
        elif unit.kind == "glossary_avoid":
            for value in unit.fields["avoid"]:  # type: ignore[union-attr]
                requirements.append(
                    {"unit": unit.id, "category": "avoid", "value": value}
                )
    return requirements


# ---------------------------------------------------------------------------
# Schema validation helpers


def _fail(path: str, message: str) -> None:
    raise UnitSchemaError(path, message)


def _object(
    value: object,
    path: str,
    *,
    required: set[str],
    allowed: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    keys = set(value)
    unknown = sorted(keys - allowed)
    if unknown:
        _fail(path, "unknown field(s): " + ", ".join(unknown))
    missing = sorted(required - keys)
    if missing:
        _fail(path, "missing required field(s): " + ", ".join(missing))
    return value


def _string(
    value: object, path: str, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    if not allow_empty and not value:
        _fail(path, "must not be empty")
    return value


def _integer(
    value: object,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        _fail(path, "must be an integer")
    if minimum is not None and value < minimum:
        _fail(path, f"must be at least {minimum}")
    if maximum is not None and value > maximum:
        _fail(path, f"must be at most {maximum}")
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        _fail(path, "must be a boolean")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _digest(value: object, path: str) -> str:
    text = _string(value, path)
    if not _DIGEST_RE.fullmatch(text):
        _fail(path, "must be a sha256:<64 lowercase hex> digest")
    return text


def _choice(value: object, path: str, choices: frozenset[str] | set[str]) -> str:
    text = _string(value, path)
    if text not in choices:
        _fail(path, f"unsupported value {text!r}")
    return text


def _range(
    value: object, path: str, *, byte_length: int | None = None
) -> tuple[int, int]:
    payload = _object(value, path, required={"start", "end"}, allowed={"start", "end"})
    start = _integer(payload["start"], f"{path}.start", minimum=0)
    end = _integer(payload["end"], f"{path}.end", minimum=0)
    if end < start:
        _fail(path, "end must not be before start")
    if byte_length is not None and end > byte_length:
        _fail(path, f"end exceeds byte_length {byte_length}")
    return start, end


def _schema_header(value: dict[str, object], expected: str) -> None:
    if value.get("schema") != expected:
        _fail("schema", f"must be {expected!r}")
    version = value.get("version")
    if type(version) is not int or version != SCHEMA_VERSION:
        _fail("version", f"unsupported version {version!r}; expected {SCHEMA_VERSION}")
    if value.get("contract") != SEMANTIC_CONTRACT:
        _fail("contract", f"must be {SEMANTIC_CONTRACT!r}")


def _ids(items: list[dict[str, object]], path: str) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        identifier = _string(item["id"], f"{path}[{index}].id")
        if identifier in seen:
            _fail(f"{path}[{index}].id", f"duplicate id {identifier!r}")
        seen.add(identifier)
    return seen


def _validate_parent_graph(
    units: list[dict[str, object]],
    path: str,
    *,
    full: bool,
) -> dict[str, dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for index, unit in enumerate(units):
        identifier = _string(unit["id"], f"{path}[{index}].id")
        by_id[identifier] = unit
    for index, unit in enumerate(units):
        identifier = unit["id"]  # type: ignore[assignment]
        parent_id = unit["parent"]
        if parent_id is not None:
            parent_id = _string(parent_id, f"{path}[{index}].parent")
            if parent_id == identifier:
                _fail(f"{path}[{index}].parent", "a unit cannot parent itself")
            if parent_id not in by_id:
                _fail(
                    f"{path}[{index}].parent",
                    f"unknown parent id {parent_id!r}",
                )
            expected = _expected_parent_kinds(unit["kind"])  # type: ignore[arg-type]
            parent_kind = by_id[parent_id]["kind"]
            if parent_kind not in expected:
                _fail(
                    f"{path}[{index}].parent",
                    f"kind {parent_kind!r} cannot parent {unit['kind']!r}",
                )
            if full and unit["kind"] != "glossary_avoid":
                parent_range = by_id[parent_id]["range"]  # type: ignore[assignment]
                child_range = unit["range"]  # type: ignore[assignment]
                if not (
                    parent_range["start"] <= child_range["start"]  # type: ignore[index]
                    and child_range["end"] <= parent_range["end"]  # type: ignore[index]
                ):
                    _fail(f"{path}[{index}].range", "must be contained in its parent range")
        else:
            expected = _expected_parent_kinds(unit["kind"])  # type: ignore[arg-type]
            if None not in expected:
                _fail(f"{path}[{index}].parent", "must reference a parent")
    seen: set[str] = set()
    for identifier in by_id:
        chain: set[str] = set()
        current: str | None = identifier
        while current is not None:
            if current in chain:
                _fail(path, f"parent cycle at {current!r}")
            chain.add(current)
            current = by_id[current]["parent"]  # type: ignore[assignment]
        seen.add(identifier)
    return by_id


def _expected_parent_kinds(kind: str) -> set[str | None]:
    if kind == "list":
        return {None, "list_item"}
    if kind == "list_item":
        return {"list"}
    if kind in {"table_header", "table_cell"}:
        return {"table"}
    if kind == "code_block":
        return {None, "list_item"}
    if kind in INLINE_KINDS:
        return set(BLOCK_KINDS)
    if kind == "glossary_avoid":
        return {None, "glossary_term"}
    return {None}


def _validate_unit_fields(unit: dict[str, object], path: str) -> None:
    kind = unit["kind"]
    fields = _UNIT_ALLOWED_FIELDS[kind]  # type: ignore[index]
    allowed = _UNIT_COMMON_FIELDS | fields
    required = _UNIT_COMMON_FIELDS | fields
    _object(unit, path, required=required, allowed=allowed)
    if kind == "heading":
        _integer(unit["level"], f"{path}.level", minimum=1, maximum=6)
        _string(unit["slug"], f"{path}.slug")
    elif kind == "glossary_term":
        _string(unit["term"], f"{path}.term")
    elif kind == "glossary_avoid":
        values = _list(unit["avoid"], f"{path}.avoid")
        if not values:
            _fail(f"{path}.avoid", "must not be empty")
        for index, value in enumerate(values):
            _string(value, f"{path}.avoid[{index}]")
    elif kind in {"list", "list_item"}:
        _boolean(unit["ordered"], f"{path}.ordered")
        _string(unit["marker"], f"{path}.marker")
        _integer(unit["depth"], f"{path}.depth", minimum=0)
        if kind == "list":
            if unit["start"] is not None:
                _integer(unit["start"], f"{path}.start", minimum=0)
        else:
            checkbox = unit["checkbox"]
            if checkbox is not None and checkbox not in {"checked", "unchecked"}:
                _fail(f"{path}.checkbox", "must be null, 'checked', or 'unchecked'")
    elif kind == "code_block":
        _boolean(unit["fenced"], f"{path}.fenced")
        _boolean(unit["closed"], f"{path}.closed")
        _string(unit["info"], f"{path}.info", allow_empty=True)
        if unit["language"] is not None:
            _string(unit["language"], f"{path}.language")
        _string(unit["content"], f"{path}.content", allow_empty=True)
    elif kind == "table":
        _integer(unit["columns"], f"{path}.columns", minimum=1)
        alignments = _list(unit["alignments"], f"{path}.alignments")
        if len(alignments) != unit["columns"]:
            _fail(f"{path}.alignments", "length must equal columns")
        for index, alignment in enumerate(alignments):
            _choice(alignment, f"{path}.alignments[{index}]", set(_ALIGNMENTS))
    elif kind in {"table_header", "table_cell"}:
        _integer(unit["row"], f"{path}.row", minimum=0)
        _integer(unit["column"], f"{path}.column", minimum=1)
        _choice(unit["align"], f"{path}.align", set(_ALIGNMENTS))
    elif kind == "thematic_break":
        _string(unit["marker"], f"{path}.marker")
    elif kind == "inline_code":
        _string(unit["value"], f"{path}.value", allow_empty=True)
    elif kind == "link":
        _string(unit["destination"], f"{path}.destination")
        _string(unit["label"], f"{path}.label", allow_empty=True)
        _boolean(unit["autolink"], f"{path}.autolink")
    elif kind == "image":
        _string(unit["destination"], f"{path}.destination")
        _string(unit["alt"], f"{path}.alt", allow_empty=True)


def _validate_full_unit(
    unit: object,
    path: str,
    *,
    digest: str,
    byte_length: int,
) -> None:
    if not isinstance(unit, dict):
        _fail(path, "must be an object")
    kind = unit.get("kind")
    if not isinstance(kind, str):
        _fail(f"{path}.kind", "must be a string")
    if kind not in UNIT_KINDS:
        _fail(f"{path}.kind", f"unknown unit kind {kind!r}")
    _validate_unit_fields(unit, path)
    _string(unit["id"], f"{path}.id")
    if not _IDENTIFIER_RE.fullmatch(unit["id"]):  # type: ignore[arg-type]
        _fail(f"{path}.id", "must contain only identifier characters")
    if _digest(unit["source_digest"], f"{path}.source_digest") != digest:
        _fail(f"{path}.source_digest", "must equal the index source digest")
    _range(unit["range"], f"{path}.range", byte_length=byte_length)
    _string(unit["text"], f"{path}.text", allow_empty=True)


def _validate_compact_unit(
    unit: object,
    path: str,
    *,
    digest: str,
) -> None:
    if not isinstance(unit, dict):
        _fail(path, "must be an object")
    kind = unit.get("kind")
    if not isinstance(kind, str):
        _fail(f"{path}.kind", "must be a string")
    if kind not in UNIT_KINDS:
        _fail(f"{path}.kind", f"unknown unit kind {kind!r}")
    _object(
        unit,
        path,
        required={"id", "kind", "source_digest", "range", "parent"},
        allowed={"id", "kind", "source_digest", "range", "parent"},
    )
    _string(unit["id"], f"{path}.id")
    if _digest(unit["source_digest"], f"{path}.source_digest") != digest:
        _fail(f"{path}.source_digest", "must equal the source digest")
    _range(unit["range"], f"{path}.range")


def _validate_unit_definition_list(
    units_value: object,
    path: str,
    *,
    digest: str,
    byte_length: int | None,
    full: bool,
) -> list[dict[str, object]]:
    values = _list(units_value, path)
    units: list[dict[str, object]] = []
    for index, value in enumerate(values):
        if full:
            _validate_full_unit(
                value,
                f"{path}[{index}]",
                digest=digest,
                byte_length=byte_length or 0,
            )
        else:
            _validate_compact_unit(value, f"{path}[{index}]", digest=digest)
        units.append(value)  # type: ignore[arg-type]
    _ids(units, path)
    _validate_parent_graph(units, path, full=full)
    return units


def validate_source_index(value: object) -> dict[str, object]:
    """Validate a version 1 source-index object and return it unchanged."""

    allowed = {
        "schema",
        "version",
        "contract",
        "source",
        "status",
        "units",
        "unsupported",
    }
    index = _object(
        value,
        "source-index",
        required=allowed,
        allowed=allowed,
    )
    _schema_header(index, SOURCE_INDEX_SCHEMA)
    source = _object(
        index["source"],
        "source",
        required={"digest", "byte_length"},
        allowed={"path", "digest", "byte_length"},
    )
    digest = _digest(source["digest"], "source.digest")
    byte_length = _integer(source["byte_length"], "source.byte_length", minimum=0)
    if "path" in source:
        _string(source["path"], "source.path")
    _validate_unit_definition_list(
        index["units"],
        "units",
        digest=digest,
        byte_length=byte_length,
        full=True,
    )
    status = _choice(index["status"], "status", {"complete", "incomplete"})
    unsupported_values = _list(index["unsupported"], "unsupported")
    seen_ranges: set[tuple[int, int, str]] = set()
    for position, item in enumerate(unsupported_values):
        item_path = f"unsupported[{position}]"
        payload = _object(
            item,
            item_path,
            required={"kind", "source_digest", "range", "text", "reason"},
            allowed={"kind", "source_digest", "range", "text", "reason"},
        )
        _string(payload["kind"], f"{item_path}.kind")
        if _digest(payload["source_digest"], f"{item_path}.source_digest") != digest:
            _fail(f"{item_path}.source_digest", "must equal the index source digest")
        _range(payload["range"], f"{item_path}.range", byte_length=byte_length)
        _string(payload["text"], f"{item_path}.text", allow_empty=True)
        _string(payload["reason"], f"{item_path}.reason")
        key = (
            payload["range"]["start"],  # type: ignore[index]
            payload["range"]["end"],  # type: ignore[index]
            payload["kind"],  # type: ignore[arg-type]
        )
        if key in seen_ranges:
            _fail(item_path, "duplicate unsupported construct")
        seen_ranges.add(key)
    if status == "complete" and unsupported_values:
        _fail("status", "complete requires an empty unsupported list")
    if status == "incomplete" and not unsupported_values:
        _fail("status", "incomplete requires at least one unsupported construct")
    return index


def validate_provenance(value: object) -> dict[str, object]:
    """Validate a version 1 ``template#sdd-provenance`` object."""

    allowed = {
        "schema",
        "version",
        "contract",
        "source",
        "units",
        "mappings",
        "strict",
        "supplementary",
        "calculations",
    }
    provenance = _object(value, "provenance", required=allowed, allowed=allowed)
    _schema_header(provenance, PROVENANCE_SCHEMA)
    source = _object(
        provenance["source"],
        "source",
        required={"path", "digest"},
        allowed={"path", "digest"},
    )
    _string(source["path"], "source.path")
    digest = _digest(source["digest"], "source.digest")
    units = _validate_unit_definition_list(
        provenance["units"],
        "units",
        digest=digest,
        byte_length=None,
        full=False,
    )
    unit_ids = {unit["id"] for unit in units}

    mappings = _list(provenance["mappings"], "mappings")
    mapped_units: set[str] = set()
    for position, item in enumerate(mappings):
        item_path = f"mappings[{position}]"
        payload = _object(
            item,
            item_path,
            required={"unit", "representation", "targets"},
            allowed={"unit", "representation", "targets"},
        )
        unit_id = _string(payload["unit"], f"{item_path}.unit")
        if unit_id not in unit_ids:
            _fail(f"{item_path}.unit", f"unknown unit id {unit_id!r}")
        if unit_id in mapped_units:
            _fail(f"{item_path}.unit", f"duplicate mapping for unit {unit_id!r}")
        mapped_units.add(unit_id)
        _choice(
            payload["representation"],
            f"{item_path}.representation",
            set(_REPRESENTATIONS),
        )
        _targets(payload["targets"], f"{item_path}.targets")

    strict = _list(provenance["strict"], "strict")
    strict_keys: set[tuple[str, str, str]] = set()
    for position, item in enumerate(strict):
        item_path = f"strict[{position}]"
        payload = _object(
            item,
            item_path,
            required={"unit", "category", "value", "targets"},
            allowed={"unit", "category", "value", "targets"},
        )
        unit_id = _string(payload["unit"], f"{item_path}.unit")
        if unit_id not in unit_ids:
            _fail(f"{item_path}.unit", f"unknown unit id {unit_id!r}")
        category = _choice(
            payload["category"], f"{item_path}.category", set(_STRICT_CATEGORIES)
        )
        text = _string(payload["value"], f"{item_path}.value", allow_empty=True)
        _targets(payload["targets"], f"{item_path}.targets")
        key = (unit_id, category, text)  # type: ignore[assignment]
        if key in strict_keys:
            _fail(item_path, "duplicate strict-preservation target")
        strict_keys.add(key)

    supplementary = _list(provenance["supplementary"], "supplementary")
    supplementary_ids: set[str] = set()
    for position, item in enumerate(supplementary):
        item_path = f"supplementary[{position}]"
        payload = _object(
            item,
            item_path,
            required={"id", "kind", "units", "targets"},
            allowed={"id", "kind", "units", "targets", "description"},
        )
        identifier = _string(payload["id"], f"{item_path}.id")
        if identifier in supplementary_ids:
            _fail(f"{item_path}.id", f"duplicate id {identifier!r}")
        supplementary_ids.add(identifier)
        _choice(
            payload["kind"], f"{item_path}.kind", set(_SUPPLEMENTARY_KINDS)
        )
        source_units = _list(payload["units"], f"{item_path}.units")
        if not source_units:
            _fail(f"{item_path}.units", "must not be empty")
        for index, unit_id in enumerate(source_units):
            _string(unit_id, f"{item_path}.units[{index}]")
            if unit_id not in unit_ids:
                _fail(f"{item_path}.units[{index}]", f"unknown unit id {unit_id!r}")
        _targets(payload["targets"], f"{item_path}.targets")
        if "description" in payload:
            _string(payload["description"], f"{item_path}.description")

    calculations = _list(provenance["calculations"], "calculations")
    calculation_ids: set[str] = set()
    for position, item in enumerate(calculations):
        item_path = f"calculations[{position}]"
        payload = _object(
            item,
            item_path,
            required={"id", "operation", "inputs", "formula", "result"},
            allowed={"id", "operation", "inputs", "formula", "result"},
        )
        identifier = _string(payload["id"], f"{item_path}.id")
        if identifier in calculation_ids:
            _fail(f"{item_path}.id", f"duplicate id {identifier!r}")
        calculation_ids.add(identifier)
        _choice(
            payload["operation"],
            f"{item_path}.operation",
            set(_CALCULATION_OPERATIONS),
        )
        inputs = _list(payload["inputs"], f"{item_path}.inputs")
        if not inputs:
            _fail(f"{item_path}.inputs", "must not be empty")
        for index, input_value in enumerate(inputs):
            input_path = f"{item_path}.inputs[{index}]"
            entry = _object(
                input_value,
                input_path,
                required={"value", "unit", "source"},
                allowed={"value", "unit", "source"},
            )
            _number(entry["value"], f"{input_path}.value")
            if entry["unit"] is not None:
                _string(entry["unit"], f"{input_path}.unit")
            if entry["source"] is not None:
                source_id = _string(entry["source"], f"{input_path}.source")
                if source_id not in unit_ids:
                    _fail(f"{input_path}.source", f"unknown unit id {source_id!r}")
        _string(payload["formula"], f"{item_path}.formula")
        result = _object(
            payload["result"],
            f"{item_path}.result",
            required={"value", "unit"},
            allowed={"value", "unit"},
        )
        _number(result["value"], f"{item_path}.result.value")
        if result["unit"] is not None:
            _string(result["unit"], f"{item_path}.result.unit")
    return provenance


def _targets(value: object, path: str) -> list[object]:
    targets = _list(value, path)
    if not targets:
        _fail(path, "must not be empty")
    for index, target in enumerate(targets):
        _string(target, f"{path}[{index}]")
    return targets


def _number(value: object, path: str) -> int | float:
    if type(value) not in _NUMBER_TYPES:
        _fail(path, "must be a number")
    return value  # type: ignore[return-value]


def _fingerprints(value: object, path: str, *, required: bool) -> None:
    entries = _list(value, path)
    if required and not entries:
        _fail(path, "must not be empty")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        entry_path = f"{path}[{index}]"
        payload = _object(
            entry,
            entry_path,
            required={"path", "digest"},
            allowed={"path", "digest"},
        )
        resource_path = _string(payload["path"], f"{entry_path}.path")
        _digest(payload["digest"], f"{entry_path}.digest")
        if resource_path in seen:
            _fail(f"{entry_path}.path", f"duplicate resource path {resource_path!r}")
        seen.add(resource_path)


def validate_receipt(value: object) -> dict[str, object]:
    """Validate a version 1 semantic evaluation receipt object."""

    allowed = {
        "schema",
        "version",
        "contract",
        "source",
        "html",
        "inputs",
        "versions",
        "generation",
        "h2",
        "verification",
        "conditions",
    }
    receipt = _object(value, "receipt", required=allowed, allowed=allowed)
    _schema_header(receipt, RECEIPT_SCHEMA)
    source = _object(
        receipt["source"],
        "source",
        required={"path", "digest"},
        allowed={"path", "digest"},
    )
    _string(source["path"], "source.path")
    _digest(source["digest"], "source.digest")
    html = _object(
        receipt["html"],
        "html",
        required={"path", "digest"},
        allowed={"path", "digest"},
    )
    _string(html["path"], "html.path")
    _digest(html["digest"], "html.digest")

    inputs = _object(
        receipt["inputs"],
        "inputs",
        required={"css", "resources", "policy"},
        allowed={"css", "resources", "policy"},
    )
    _fingerprints(inputs["css"], "inputs.css", required=True)
    _fingerprints(inputs["resources"], "inputs.resources", required=False)
    policy = _object(
        inputs["policy"],
        "inputs.policy",
        required={"version", "digest"},
        allowed={"version", "digest"},
    )
    _string(policy["version"], "inputs.policy.version")
    _digest(policy["digest"], "inputs.policy.digest")

    versions = _object(
        receipt["versions"],
        "versions",
        required={"settings", "rubric", "profile"},
        allowed={"settings", "rubric", "profile"},
    )
    for name in ("settings", "rubric", "profile"):
        _string(versions[name], f"versions.{name}")

    generation = _object(
        receipt["generation"],
        "generation",
        required={"id", "revision", "parent", "job", "cycle"},
        allowed={"id", "revision", "parent", "job", "cycle"},
    )
    _string(generation["id"], "generation.id")
    _integer(generation["revision"], "generation.revision", minimum=0)
    if generation["parent"] is not None:
        _string(generation["parent"], "generation.parent")
    _string(generation["job"], "generation.job")
    _string(generation["cycle"], "generation.cycle")

    h2 = _object(
        receipt["h2"],
        "h2",
        required={"reference", "purpose"},
        allowed={"reference", "purpose"},
    )
    _string(h2["reference"], "h2.reference")
    if h2["purpose"] != "Html":
        _fail("h2.purpose", "must be 'Html'")

    verification = _object(
        receipt["verification"],
        "verification",
        required={"result", "checks"},
        allowed={"result", "checks"},
    )
    _choice(verification["result"], "verification.result", {"pass", "fail"})
    checks = _list(verification["checks"], "verification.checks")
    if not checks:
        _fail("verification.checks", "must not be empty")
    check_names: set[str] = set()
    for position, check in enumerate(checks):
        check_path = f"verification.checks[{position}]"
        payload = _object(
            check,
            check_path,
            required={"name", "decision", "evidence"},
            allowed={"name", "decision", "evidence"},
        )
        name = _string(payload["name"], f"{check_path}.name")
        if name in check_names:
            _fail(f"{check_path}.name", f"duplicate check name {name!r}")
        check_names.add(name)
        _choice(
            payload["decision"],
            f"{check_path}.decision",
            set(_VERIFICATION_DECISIONS),
        )
        evidence = _list(payload["evidence"], f"{check_path}.evidence")
        if payload["decision"] in {"pass", "fail"} and not evidence:
            _fail(f"{check_path}.evidence", "must not be empty for pass or fail")
        for index, reference in enumerate(evidence):
            _string(reference, f"{check_path}.evidence[{index}]")

    conditions = _list(receipt["conditions"], "conditions")
    condition_ids: set[str] = set()
    for position, condition in enumerate(conditions):
        condition_path = f"conditions[{position}]"
        payload = _object(
            condition,
            condition_path,
            required={"id", "decision", "evidence"},
            allowed={"id", "decision", "evidence"},
        )
        identifier = _string(payload["id"], f"{condition_path}.id")
        if identifier not in RECEIPT_CONDITION_IDS:
            _fail(f"{condition_path}.id", f"unknown condition id {identifier!r}")
        if identifier in condition_ids:
            _fail(f"{condition_path}.id", f"duplicate condition id {identifier!r}")
        condition_ids.add(identifier)
        _choice(
            payload["decision"],
            f"{condition_path}.decision",
            set(_CONDITION_DECISIONS),
        )
        evidence = _list(payload["evidence"], f"{condition_path}.evidence")
        if not evidence:
            _fail(f"{condition_path}.evidence", "must not be empty")
        for index, reference in enumerate(evidence):
            _string(reference, f"{condition_path}.evidence[{index}]")
    missing_conditions = sorted(set(RECEIPT_CONDITION_IDS) - condition_ids)
    if missing_conditions:
        _fail("conditions", "missing condition(s): " + ", ".join(missing_conditions))
    return receipt
