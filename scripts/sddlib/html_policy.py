from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
from typing import TypeAlias


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
        resolved = candidate.resolve(strict=False)
        relative = resolved.relative_to(root)
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
