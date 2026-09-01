from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
from typing import TypeAlias
from urllib.parse import unquote, urlsplit


PathInput: TypeAlias = str | os.PathLike[str]
PolicyResult: TypeAlias = dict[str, object]

_TARGET_DIRECTORIES = {
    "adr": "adr",
    "specs": "spec",
    "plans": "plan",
}
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_DIGEST_SHAPE_RE = re.compile(r"sha256:[0-9a-f]{64}", re.IGNORECASE)


class DigestStatus(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    MALFORMED = "malformed"
    UPPERCASE = "uppercase"


@dataclass(frozen=True)
class DigestMetadata:
    """The result of parsing the source digest metadata in one HTML document."""

    status: DigestStatus
    digest: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status is DigestStatus.VALID


@dataclass(frozen=True)
class Target:
    """A canonical Markdown target and its adjacent HTML companion."""

    repository_root: Path
    source_path: Path
    companion_path: Path
    kind: str

    @property
    def html_path(self) -> Path:
        return self.companion_path

    @property
    def source_relative(self) -> str:
        return self.source_path.relative_to(self.repository_root).as_posix()

    @property
    def companion_relative(self) -> str:
        return self.companion_path.relative_to(self.repository_root).as_posix()

    @property
    def html_relative(self) -> str:
        return self.companion_relative


class PolicyInputError(ValueError):
    """An invalid policy argument that callers should map to exit code 2."""

    exit_code = 2

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
        self.result: PolicyResult = _result("deny", message)


class PathOutsideRepository(PolicyInputError):
    """A supplied path does not resolve inside the repository root."""


class _DigestMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.matches: list[list[tuple[str, str | None]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "meta":
            return
        names = [value for name, value in attrs if name == "name"]
        if any(value == "sdd-source-digest" for value in names):
            self.matches.append(attrs)
            return
        # Case variants are malformed metadata, rather than an unrelated meta.
        if any(
            value is not None and value.lower() == "sdd-source-digest"
            for value in names
        ):
            self.matches.append(attrs)


def _result(
    decision: str,
    message: str,
    paths: Iterable[str] = (),
    expected_digests: dict[str, str] | None = None,
) -> PolicyResult:
    return {
        "decision": decision,
        "message": message,
        "paths": list(paths),
        "expected_digests": dict(expected_digests or {}),
    }


def _repository_root(repo_root: PathInput) -> Path:
    try:
        root = Path(repo_root)
    except (TypeError, ValueError) as exc:
        raise PolicyInputError("repository root must be a valid path") from exc
    if not os.fspath(root):
        raise PolicyInputError("repository root must not be empty")
    try:
        root = root.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PolicyInputError("repository root cannot be resolved") from exc
    if not root.is_dir():
        raise PolicyInputError(f"repository root is not a directory: {root}")
    return root


def _path_and_relative(root: Path, raw_path: PathInput) -> tuple[Path, Path]:
    try:
        value = os.fspath(raw_path)
    except TypeError as exc:
        raise PolicyInputError("policy paths must be strings or path-like values") from exc
    if isinstance(value, bytes):
        raise PolicyInputError("policy paths must be text, not bytes")
    if not value:
        raise PolicyInputError("policy paths must not be empty")
    if "\x00" in value:
        raise PolicyInputError("policy paths must not contain NUL bytes")
    try:
        supplied = Path(value)
        candidate = supplied if supplied.is_absolute() else root / supplied
        # Keep the lexical name for target classification; resolve separately
        # so symlinks cannot escape the repository containment check.
        lexical = Path(os.path.abspath(candidate))
        relative = lexical.relative_to(root)
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathOutsideRepository(f"path is outside repository: {value}") from exc
    except (OSError, RuntimeError) as exc:
        raise PolicyInputError(f"path cannot be resolved: {value}") from exc
    return resolved, relative


def _target_from_relative(root: Path, relative: Path) -> Target | None:
    if relative == Path("CONTEXT.md"):
        source_relative = relative
        kind = "context"
    elif (
        len(relative.parts) == 3
        and relative.parts[0] == "docs"
        and relative.parts[1] == "adr"
        and relative.name.endswith(".md")
        and not relative.name.startswith(".")
    ):
        source_relative = relative
        kind = "adr"
    elif (
        len(relative.parts) == 4
        and relative.parts[0] == "docs"
        and relative.parts[1] == "sdd"
        and relative.parts[2] in _TARGET_DIRECTORIES
        and relative.name.endswith(".md")
        and not relative.name.startswith(".")
    ):
        source_relative = relative
        kind = _TARGET_DIRECTORIES[relative.parts[2]]
    elif relative == Path("CONTEXT.html"):
        source_relative = Path("CONTEXT.md")
        kind = "context"
    elif (
        len(relative.parts) == 3
        and relative.parts[0] == "docs"
        and relative.parts[1] == "adr"
        and relative.name.endswith(".html")
        and not relative.name.startswith(".")
    ):
        source_relative = relative.with_suffix(".md")
        kind = "adr"
    elif (
        len(relative.parts) == 4
        and relative.parts[0] == "docs"
        and relative.parts[1] == "sdd"
        and relative.parts[2] in _TARGET_DIRECTORIES
        and relative.name.endswith(".html")
        and not relative.name.startswith(".")
    ):
        source_relative = relative.with_suffix(".md")
        kind = _TARGET_DIRECTORIES[relative.parts[2]]
    else:
        return None

    source_path = root / source_relative
    companion_path = root / source_relative.with_suffix(".html")
    for path in (source_path, companion_path):
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise PathOutsideRepository(
                f"target pair resolves outside repository: {path}"
            ) from exc
        except (OSError, RuntimeError) as exc:
            raise PolicyInputError(f"target path cannot be resolved: {path}") from exc
    return Target(root, source_path, companion_path, kind)


def resolve_target(repo_root: PathInput, path: PathInput) -> Target | None:
    """Resolve one target path, returning ``None`` for unrelated in-repo paths."""

    root = _repository_root(repo_root)
    _resolved, relative = _path_and_relative(root, path)
    return _target_from_relative(root, relative)


def sha256_file(path: PathInput) -> str:
    """Return the lowercase SHA-256 digest of a file's exact bytes."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_digest_metadata(html: str | bytes) -> DigestMetadata:
    """Parse exactly one strict ``sdd-source-digest`` meta element."""

    if isinstance(html, bytes):
        try:
            html = html.decode("utf-8")
        except UnicodeDecodeError:
            return DigestMetadata(DigestStatus.MALFORMED)
    if not isinstance(html, str):
        raise TypeError("HTML must be text or UTF-8 bytes")

    parser = _DigestMetaParser()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError):
        return DigestMetadata(DigestStatus.MALFORMED)

    if not parser.matches:
        return DigestMetadata(DigestStatus.MISSING)
    if len(parser.matches) > 1:
        return DigestMetadata(DigestStatus.DUPLICATE)

    attrs = parser.matches[0]
    names = [value for name, value in attrs if name == "name"]
    if names != ["sdd-source-digest"]:
        return DigestMetadata(DigestStatus.MALFORMED)
    contents = [value for name, value in attrs if name == "content"]
    if len(contents) != 1 or contents[0] is None:
        return DigestMetadata(DigestStatus.MALFORMED)
    content = contents[0]
    if _DIGEST_RE.fullmatch(content):
        return DigestMetadata(DigestStatus.VALID, content)
    if _DIGEST_SHAPE_RE.fullmatch(content) and content != content.lower():
        return DigestMetadata(DigestStatus.UPPERCASE)
    return DigestMetadata(DigestStatus.MALFORMED)


def read_digest_metadata(path: PathInput) -> DigestMetadata:
    """Read and parse digest metadata without normalizing the HTML bytes."""

    try:
        return parse_digest_metadata(Path(path).read_bytes())
    except FileNotFoundError:
        return DigestMetadata(DigestStatus.MISSING)
    except OSError:
        return DigestMetadata(DigestStatus.MALFORMED)


def _path_values(value: Iterable[PathInput], label: str) -> list[PathInput]:
    if isinstance(value, (str, bytes, os.PathLike)):
        raise PolicyInputError(f"{label} must be a sequence of paths")
    try:
        return list(value)
    except TypeError as exc:
        raise PolicyInputError(f"{label} must be a sequence of paths") from exc


def _permission_paths(
    root: Path,
    values: Iterable[PathInput],
    *,
    label: str,
    require: str,
) -> set[str]:
    allowed: set[str] = set()
    for raw_path in _path_values(values, label):
        _resolved, relative = _path_and_relative(root, raw_path)
        target = _target_from_relative(root, relative)
        if target is None:
            raise PolicyInputError(f"{label} contains an unrelated path: {raw_path}")
        expected = (
            target.source_relative if require == "source" else target.companion_relative
        )
        if relative.as_posix() != expected:
            raise PolicyInputError(
                f"{label} path must name a target {require}: {relative.as_posix()}"
            )
        allowed.add(expected)
    return allowed


def _file_digest(path: Path) -> str | None:
    try:
        return sha256_file(path)
    except (FileNotFoundError, IsADirectoryError, OSError):
        return None


def check_edit(
    repo_root: PathInput,
    paths: Iterable[PathInput],
    bootstrap_paths: Iterable[PathInput] = (),
    new_source_paths: Iterable[PathInput] = (),
    **unknown: object,
) -> PolicyResult:
    """Return a host-neutral allow/deny result for one file-edit operation."""

    if unknown:
        names = ", ".join(sorted(unknown))
        raise PolicyInputError(f"unknown policy argument(s): {names}")
    root = _repository_root(repo_root)
    bootstrap = _permission_paths(
        root,
        bootstrap_paths,
        label="bootstrap_paths",
        require="companion",
    )
    new_sources = _permission_paths(
        root,
        new_source_paths,
        label="new_source_paths",
        require="source",
    )

    entries: list[tuple[Target, str]] = []
    for raw_path in _path_values(paths, "paths"):
        _resolved, relative = _path_and_relative(root, raw_path)
        target = _target_from_relative(root, relative)
        if target is not None:
            role = "source" if relative.as_posix() == target.source_relative else "companion"
            entries.append((target, role))

    if not entries:
        return _result("allow", "No synchronized target documents are affected.")

    groups: dict[str, tuple[Target, set[str]]] = {}
    for target, role in entries:
        key = target.source_relative
        if key not in groups:
            groups[key] = (target, set())
        groups[key][1].add(role)

    affected_paths: list[str] = []
    expected_digests: dict[str, str] = {}
    messages: list[str] = []
    denied = False

    for target, roles in groups.values():
        source_relative = target.source_relative
        companion_relative = target.companion_relative
        source_digest = _file_digest(target.source_path)
        if source_digest is not None:
            expected_digests[companion_relative] = f"sha256:{source_digest}"

        if "source" in roles:
            affected_paths.extend((source_relative, companion_relative))
        else:
            affected_paths.append(companion_relative)

        if roles == {"source", "companion"}:
            denied = True
            messages.append(
                f"Cannot edit paired Markdown and HTML in one operation: "
                f"{source_relative} and {companion_relative}."
            )
            continue

        if source_digest is None:
            denied = True
            messages.append(
                f"Cannot authorize {companion_relative}; current Markdown source "
                f"{source_relative} is unavailable. Deletion and movement require "
                "the Git diff checker."
            )
            continue

        if roles == {"source"}:
            messages.append(
                f"Markdown changed; author {companion_relative} separately."
            )
            continue

        metadata = read_digest_metadata(target.companion_path)
        if metadata.is_valid:
            if metadata.digest == f"sha256:{source_digest}":
                denied = True
                messages.append(
                    f"HTML-only edit denied for {companion_relative}; its source "
                    "digest is already current."
                )
            else:
                messages.append(
                    f"HTML companion {companion_relative} may be updated with the "
                    f"current digest for {source_relative}."
                )
            continue

        if metadata.status is DigestStatus.MISSING:
            if companion_relative in bootstrap:
                messages.append(
                    f"Bootstrap authoring allowed for {companion_relative}; use "
                    f"sha256:{source_digest}."
                )
            elif source_relative in new_sources:
                messages.append(
                    f"First companion authoring allowed for {companion_relative} "
                    f"after creating {source_relative}."
                )
            else:
                denied = True
                messages.append(
                    f"HTML companion {companion_relative} has no source digest "
                    f"metadata; edit {source_relative} first or bootstrap it."
                )
        else:
            denied = True
            messages.append(
                f"HTML companion {companion_relative} has {metadata.status.value} "
                "source digest metadata; write a valid companion after the source "
                "edit."
            )

    # A pair is reported once even if a caller supplied duplicate paths.
    unique_paths = list(dict.fromkeys(affected_paths))
    return _result(
        "deny" if denied else "allow",
        " ".join(messages),
        unique_paths,
        expected_digests,
    )


# The explicit alias reads naturally for callers that deal in source metadata.
parse_source_digest = parse_digest_metadata


_HTML_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_FORBIDDEN_TAGS = {"script", "iframe", "frame", "object", "embed", "style"}
_MEDIA_TAGS = {"img", "audio", "video", "source", "track"}
_OUTLINE_TAGS = {"aside", "nav"}
_OUTLINE_EXCLUDED_TAGS = {"aside", "caption", "details", "nav"}
_SCOPE_VALUES = {"col", "colgroup", "row", "rowgroup"}
_CSP_REQUIRED = {
    "default-src": {"'none'"},
    "img-src": {"'self'", "data:"},
    "style-src": {"'self'"},
    "base-uri": {"'none'"},
    "form-action": {"'none'"},
    "frame-ancestors": {"'none'"},
}
_MD_FENCE_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_MD_FENCE_CLOSE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*$")
_MD_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_MD_TASK_RE = re.compile(r"^## Task (\d+):[ \t]*(.*)$")
_MD_REFERENCE_RE = re.compile(r"^ {0,3}\[[^\]]+\]:\s+\S+")
_MD_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_REFERENCE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\[[^\]]*\]")
_MD_AUTOLINK_RE = re.compile(r"<((?:https?://|mailto:)[^ >]+)>")
_MD_TOKEN_RE = re.compile(
    r"</?[A-Za-z][^>]*>|[\w]+(?:['’][\w]+)*", re.UNICODE
)
_LANGUAGE_WORDS = {
    "en": {
        "a",
        "an",
        "and",
        "are",
        "as",
        "because",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "was",
        "with",
    },
    "fr": {
        "au",
        "avec",
        "dans",
        "de",
        "des",
        "du",
        "et",
        "la",
        "le",
        "les",
        "pour",
        "que",
        "un",
        "une",
    },
    "de": {
        "als",
        "auf",
        "das",
        "der",
        "die",
        "ein",
        "eine",
        "mit",
        "und",
        "von",
        "zu",
    },
    "es": {
        "con",
        "de",
        "el",
        "en",
        "la",
        "las",
        "los",
        "para",
        "por",
        "que",
        "una",
        "un",
        "y",
    },
    "it": {
        "con",
        "da",
        "del",
        "di",
        "e",
        "gli",
        "il",
        "la",
        "le",
        "per",
        "una",
        "un",
    },
}


@dataclass
class HTMLNode:
    """One parsed HTML element and its ordered child/text content."""

    tag: str
    attrs: tuple[tuple[str, str | None], ...] = ()
    parent: HTMLNode | None = None
    children: list[HTMLNode] = field(default_factory=list)
    text_nodes: list[str] = field(default_factory=list)
    content: list[HTMLNode | str] = field(default_factory=list)


@dataclass(frozen=True)
class HTMLDocument:
    """The standard-library parse result retained for validation and callers."""

    root: HTMLNode
    nodes: tuple[HTMLNode, ...]
    errors: tuple[str, ...] = ()

    @property
    def headings(self) -> tuple[HTMLNode, ...]:
        return tuple(node for node in self.nodes if node.tag in {f"h{i}" for i in range(1, 7)})

    @property
    def fragments(self) -> tuple[str, ...]:
        return tuple(
            value
            for node in self.nodes
            for name, value in node.attrs
            if name == "id" and value
        )

    @property
    def landmarks(self) -> tuple[HTMLNode, ...]:
        return tuple(node for node in self.nodes if node.tag in {"header", "main", "aside", "nav"})


class _AuthoredHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLNode("#document")
        self.nodes: list[HTMLNode] = []
        self.stack: list[HTMLNode] = [self.root]
        self.errors: list[str] = []

    @property
    def current(self) -> HTMLNode:
        return self.stack[-1]

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], push: bool) -> None:
        raw_tag = self.get_starttag_text() or ""
        quote: str | None = None
        for character in raw_tag:
            if quote:
                if character == quote:
                    quote = None
            elif character in {"'", '"'}:
                quote = character
        if quote is not None:
            self.errors.append(f"unterminated attribute quote in <{tag}>")
        node = HTMLNode(tag.lower(), tuple((name.lower(), value) for name, value in attrs), self.current)
        self.current.children.append(node)
        self.current.content.append(node)
        self.nodes.append(node)
        if push and node.tag not in _HTML_VOID_TAGS:
            self.stack.append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _HTML_VOID_TAGS:
            self.errors.append(f"closing tag for void element <{normalized}>")
            return
        if len(self.stack) == 1:
            self.errors.append(f"unexpected closing tag </{normalized}>")
            return
        if self.stack[-1].tag != normalized:
            self.errors.append(f"unbalanced closing tag </{normalized}>")
            matching = next(
                (index for index in range(len(self.stack) - 1, 0, -1) if self.stack[index].tag == normalized),
                None,
            )
            if matching is None:
                return
            del self.stack[matching:]
            return
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        self.current.text_nodes.append(data)
        self.current.content.append(data)

    def handle_comment(self, data: str) -> None:
        return

    def handle_decl(self, decl: str) -> None:
        if decl.lower() != "doctype html":
            self.errors.append(f"unsupported declaration: {decl}")

    def unknown_decl(self, data: str) -> None:
        self.errors.append(f"unsupported declaration: {data}")

    def handle_pi(self, data: str) -> None:
        self.errors.append(f"processing instruction is not allowed: {data}")


def parse_html(html: str | bytes) -> HTMLDocument:
    """Parse authored HTML while retaining nodes, attributes, text, and errors."""

    if isinstance(html, bytes):
        try:
            html = html.decode("utf-8")
        except UnicodeDecodeError:
            root = HTMLNode("#document")
            return HTMLDocument(root, (), ("HTML is not valid UTF-8",))
    if not isinstance(html, str):
        raise TypeError("HTML must be text or UTF-8 bytes")
    parser = _AuthoredHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError) as exc:
        parser.errors.append(f"HTML parser error: {exc}")
    if len(parser.stack) != 1:
        parser.errors.append("unclosed HTML element")
    return HTMLDocument(parser.root, tuple(parser.nodes), tuple(parser.errors))


def _attrs(node: HTMLNode, name: str) -> list[str | None]:
    return [value for attr, value in node.attrs if attr == name]


def _attr(node: HTMLNode, name: str) -> str | None:
    values = _attrs(node, name)
    return values[0] if values else None


def _class_names(node: HTMLNode) -> set[str]:
    value = _attr(node, "class") or ""
    return set(value.split())


def _descendants(node: HTMLNode) -> Iterator[HTMLNode]:
    for child in node.children:
        yield child
        yield from _descendants(child)


def _node_text(node: HTMLNode) -> str:
    parts: list[str] = []
    for item in node.content:
        parts.append(item if isinstance(item, str) else _node_text(item))
    return "".join(parts)


def _ancestor(node: HTMLNode, tags: set[str]) -> HTMLNode | None:
    current = node.parent
    while current is not None:
        if current.tag in tags:
            return current
        current = current.parent
    return None


def _under(node: HTMLNode, ancestor: HTMLNode) -> bool:
    current = node.parent
    while current is not None:
        if current is ancestor:
            return True
        current = current.parent
    return False


def _normal_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def _markdown_inline_text(line: str) -> str:
    line = _MD_AUTOLINK_RE.sub(r"\1", line)
    raw_tags: list[str] = []

    def protect_raw_tag(match: re.Match[str]) -> str:
        raw_tags.append(match.group(0))
        return f"\x00raw{len(raw_tags) - 1}\x00"

    line = re.sub(r"</?[A-Za-z][^>]*>", protect_raw_tag, line)
    line = _MD_LINK_RE.sub(r"\1", line)
    line = _MD_REFERENCE_LINK_RE.sub(r"\1", line)
    line = re.sub(r"(?<!\w)\[([^\]]+)\]", r"\1", line)
    line = re.sub(r"\*\*|__|~~", "", line)
    line = re.sub(r"(?<!\w)[*_](?=\w)|(?<=\w)[*_](?!\w)", "", line)
    line = re.sub(r"\\([\\`*{}\[\]()#+.!_>~-])", r"\1", line)
    return re.sub(r"\x00raw(\d+)\x00", lambda match: raw_tags[int(match.group(1))], line)


def _markdown_visible_text(markdown: str, *, include_fenced_code: bool = True) -> str:
    fragments: list[str] = []
    fence_marker: str | None = None
    fence_length = 0
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip("\r\n")
        if fence_marker is not None:
            close = _MD_FENCE_CLOSE_RE.match(line)
            if close and close.group(2)[0] == fence_marker and len(close.group(2)) >= fence_length:
                fence_marker = None
                fence_length = 0
            elif include_fenced_code:
                fragments.append(line)
            continue
        opened = _MD_FENCE_OPEN_RE.match(line)
        if opened:
            fence = opened.group(2)
            if fence[0] == "`" and "`" in opened.group(3):
                opened = None
            else:
                fence_marker = fence[0]
                fence_length = len(fence)
                continue
        if _MD_REFERENCE_RE.match(line) or _MD_TABLE_SEPARATOR_RE.match(line):
            continue
        line = re.sub(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+", "", line)
        line = re.sub(r"^ {0,3}>[ \t]?", "", line)
        line = re.sub(r"^ {0,3}\[[ xX]\][ \t]+", "", line)
        line = re.sub(r"^ {0,3}#{1,6}[ \t]+", "", line)
        line = line.replace("|", " ") if "|" in line else line
        fragments.append(_markdown_inline_text(line))
    return "\n".join(fragments)


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _MD_TOKEN_RE.findall(text)]


def _main_visible_text(main: HTMLNode) -> str:
    parts: list[str] = []
    block_tags = {
        "article",
        "dd",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def visit(node: HTMLNode) -> None:
        if (
            node.tag in _OUTLINE_EXCLUDED_TAGS
            or "task-number" in _class_names(node)
            or "skip-link" in _class_names(node)
        ):
            return
        if node.tag in block_tags and parts and not parts[-1].endswith((" ", "\n", "\t")):
            parts.append(" ")
        for item in node.content:
            if isinstance(item, str):
                parts.append(item)
            else:
                visit(item)
        if node.tag in block_tags:
            parts.append(" ")

    visit(main)
    return "".join(parts)


def _source_headings(markdown: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    fence_marker: str | None = None
    fence_length = 0
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip("\r\n")
        if fence_marker is not None:
            close = _MD_FENCE_CLOSE_RE.match(line)
            if close and close.group(2)[0] == fence_marker and len(close.group(2)) >= fence_length:
                fence_marker = None
                fence_length = 0
            continue
        opened = _MD_FENCE_OPEN_RE.match(line)
        if opened:
            fence = opened.group(2)
            if not (fence[0] == "`" and "`" in opened.group(3)):
                fence_marker = fence[0]
                fence_length = len(fence)
                continue
        match = _MD_HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), _markdown_inline_text(match.group(2)).strip()))
    return headings


def _source_task_headings(markdown: str) -> list[tuple[int, str]]:
    return [
        (int(match.group(1)), match.group(2).strip())
        for level, title in _source_headings(markdown)
        if level == 2
        and (match := _MD_TASK_RE.match(f"## {title}"))
    ]


def _slugify(text: str, used: dict[str, int]) -> str:
    slug = re.sub(r"\s+", "-", text.strip())
    slug = re.sub(r"[^\w\-]", "", slug, flags=re.UNICODE)
    slug = slug.strip("-").lower() or "section"
    occurrence = used.get(slug, 0)
    used[slug] = occurrence + 1
    return slug if occurrence == 0 else f"{slug}-{occurrence}"


def _relative_resource(root: Path, html_path: Path, value: str) -> str | None:
    split = urlsplit(value)
    if split.scheme or split.netloc:
        return None
    decoded = unquote(split.path)
    if not decoded or "\\" in decoded:
        return None
    if decoded.startswith("/"):
        candidate = root / decoded.lstrip("/")
    else:
        candidate = html_path.parent / decoded
    try:
        return candidate.resolve(strict=False).relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def _language_from_source(markdown: str) -> str | None:
    prose = _markdown_visible_text(markdown, include_fenced_code=False)
    prose = re.sub(r"`[^`]*`", " ", prose)
    prose = re.sub(r"</?[A-Za-z][^>]*>", " ", prose)
    if re.search(r"[\u3040-\u30ff]", prose):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", prose):
        return "ko"
    if re.search(r"[\u0400-\u04ff]", prose):
        return "ru"
    if re.search(r"[\u0600-\u06ff]", prose):
        return "ar"
    if re.search(r"[\u0590-\u05ff]", prose):
        return "he"
    if re.search(r"[\u0370-\u03ff]", prose):
        return "el"
    words = {word.casefold() for word in re.findall(r"[A-Za-z]+", prose)}
    if not words:
        return None
    scores = {language: len(words & common) for language, common in _LANGUAGE_WORDS.items()}
    winner, score = max(scores.items(), key=lambda item: item[1])
    return winner if score else "en"


def _issue(code: str, message: str, source_relative: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": source_relative}


def _csp_directives(content: str) -> dict[str, set[str]]:
    directives: dict[str, set[str]] = {}
    for part in content.split(";"):
        values = part.split()
        if not values:
            continue
        name = values[0].casefold()
        directives.setdefault(name, set()).update(value.casefold() for value in values[1:])
    return directives


def _outline_name(node: HTMLNode, document: HTMLDocument) -> bool:
    label = _attr(node, "aria-label")
    if label and label.strip():
        return True
    labelled_by = (_attr(node, "aria-labelledby") or "").split()
    ids = set(document.fragments)
    return bool(labelled_by and set(labelled_by) <= ids)


def _validation_result(
    target: Target,
    violations: list[dict[str, str]],
    warnings: list[dict[str, str]],
    expected_digest: str | None,
) -> PolicyResult:
    paths = [target.source_relative, target.companion_relative]
    expected = {target.companion_relative: expected_digest} if expected_digest else {}
    if violations:
        message = f"HTML validation failed for {target.companion_relative}: " + " ".join(
            item["message"] for item in violations
        )
        decision = "deny"
    else:
        message = f"HTML companion {target.companion_relative} is valid."
        decision = "allow"
    return {
        "decision": decision,
        "message": message,
        "paths": paths,
        "expected_digests": expected,
        "violations": violations,
        "warnings": warnings,
    }


def validate_html(
    repo_root: PathInput,
    source_path: PathInput,
    companion_path: PathInput | None = None,
) -> PolicyResult:
    """Validate one authored HTML companion against its canonical Markdown source."""

    root = _repository_root(repo_root)
    target = _target_from_relative(root, _path_and_relative(root, source_path)[1])
    if target is None:
        raise PolicyInputError(f"path is not a Target document: {source_path}")
    if companion_path is not None:
        supplied_target = _target_from_relative(
            root, _path_and_relative(root, companion_path)[1]
        )
        if (
            supplied_target is None
            or supplied_target != target
            or supplied_target.companion_path != _path_and_relative(root, companion_path)[0]
        ):
            raise PolicyInputError("source and companion paths do not name one target pair")

    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    source_relative = target.source_relative
    expected_digest: str | None = None
    source_available = True
    try:
        source_bytes = target.source_path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, OSError):
        source_available = False
        violations.append(_issue("source-missing", f"Markdown source {source_relative} is unavailable.", source_relative))
        source_bytes = b""
    if source_available:
        expected_digest = f"sha256:{sha256_file(target.source_path)}"
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_text = ""
        violations.append(_issue("source-encoding", f"Markdown source {source_relative} is not UTF-8.", source_relative))

    try:
        html_bytes = target.companion_path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, OSError):
        violations.append(_issue("companion-missing", f"HTML companion {target.companion_relative} is unavailable.", source_relative))
        return _validation_result(target, violations, warnings, expected_digest)
    document = parse_html(html_bytes)
    for error in document.errors:
        violations.append(_issue("malformed-html", error, source_relative))

    html_nodes = [node for node in document.nodes if node.tag == "html"]
    if len(html_nodes) != 1:
        violations.append(_issue("html-element", "The companion must contain exactly one html element.", source_relative))
    html_node = html_nodes[0] if len(html_nodes) == 1 else None

    metadata = parse_digest_metadata(html_bytes)
    if not metadata.is_valid:
        violations.append(_issue("digest-metadata", f"Source digest metadata is {metadata.status.value}.", source_relative))
    elif metadata.digest != expected_digest:
        violations.append(_issue("digest-mismatch", f"Digest does not match the exact bytes of {source_relative}.", source_relative))

    if html_node is not None:
        lang = (_attr(html_node, "lang") or "").strip()
        if not lang or lang.casefold() == "und":
            violations.append(_issue("language", "html lang must name the dominant prose language, not und.", source_relative))
        elif not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", lang):
            violations.append(_issue("language", "html lang must be a language tag.", source_relative))
        else:
            dominant = _language_from_source(source_text)
            if dominant and lang.split("-", 1)[0].casefold() != dominant:
                violations.append(_issue("language", f"html lang {lang!r} does not match dominant prose language {dominant!r}.", source_relative))

    meta_charset = [node for node in document.nodes if node.tag == "meta" and _attr(node, "charset") is not None]
    if len(meta_charset) != 1 or (_attr(meta_charset[0], "charset") or "").casefold() != "utf-8":
        violations.append(_issue("charset", "Exactly one UTF-8 charset declaration is required.", source_relative))
    viewports = [
        node for node in document.nodes
        if node.tag == "meta" and (_attr(node, "name") or "").casefold() == "viewport"
    ]
    if len(viewports) != 1 or not (_attr(viewports[0], "content") or "").strip():
        violations.append(_issue("viewport", "Exactly one non-empty viewport declaration is required.", source_relative))
    titles = [node for node in document.nodes if node.tag == "title"]
    if len(titles) != 1 or not _node_text(titles[0]).strip():
        violations.append(_issue("title", "Exactly one non-empty title is required.", source_relative))

    csp_nodes = [
        node for node in document.nodes
        if node.tag == "meta" and (_attr(node, "http-equiv") or "").casefold() == "content-security-policy"
    ]
    if len(csp_nodes) != 1:
        violations.append(_issue("csp", "Exactly one restrictive Content-Security-Policy is required.", source_relative))
    else:
        directives = _csp_directives(_attr(csp_nodes[0], "content") or "")
        for name, expected in _CSP_REQUIRED.items():
            if directives.get(name) != expected:
                violations.append(_issue("csp", f"CSP directive {name} is not restrictive enough.", source_relative))
        forbidden_csp_values = {"*", "http:", "https:", "'unsafe-inline'", "'unsafe-eval'"}
        if any(value in forbidden_csp_values for values in directives.values() for value in values):
            violations.append(_issue("csp", "CSP contains a broad or executable source.", source_relative))

    stylesheet_links = [
        node for node in document.nodes
        if node.tag == "link" and "stylesheet" in {token.casefold() for token in (_attr(node, "rel") or "").split()}
    ]
    if len(stylesheet_links) != 1:
        violations.append(_issue("stylesheet-count", "Exactly one shared stylesheet link is required.", source_relative))
    else:
        href = _attr(stylesheet_links[0], "href") or ""
        relative = _relative_resource(root, target.companion_path, href)
        if relative != "docs/sdd/assets/sdd.css":
            violations.append(_issue("stylesheet-resource", "The stylesheet must resolve to docs/sdd/assets/sdd.css inside the repository.", source_relative))

    for node in document.nodes:
        for name, value in node.attrs:
            if name.startswith("on"):
                violations.append(_issue("event-attribute", f"Event attribute {name} is not allowed.", source_relative))
            if name == "style":
                violations.append(_issue("style-attribute", "Inline style attributes are not allowed.", source_relative))
            if name in {"srcdoc", "formaction"}:
                violations.append(_issue("executable-attribute", f"Attribute {name} is not allowed.", source_relative))
            if name in {"href", "src", "poster", "data"} and value:
                scheme = urlsplit(value).scheme.casefold()
                if scheme in {"javascript", "vbscript"} or value.casefold().startswith("data:text/html"):
                    violations.append(_issue("executable-resource", f"Executable resource {value!r} is not allowed.", source_relative))
        if node.tag in _FORBIDDEN_TAGS:
            violations.append(_issue("unsafe-tag", f"Tag <{node.tag}> is not allowed in authored HTML.", source_relative))
        if node.tag == "font":
            violations.append(_issue("external-font", "Font elements and external fonts are not allowed.", source_relative))
        if node.tag == "link" and (
            "font" in {token.casefold() for token in (_attr(node, "rel") or "").split()}
            or (_attr(node, "as") or "").casefold() == "font"
        ):
            violations.append(_issue("external-font", "External font resources are not allowed.", source_relative))
        if node.tag in _MEDIA_TAGS:
            for attr_name in ("src", "poster", "srcset"):
                value = _attr(node, attr_name)
                if not value:
                    continue
                values = value.split(",") if attr_name == "srcset" else [value]
                for resource in values:
                    resource_value = resource.strip().split()[0]
                    if resource_value.casefold().startswith("data:") and not resource_value.casefold().startswith("data:image/"):
                        violations.append(_issue("network-resource", f"Non-image data resource {resource_value!r} is not allowed.", source_relative))
                    elif _relative_resource(root, target.companion_path, resource_value) is None:
                        violations.append(_issue("network-resource", f"Network-dependent resource {resource_value!r} is not allowed.", source_relative))

    bodies = [node for node in document.nodes if node.tag == "body"]
    mains = [node for node in document.nodes if node.tag == "main"]
    headers = [node for node in document.nodes if node.tag == "header"]
    if len(bodies) != 1:
        violations.append(_issue("body", "Exactly one body element is required.", source_relative))
    if len(mains) != 1:
        violations.append(_issue("main", "Exactly one main element is required.", source_relative))
    main = mains[0] if len(mains) == 1 else None
    if len(headers) != 1:
        violations.append(_issue("document-header", "Exactly one document-kind header is required.", source_relative))
    else:
        kind_label = {"context": "glossary", "adr": "adr", "spec": "spec", "plan": "plan"}[target.kind]
        header_text = _node_text(headers[0]).casefold()
        header_kind = (_attr(headers[0], "data-document-kind") or "").casefold()
        if kind_label not in header_text and kind_label != header_kind:
            violations.append(_issue("document-header", f"Header must identify this document as {kind_label}.", source_relative))
    if main is not None:
        main_id = _attr(main, "id")
        tabindex = _attr(main, "tabindex")
        if not main_id:
            violations.append(_issue("main-target", "main must have a non-empty content target id.", source_relative))
        if tabindex is None or not re.fullmatch(r"-?[0-9]+", tabindex) or int(tabindex) > 0:
            violations.append(_issue("main-focus", "main must be programmatically focusable with tabindex -1 or lower.", source_relative))
        if bodies:
            first_content = next(
                (item for item in bodies[0].content if not isinstance(item, str) or item.strip()),
                None,
            )
            if (
                not isinstance(first_content, HTMLNode)
                or first_content.tag != "a"
                or (_attr(first_content, "href") or "") != f"#{main_id}"
            ):
                violations.append(_issue("skip-link", "The body must start with a skip link targeting main.", source_relative))
        skip_links = [
            node for node in document.nodes
            if node.tag == "a" and "skip-link" in _class_names(node)
        ]
        if not skip_links or not main_id or not any((_attr(node, "href") or "") == f"#{main_id}" for node in skip_links):
            violations.append(_issue("skip-link", "A skip link to main is required.", source_relative))

    if main is not None:
        html_headings = [
            node for node in _descendants(main)
            if node.tag in {f"h{i}" for i in range(1, 7)} and _ancestor(node, _OUTLINE_EXCLUDED_TAGS) is None
        ]
        source_headings = _source_headings(source_text)
        if len(html_headings) != len(source_headings):
            violations.append(_issue("heading-structure", "Heading count does not match the Markdown source.", source_relative))
        used: dict[str, int] = {}
        for index, (source_heading, html_heading) in enumerate(zip(source_headings, html_headings)):
            source_level, source_title = source_heading
            expected_id = _slugify(source_title, used)
            html_level = int(html_heading.tag[1])
            if html_level != source_level or _normal_text(_node_text(html_heading)) != _normal_text(source_title):
                violations.append(_issue("heading-structure", f"Heading {index + 1} does not preserve its Markdown level and text.", source_relative))
            if _attr(html_heading, "id") != expected_id:
                violations.append(_issue("heading-id", f"Heading {index + 1} must use stable id {expected_id!r}.", source_relative))
        if len(html_headings) != len(set(_attr(node, "id") for node in html_headings)):
            violations.append(_issue("heading-id", "Heading ids must be unique.", source_relative))
        if sum(1 for node in html_headings if node.tag == "h1") > 1:
            warnings.append(_issue("multiple-h1", "Multiple h1 headings are preserved from Markdown.", source_relative))
        previous_level = 0
        for node in html_headings:
            level = int(node.tag[1])
            if previous_level and level > previous_level + 1:
                warnings.append(_issue("skipped-heading-level", "Heading levels skip a rank; the source level was preserved.", source_relative))
            previous_level = level

        outlines = [node for node in document.nodes if node.tag in _OUTLINE_TAGS]
        outline_headings = [node for node in html_headings if node.tag in {"h2", "h3"}]
        if outline_headings:
            named_outlines = [node for node in outlines if _outline_name(node, document)]
            if not named_outlines:
                violations.append(_issue("outline-missing", "A named aside/nav outline is required for h2 or h3 headings.", source_relative))
            else:
                outline = named_outlines[0]
                if not any(
                    node.tag == "details" for node in _descendants(outline)
                ) and _ancestor(outline, {"details"}) is None:
                    violations.append(_issue("outline-details", "The outline must be exposed through native details.", source_relative))
                outline_ids = {
                    (_attr(node, "href") or "")[1:]
                    for node in _descendants(outline)
                    if node.tag == "a" and (_attr(node, "href") or "").startswith("#")
                }
                expected_outline_ids = {_attr(node, "id") for node in outline_headings}
                if not expected_outline_ids <= outline_ids:
                    violations.append(_issue("outline-links", "Every h2 and h3 heading must be reachable from the outline.", source_relative))
        else:
            for outline in outlines:
                if not _node_text(outline).strip():
                    violations.append(_issue("empty-outline", "Empty aside/nav elements are not allowed without h2 or h3 headings.", source_relative))

        ids = set(document.fragments)
        fragment_ids = list(document.fragments)
        if len(fragment_ids) != len(ids):
            violations.append(_issue("fragment-id", "Element ids must be unique.", source_relative))
        for node in document.nodes:
            if node.tag == "a":
                href = _attr(node, "href") or ""
                if href.startswith("#") and href[1:] not in ids:
                    violations.append(_issue("fragment-target", f"Fragment target {href!r} does not resolve.", source_relative))

        tables = [node for node in _descendants(main) if node.tag == "table"]
        for table in tables:
            captions = [node for node in _descendants(table) if node.tag == "caption"]
            if not captions or not _node_text(captions[0]).strip():
                violations.append(_issue("table-caption", "Every data table needs a non-empty caption.", source_relative))
            headers_in_table = [node for node in _descendants(table) if node.tag == "th"]
            if not headers_in_table or any((_attr(node, "scope") or "").casefold() not in _SCOPE_VALUES for node in headers_in_table):
                violations.append(_issue("table-header-scope", "Every table header cell needs a valid scope.", source_relative))

        if target.kind == "context":
            dls = [node for node in _descendants(main) if node.tag == "dl"]
            terms = [node for node in _descendants(main) if node.tag == "dt"]
            definitions = [node for node in _descendants(main) if node.tag == "dd"]
            if not dls or not terms or not definitions:
                violations.append(_issue("glossary-structure", "Glossaries must use dl with dt and dd entries.", source_relative))
            if "avoid" in _markdown_visible_text(source_text).casefold():
                avoid_text = [node for node in _descendants(main) if "avoid" in _node_text(node).casefold()]
                if not any(_ancestor(node, {"dd"}) is not None for node in avoid_text):
                    violations.append(_issue("glossary-avoid", "An _Avoid_ paragraph must remain inside its related dd.", source_relative))
        elif target.kind == "adr":
            if not any(node.tag == "article" and _under(node, main) for node in document.nodes):
                violations.append(_issue("adr-article", "ADRs must use a compact decision article.", source_relative))
        elif target.kind == "spec":
            for heading in html_headings:
                if heading.tag == "h2" and _ancestor(heading, {"section"}) is None:
                    violations.append(_issue("spec-section", "Spec h2 headings must be contained in semantic section blocks.", source_relative))
        elif target.kind == "plan":
            task_headings = _source_task_headings(source_text)
            task_articles = [
                node for node in document.nodes
                if node.tag == "article" and _under(node, main) and _attr(node, "data-task-number")
            ]
            numbers = {_attr(node, "data-task-number") for node in task_articles}
            for number, _title in task_headings:
                if str(number) not in numbers:
                    violations.append(_issue("plan-task-article", f"Plan task {number} must be an independent article.", source_relative))
            for node in task_articles:
                if not any(_under(heading, node) for heading in html_headings if heading.tag in {"h2", "h3"}):
                    violations.append(_issue("plan-task-article", "Each plan task article must contain its task heading.", source_relative))

        source_tokens = _tokens(_markdown_visible_text(source_text))
        html_tokens = _tokens(_main_visible_text(main))
        if source_tokens != html_tokens:
            index = next(
                (position for position, (expected, actual) in enumerate(zip(source_tokens, html_tokens)) if expected != actual),
                min(len(source_tokens), len(html_tokens)),
            )
            expected_fragment = source_tokens[index] if index < len(source_tokens) else "<end>"
            actual_fragment = html_tokens[index] if index < len(html_tokens) else "<end>"
            if expected_fragment in html_tokens[index + 1:]:
                detail = f"source fragment {expected_fragment!r} is reordered"
            else:
                detail = f"source fragment {expected_fragment!r} is missing or changed (found {actual_fragment!r})"
            violations.append(_issue("source-text", f"First source-text mismatch: {detail}.", source_relative))

    return _validation_result(target, violations, warnings, expected_digest)


# These names make the validator easy to consume from policy-oriented callers.
validate_companion = validate_html
validate_target = validate_html
validate_authored_html = validate_html
validate_document = validate_html
