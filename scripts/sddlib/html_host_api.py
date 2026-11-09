"""Versioned stdin/stdout host API for candidate HTML validation.

The API is an in-memory boundary for hosts that author HTML candidates.  The
document root is the caller's current working directory.  Markdown, candidate
HTML, resources, and receipts are supplied as base64 bytes keyed by canonical
repository-relative paths, so a candidate can be validated as if it were at its
official path without writing any file.

The API deliberately stops at static validation and supplied-input digest
binding.  It does not create HTML, write files, bootstrap a companion, render,
assess meaning, call a model, or decide that a document may be published.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import threading
import time
from typing import IO, Any

from sddlib.html_policy import PolicyInputError, resolve_target, validate_html
from sddlib.html_units import (
    SCHEMA_VERSION,
    SEMANTIC_CONTRACT,
    STRICT_CONTRACT,
    UnitSchemaError,
    scan_markdown,
    strict_requirements,
    validate_receipt,
)


PROTOCOL_NAME = "sdd-html-host-api"
PROTOCOL_VERSION = 1
POLICY_VERSION = "sdd-html-policy-v1"
POLICY_VERSION_ALIASES = frozenset({POLICY_VERSION, "semantic-v1"})
POLICY_FILES = (
    "html_units.py",
    "html_semantic.py",
    "html_svg.py",
    "html_policy.py",
    "html_host_api.py",
)

MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_CANDIDATE_BYTES = 8 * 1024 * 1024
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 64 * 1024 * 1024
MAX_INPUTS = 256
MAX_PATHS = 1_024
DEFAULT_TIMEOUT_MS = 30_000
MAX_TIMEOUT_MS = 300_000
RECEIPT_DIRECTORY = "docs/sdd/html-evidence"
SHARED_CSS = "docs/sdd/assets/sdd.css"

OPERATIONS = ("capabilities", "discover", "source-units", "candidate-check")
STAGES = ("structural", "final")
_COMMON_FIELDS = frozenset({"version", "operation", "timeout_ms"})
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class HostAPIError(ValueError):
    """A machine-readable protocol or input failure."""

    exit_code = 2

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.details = dict(details or {})

    def as_error(self) -> dict[str, object]:
        error: dict[str, object] = {"code": self.code, "message": self.message}
        if self.path is not None:
            error["path"] = self.path
        if self.details:
            error["details"] = self.details
        return error


class HostAPITimeout(HostAPIError):
    """The request exceeded its supplied wall-clock budget."""


@dataclass(frozen=True)
class SuppliedInput:
    """One decoded in-memory input and its exact-byte digest."""

    path: str
    data: bytes
    digest: str
    size: int


def _root_path(root: str | os.PathLike[str] | None) -> Path:
    try:
        candidate = Path.cwd() if root is None else Path(root)
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HostAPIError("root-unavailable", f"document root cannot be resolved: {exc}") from exc
    if not resolved.is_dir():
        raise HostAPIError("root-unavailable", f"document root is not a directory: {resolved}")
    return resolved


def normalize_relative_path(root: Path, value: object, *, field: str = "path") -> str:
    """Return one canonical repository-relative POSIX path or fail explicitly."""

    if not isinstance(value, str):
        raise HostAPIError("path-invalid", f"{field} must be a string", details={"field": field})
    if not value:
        raise HostAPIError("path-invalid", f"{field} must not be empty", details={"field": field})
    if "\x00" in value or any(ord(character) < 0x20 for character in value):
        raise HostAPIError("path-invalid", f"{field} contains a control character", details={"field": field})
    if value.startswith("/") or value.startswith("\\") or _DRIVE_RE.match(value):
        raise HostAPIError("path-escape", f"{field} must be repository-relative, not absolute", details={"field": field})
    if "\\" in value:
        if ".." in value.split("\\"):
            raise HostAPIError("path-escape", f"{field} must not contain '..'", details={"field": field})
        raise HostAPIError("path-invalid", f"{field} must use forward slashes", details={"field": field})
    parts = value.split("/")
    if any(part == "" for part in parts):
        raise HostAPIError("path-invalid", f"{field} must not contain empty path segments", details={"field": field})
    if ".." in parts:
        raise HostAPIError("path-escape", f"{field} must not contain '..'", details={"field": field})
    if "." in parts:
        raise HostAPIError("path-invalid", f"{field} must not contain '.' segments", details={"field": field})
    try:
        resolved = (root / value).resolve(strict=False)
        resolved.relative_to(root)
    except ValueError as exc:
        raise HostAPIError(
            "path-escape",
            f"{field} resolves outside the document root",
            details={"field": field},
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise HostAPIError("path-invalid", f"{field} cannot be resolved: {exc}", details={"field": field}) from exc
    return value


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _encode_limit(limit: int) -> int:
    return ((limit + 2) // 3) * 4


def _decode_inputs(root: Path, value: object) -> dict[str, SuppliedInput]:
    if value is None:
        raise HostAPIError("missing-field", "inputs is required")
    if not isinstance(value, dict):
        raise HostAPIError("invalid-request", "inputs must be a JSON object keyed by relative path")
    if len(value) > MAX_INPUTS:
        raise HostAPIError(
            "too-many-inputs",
            f"inputs contains {len(value)} entries; the limit is {MAX_INPUTS}",
            details={"limit": MAX_INPUTS, "count": len(value)},
        )

    inputs: dict[str, SuppliedInput] = {}
    resolved_seen: dict[str, str] = {}
    total = 0
    for raw_path, encoded in value.items():
        path = normalize_relative_path(root, raw_path, field="inputs key")
        if path in inputs:
            raise HostAPIError("duplicate-input", f"inputs contains duplicate path {path!r}", path=path)
        resolved_path = str((root / path).resolve(strict=False))
        if resolved_path in resolved_seen:
            raise HostAPIError(
                "duplicate-input",
                f"inputs paths {resolved_seen[resolved_path]!r} and {path!r} resolve to the same file",
                path=path,
            )
        resolved_seen[resolved_path] = path
        if not isinstance(encoded, str):
            raise HostAPIError(
                "invalid-base64",
                f"input {path!r} must be a base64 string",
                path=path,
            )
        compact = "".join(encoded.split())
        if len(compact) > _encode_limit(MAX_INPUT_BYTES):
            raise HostAPIError(
                "input-too-large",
                f"input {path!r} exceeds the {MAX_INPUT_BYTES}-byte limit",
                path=path,
                details={"limit": MAX_INPUT_BYTES},
            )
        try:
            data = base64.b64decode(compact, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HostAPIError(
                "invalid-base64",
                f"input {path!r} is not valid base64: {exc}",
                path=path,
            ) from exc
        if len(data) > MAX_INPUT_BYTES:
            raise HostAPIError(
                "input-too-large",
                f"input {path!r} is {len(data)} bytes; the per-input limit is {MAX_INPUT_BYTES}",
                path=path,
                details={"limit": MAX_INPUT_BYTES, "bytes": len(data)},
            )
        total += len(data)
        if total > MAX_TOTAL_INPUT_BYTES:
            raise HostAPIError(
                "input-too-large",
                f"inputs total more than {MAX_TOTAL_INPUT_BYTES} bytes",
                details={"limit": MAX_TOTAL_INPUT_BYTES, "bytes": total},
            )
        inputs[path] = SuppliedInput(path, data, _digest_bytes(data), len(data))
    return inputs


def _utf8(data: bytes, path: str, *, role: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HostAPIError(
            "invalid-encoding",
            f"{role} {path} is not valid UTF-8",
            path=path,
            details={"role": role, "error": str(exc)},
        ) from exc


def _check_fields(payload: Mapping[str, object], allowed: set[str] | frozenset[str]) -> None:
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise HostAPIError(
            "unknown-field",
            "request contains unknown field(s): " + ", ".join(unknown),
            details={"fields": unknown},
        )


def _timeout_value(payload: Mapping[str, object]) -> int:
    value = payload.get("timeout_ms", DEFAULT_TIMEOUT_MS)
    if type(value) is not int or value < 0 or value > MAX_TIMEOUT_MS:
        raise HostAPIError(
            "invalid-timeout",
            f"timeout_ms must be an integer from 0 to {MAX_TIMEOUT_MS}",
            details={"value": value, "maximum": MAX_TIMEOUT_MS},
        )
    return value


@contextmanager
def _deadline(timeout_ms: int):
    if timeout_ms <= 0:
        raise HostAPITimeout(
            "timeout",
            f"request timeout of {timeout_ms} ms is already expired",
            details={"timeout_ms": timeout_ms},
        )

    started = time.monotonic()
    previous_handler: Any = None
    timer_installed = False
    if threading.current_thread() is threading.main_thread() and hasattr(signal, "setitimer"):
        previous_handler = signal.getsignal(signal.SIGALRM)

        def _interrupt(signum: int, frame: Any) -> None:
            raise HostAPITimeout(
                "timeout",
                f"request exceeded its {timeout_ms} ms timeout",
                details={"timeout_ms": timeout_ms},
            )

        signal.signal(signal.SIGALRM, _interrupt)
        signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)
        timer_installed = True
    try:
        yield started
    finally:
        if timer_installed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    if not timer_installed and (time.monotonic() - started) * 1000.0 > timeout_ms:
        raise HostAPITimeout(
            "timeout",
            f"request exceeded its {timeout_ms} ms timeout",
            details={"timeout_ms": timeout_ms},
        )


def _violation(code: str, message: str, path: str) -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def _policy_identity() -> dict[str, object]:
    identity = policy_identity()
    return {
        "version": identity["version"],
        "digest": identity["digest"],
        "files": list(identity["files"]),
    }


@lru_cache(maxsize=1)
def policy_identity() -> dict[str, object]:
    """Return the canonical policy version and fingerprint.

    The fingerprint covers the validator modules that define static policy.
    It is not a signature and does not authenticate a checkout.
    """

    directory = Path(__file__).resolve().parent
    hasher = hashlib.sha256()
    for name in POLICY_FILES:
        try:
            data = (directory / name).read_bytes()
        except OSError as exc:
            raise HostAPIError(
                "policy-unavailable",
                f"cannot read policy module {name}: {exc}",
            ) from exc
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(len(data)).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(data)
    return {
        "version": POLICY_VERSION,
        "digest": "sha256:" + hasher.hexdigest(),
        "files": list(POLICY_FILES),
    }


def _input_report(
    inputs: Mapping[str, SuppliedInput], roles: Mapping[str, str]
) -> list[dict[str, object]]:
    return [
        {
            "path": item.path,
            "digest": item.digest,
            "bytes": item.size,
            "role": roles.get(item.path, "resource"),
        }
        for item in sorted(inputs.values(), key=lambda supplied: supplied.path)
    ]


def _input_digests(inputs: Mapping[str, SuppliedInput]) -> dict[str, str]:
    return {item.path: item.digest for item in sorted(inputs.values(), key=lambda supplied: supplied.path)}


def _capabilities(root: Path, payload: Mapping[str, object]) -> dict[str, object]:
    _check_fields(payload, _COMMON_FIELDS)
    return {
        "protocol": {"name": PROTOCOL_NAME, "version": PROTOCOL_VERSION},
        "operations": list(OPERATIONS),
        "contracts": [STRICT_CONTRACT, SEMANTIC_CONTRACT],
        "stages": {
            "structural": {
                "final": False,
                "final_binding": False,
                "receipt": "not-accepted",
                "message": "Structural static checks only; this stage is never a final pass.",
            },
            "final": {
                "final": True,
                "final_binding": True,
                "receipt": "required",
                "message": "Static checks plus receipt and supplied-input digest binding.",
            },
        },
        "limits": {
            "source_bytes": MAX_SOURCE_BYTES,
            "candidate_html_bytes": MAX_CANDIDATE_BYTES,
            "input_bytes": MAX_INPUT_BYTES,
            "total_input_bytes": MAX_TOTAL_INPUT_BYTES,
            "inputs": MAX_INPUTS,
            "paths": MAX_PATHS,
            "timeout_ms_default": DEFAULT_TIMEOUT_MS,
            "timeout_ms_max": MAX_TIMEOUT_MS,
        },
        "bootstrap": {"implicit": False, "operation": "html-docs bootstrap"},
        "writes": {"files": False, "html": False},
        "receipt": {
            "directory": RECEIPT_DIRECTORY,
            "path": "caller-supplied",
            "derived": False,
            "final_required": True,
        },
        "policy": {
            **_policy_identity(),
            "accepted_versions": sorted(POLICY_VERSION_ALIASES),
        },
        "assurance": "static-only",
        "limitations": [
            "The API performs static checks and in-memory digest binding only.",
            "It does not render, assess meaning, call a model, create HTML, or write files.",
            "It does not replace an H2 evaluation, publication, Git, or CI decision.",
        ],
    }


def _discover(root: Path, payload: Mapping[str, object]) -> dict[str, object]:
    _check_fields(payload, _COMMON_FIELDS | {"paths"})
    paths = payload.get("paths")
    if paths is None:
        raise HostAPIError("missing-field", "paths is required for discover")
    if not isinstance(paths, list):
        raise HostAPIError("invalid-request", "paths must be a JSON array")
    if len(paths) > MAX_PATHS:
        raise HostAPIError(
            "too-many-paths",
            f"paths contains {len(paths)} entries; the limit is {MAX_PATHS}",
            details={"limit": MAX_PATHS},
        )
    if not paths:
        raise HostAPIError("invalid-request", "paths must not be empty")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = normalize_relative_path(root, raw_path, field="paths[]")
        if path in seen:
            continue
        seen.add(path)
        normalized.append(path)

    targets: list[dict[str, object]] = []
    by_source: dict[str, dict[str, object]] = {}
    unrelated: list[str] = []
    for path in normalized:
        try:
            target = resolve_target(root, path)
        except (PolicyInputError, OSError, RuntimeError) as exc:
            raise HostAPIError("path-invalid", f"cannot resolve {path!r}: {exc}", path=path) from exc
        if target is None:
            unrelated.append(path)
            continue
        entry = by_source.get(target.source_relative)
        if entry is None:
            entry = {
                "source": target.source_relative,
                "html": target.companion_relative,
                "kind": target.kind,
                "input_paths": [],
            }
            by_source[target.source_relative] = entry
            targets.append(entry)
        cast_list = entry["input_paths"]
        cast_list.append(path)  # type: ignore[union-attr]
    return {
        "targets": targets,
        "unrelated": unrelated,
        "policy": _policy_identity(),
    }


def _source_units(root: Path, payload: Mapping[str, object]) -> dict[str, object]:
    _check_fields(payload, _COMMON_FIELDS | {"path", "inputs"})
    raw_path = payload.get("path")
    if raw_path is None:
        raise HostAPIError("missing-field", "path is required for source-units")
    path = normalize_relative_path(root, raw_path, field="path")
    inputs = _decode_inputs(root, payload.get("inputs"))
    try:
        target = resolve_target(root, path)
    except (PolicyInputError, OSError, RuntimeError) as exc:
        raise HostAPIError("path-invalid", f"cannot resolve {path!r}: {exc}", path=path) from exc
    if target is None:
        raise HostAPIError("not-target", f"{path!r} is not a Target document", path=path)

    source_relative = target.source_relative
    source_input = inputs.get(source_relative)
    if source_input is None:
        raise HostAPIError(
            "missing-input",
            f"source-units requires the exact source bytes for {source_relative}",
            path=source_relative,
            details={"role": "source"},
        )
    if source_input.size > MAX_SOURCE_BYTES:
        raise HostAPIError(
            "input-too-large",
            f"Markdown source {source_relative} is {source_input.size} bytes; the limit is {MAX_SOURCE_BYTES}",
            path=source_relative,
            details={"role": "source", "limit": MAX_SOURCE_BYTES, "bytes": source_input.size},
        )
    _utf8(source_input.data, source_relative, role="source")
    try:
        scan = scan_markdown(source_input.data)
        index = scan.to_index(source_relative)
        strict = strict_requirements(scan)
    except (ValueError, TypeError) as exc:
        raise HostAPIError("invalid-encoding", f"cannot scan {source_relative}: {exc}", path=source_relative) from exc

    status = index["status"]
    return {
        "path": source_relative,
        "target": {
            "source": source_relative,
            "html": target.companion_relative,
            "kind": target.kind,
        },
        "schema": index["schema"],
        "schema_version": index["version"],
        "contract": index["contract"],
        "source": index["source"],
        "status": status,
        "units": index["units"],
        "unsupported": index["unsupported"],
        "strict": strict,
        "coverage": {
            "status": status,
            "complete": status == "complete",
            "unit_count": len(index["units"]),  # type: ignore[arg-type]
            "unsupported_count": len(index["unsupported"]),  # type: ignore[arg-type]
        },
        "assurance": "lossless-byte-scan",
        "limitations": [
            "Source units cover the exact Markdown bytes only.",
            "This operation does not assess semantic preservation or any HTML candidate.",
        ],
        "inputs": _input_report(inputs, {source_relative: "source"}),
        "input_digests": _input_digests(inputs),
        "policy": _policy_identity(),
    }


def _receipt_path(root: Path, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise HostAPIError("invalid-receipt-path", "receipt must be a non-empty relative path")
    path = normalize_relative_path(root, value, field="receipt")
    if not path.startswith(RECEIPT_DIRECTORY + "/") or not path.endswith(".json"):
        raise HostAPIError(
            "invalid-receipt-path",
            f"receipt must be a .json path under {RECEIPT_DIRECTORY}/",
            path=path,
        )
    return path


def _bind_fingerprint(
    entry: Mapping[str, object],
    *,
    root: Path,
    inputs: Mapping[str, SuppliedInput],
    role: str,
    source_relative: str,
    violations: list[dict[str, str]],
) -> dict[str, object]:
    raw_path = entry.get("path")
    path = normalize_relative_path(root, raw_path, field=f"receipt.inputs.{role}.path")
    digest = entry.get("digest")
    supplied = inputs.get(path)
    if supplied is None:
        raise HostAPIError(
            "missing-input",
            f"receipt references {role} {path}, but its bytes were not supplied",
            path=path,
            details={"role": role},
        )
    matched = supplied.digest == digest
    if not matched:
        violations.append(
            _violation(
                f"receipt-{role}-digest",
                f"Receipt {role} digest for {path} does not match the supplied bytes.",
                source_relative,
            )
        )
    return {"path": path, "digest": digest, "supplied_digest": supplied.digest, "match": matched}


def _bind_receipt(
    receipt: Mapping[str, object],
    *,
    root: Path,
    inputs: Mapping[str, SuppliedInput],
    source_relative: str,
    html_relative: str,
    source_input: SuppliedInput,
    html_input: SuppliedInput,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    violations: list[dict[str, str]] = []

    source = receipt["source"]
    html = receipt["html"]
    if source["path"] != source_relative:
        violations.append(
            _violation(
                "receipt-source-path",
                f"Receipt source path {source['path']!r} does not match {source_relative!r}.",
                source_relative,
            )
        )
    if source["digest"] != source_input.digest:
        violations.append(
            _violation(
                "receipt-source-digest",
                "Receipt source digest does not match the supplied Markdown bytes.",
                source_relative,
            )
        )
    if html["path"] != html_relative:
        violations.append(
            _violation(
                "receipt-html-path",
                f"Receipt HTML path {html['path']!r} does not match {html_relative!r}.",
                source_relative,
            )
        )
    if html["digest"] != html_input.digest:
        violations.append(
            _violation(
                "receipt-html-digest",
                "Receipt HTML digest does not match the supplied candidate bytes.",
                source_relative,
            )
        )

    receipt_inputs = receipt["inputs"]
    css = [
        _bind_fingerprint(
            entry,  # type: ignore[arg-type]
            root=root,
            inputs=inputs,
            role="css",
            source_relative=source_relative,
            violations=violations,
        )
        for entry in receipt_inputs["css"]  # type: ignore[union-attr]
    ]
    resources = [
        _bind_fingerprint(
            entry,  # type: ignore[arg-type]
            root=root,
            inputs=inputs,
            role="resource",
            source_relative=source_relative,
            violations=violations,
        )
        for entry in receipt_inputs["resources"]  # type: ignore[union-attr]
    ]
    if SHARED_CSS not in {entry["path"] for entry in css}:
        violations.append(
            _violation(
                "receipt-css-missing",
                f"Receipt does not fingerprint the shared stylesheet {SHARED_CSS}.",
                source_relative,
            )
        )

    policy = receipt_inputs["policy"]  # type: ignore[index]
    identity = policy_identity()
    version_ok = policy["version"] in POLICY_VERSION_ALIASES  # type: ignore[index]
    if not version_ok:
        violations.append(
            _violation(
                "receipt-policy-version",
                f"Receipt policy version {policy['version']!r} does not match {identity['version']!r}.",  # type: ignore[index]
                source_relative,
            )
        )
    digest_ok = policy["digest"] == identity["digest"]  # type: ignore[index]
    if not digest_ok:
        violations.append(
            _violation(
                "receipt-policy-digest",
                "Receipt policy digest does not match this policy implementation.",
                source_relative,
            )
        )

    verification = receipt["verification"]
    if verification["result"] != "pass":  # type: ignore[index]
        violations.append(
            _violation(
                "receipt-verification",
                "Receipt verification result is not pass.",
                source_relative,
            )
        )
    checks: dict[str, object] = {}
    for check in verification["checks"]:  # type: ignore[index]
        checks[check["name"]] = check["decision"]  # type: ignore[index]
        if check["decision"] != "pass":  # type: ignore[index]
            violations.append(
                _violation(
                    "receipt-check",
                    f"Receipt verification check {check['name']!r} is {check['decision']!r}, not pass.",  # type: ignore[index]
                    source_relative,
                )
            )

    conditions: dict[str, object] = {}
    for condition in receipt["conditions"]:  # type: ignore[index]
        conditions[condition["id"]] = condition["decision"]  # type: ignore[index]
        if condition["decision"] != "met":  # type: ignore[index]
            violations.append(
                _violation(
                    "receipt-condition",
                    f"Receipt condition {condition['id']!r} is {condition['decision']!r}, not met.",  # type: ignore[index]
                    source_relative,
                )
            )

    return violations, {
        "source": {"path": source["path"], "digest": source["digest"], "match": source["digest"] == source_input.digest},
        "html": {"path": html["path"], "digest": html["digest"], "match": html["digest"] == html_input.digest},
        "css": css,
        "resources": resources,
        "policy": {
            "version": policy["version"],  # type: ignore[index]
            "digest": policy["digest"],  # type: ignore[index]
            "expected_version": identity["version"],
            "accepted_versions": sorted(POLICY_VERSION_ALIASES),
            "expected_digest": identity["digest"],
            "match": version_ok and digest_ok,
        },
        "verification": {"result": verification["result"], "checks": checks},  # type: ignore[index]
        "conditions": conditions,
        "bound": not violations,
    }


def _parse_receipt(text: str, path: str) -> dict[str, object]:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HostAPIError(
            "receipt-invalid-json",
            f"receipt {path} is not valid JSON: {exc}",
            path=path,
        ) from exc
    if not isinstance(value, dict):
        raise HostAPIError("receipt-invalid-json", f"receipt {path} must be a JSON object", path=path)
    try:
        return validate_receipt(value)
    except UnitSchemaError as exc:
        code = "receipt-schema"
        if exc.path in {"version", "schema", "contract"}:
            code = "unsupported-version" if exc.path == "version" else "unsupported-schema"
        raise HostAPIError(
            code,
            f"receipt {path} does not match schema version {SCHEMA_VERSION}: {exc}",
            path=path,
            details={"field": exc.path, "reason": exc.message},
        ) from exc


def _candidate_check(root: Path, payload: Mapping[str, object]) -> dict[str, object]:
    _check_fields(payload, _COMMON_FIELDS | {"path", "stage", "inputs", "receipt"})
    raw_path = payload.get("path")
    if raw_path is None:
        raise HostAPIError("missing-field", "path is required for candidate-check")
    path = normalize_relative_path(root, raw_path, field="path")
    stage = payload.get("stage")
    if stage not in STAGES:
        raise HostAPIError(
            "invalid-stage",
            "stage must be 'structural' or 'final'",
            details={"value": stage},
        )
    inputs = _decode_inputs(root, payload.get("inputs"))
    try:
        target = resolve_target(root, path)
    except (PolicyInputError, OSError, RuntimeError) as exc:
        raise HostAPIError("path-invalid", f"cannot resolve {path!r}: {exc}", path=path) from exc
    if target is None:
        raise HostAPIError("not-target", f"{path!r} is not a Target document", path=path)

    source_relative = target.source_relative
    html_relative = target.companion_relative
    source_input = inputs.get(source_relative)
    if source_input is None:
        raise HostAPIError(
            "missing-input",
            f"candidate-check requires the exact source bytes for {source_relative}",
            path=source_relative,
            details={"role": "source"},
        )
    html_input = inputs.get(html_relative)
    if html_input is None:
        raise HostAPIError(
            "missing-input",
            f"candidate-check requires the exact candidate bytes for {html_relative}",
            path=html_relative,
            details={"role": "candidate"},
        )
    if source_input.size > MAX_SOURCE_BYTES:
        raise HostAPIError(
            "input-too-large",
            f"Markdown source {source_relative} is {source_input.size} bytes; the limit is {MAX_SOURCE_BYTES}",
            path=source_relative,
            details={"role": "source", "limit": MAX_SOURCE_BYTES, "bytes": source_input.size},
        )
    if html_input.size > MAX_CANDIDATE_BYTES:
        raise HostAPIError(
            "input-too-large",
            f"Candidate HTML {html_relative} is {html_input.size} bytes; the limit is {MAX_CANDIDATE_BYTES}",
            path=html_relative,
            details={"role": "candidate", "limit": MAX_CANDIDATE_BYTES, "bytes": html_input.size},
        )
    _utf8(source_input.data, source_relative, role="source")
    _utf8(html_input.data, html_relative, role="candidate")

    receipt_path: str | None = None
    raw_receipt = payload.get("receipt")
    if raw_receipt is not None:
        receipt_path = _receipt_path(root, raw_receipt)
    if stage == "structural":
        if receipt_path is not None:
            raise HostAPIError(
                "receipt-not-allowed",
                "structural stage does not accept a receipt; use stage 'final' for receipt binding",
                path=receipt_path,
            )
    else:
        if receipt_path is None:
            raise HostAPIError(
                "missing-input",
                "final stage requires a receipt path and its supplied bytes",
                details={"role": "receipt"},
            )
        if receipt_path not in inputs:
            raise HostAPIError(
                "missing-input",
                f"final stage requires the supplied bytes for receipt {receipt_path}",
                path=receipt_path,
                details={"role": "receipt"},
            )

    try:
        static = validate_html(
            root,
            source_relative,
            html_relative,
            file_contents={item.path: item.data for item in inputs.values()},
        )
    except PolicyInputError as exc:
        raise HostAPIError("validation-input", f"static validation input failed: {exc}", path=path) from exc

    static_violations = list(static.get("violations", []))  # type: ignore[arg-type]
    binding_violations: list[dict[str, str]] = []
    receipt_summary: dict[str, object] | None = None
    roles = {source_relative: "source", html_relative: "candidate"}
    if receipt_path is not None:
        roles[receipt_path] = "receipt"

    if stage == "final":
        if static.get("contract") != SEMANTIC_CONTRACT:
            binding_violations.append(
                _violation(
                    "receipt-contract",
                    f"Final receipt binding requires a {SEMANTIC_CONTRACT} companion, not {static.get('contract')!r}.",
                    source_relative,
                )
            )
        receipt_input = inputs[receipt_path]  # type: ignore[index]
        receipt_text = _utf8(receipt_input.data, receipt_path, role="receipt")  # type: ignore[arg-type]
        receipt = _parse_receipt(receipt_text, receipt_path)  # type: ignore[arg-type]
        bound_violations, binding = _bind_receipt(
            receipt,
            root=root,
            inputs=inputs,
            source_relative=source_relative,
            html_relative=html_relative,
            source_input=source_input,
            html_input=html_input,
        )
        binding_violations.extend(bound_violations)
        binding["bound"] = not binding_violations
        receipt_summary = {
            "path": receipt_path,
            "digest": receipt_input.digest,
            "schema": receipt["schema"],
            "version": receipt["version"],
            "contract": receipt["contract"],
            "binding": binding,
        }

    violations = static_violations + binding_violations
    decision = "deny" if violations or static.get("decision") != "allow" else "allow"

    if stage == "structural":
        if decision == "allow":
            message = (
                f"Structural static validation passed for {html_relative}; this is not a "
                "final pass. No receipt or final binding was checked, and semantic "
                "preservation and rendering are not verified."
            )
        else:
            message = (
                f"Structural static validation failed for {html_relative}; no final "
                "binding was checked. " + str(static.get("message", ""))
            )
    else:
        if decision == "allow":
            message = (
                f"Final in-memory validation passed for {html_relative}: static checks and "
                "receipt/supplied-input digest binding are bound. Semantic preservation, "
                "rendering, Git state, and publication are not verified."
            )
        else:
            details = " ".join(item["message"] for item in violations)
            message = f"Final in-memory validation failed for {html_relative}. {details}".strip()

    result: dict[str, object] = {
        "stage": stage,
        "final": stage == "final",
        "final_binding": stage == "final",
        "publication": "not-performed",
        "target": {
            "source": source_relative,
            "html": html_relative,
            "kind": target.kind,
        },
        "decision": decision,
        "message": message,
        "paths": static.get("paths", [source_relative, html_relative]),
        "expected_digests": static.get("expected_digests", {}),
        "violations": violations,
        "warnings": static.get("warnings", []),
        "contract": static.get("contract"),
        "assurance": static.get("assurance", "static-only"),
        "digests": {
            "source": source_input.digest,
            "candidate": html_input.digest,
            "receipt": inputs[receipt_path].digest if receipt_path is not None else None,
        },
        "receipt": receipt_summary,
        "inputs": _input_report(inputs, roles),
        "input_digests": _input_digests(inputs),
        "policy": _policy_identity(),
        "limitations": [
            "Static checks and supplied-input digest binding only.",
            "Semantic preservation, rendering, model assessment, Git state, and CI state are not verified.",
            "No file was written and no HTML was created or bootstrapped.",
        ],
    }
    if stage == "structural":
        result["limitations"].insert(  # type: ignore[union-attr]
            0,
            "The structural stage has no receipt and no final binding; it is not a final pass.",
        )
    return result


_OPERATIONS = {
    "capabilities": _capabilities,
    "discover": _discover,
    "source-units": _source_units,
    "candidate-check": _candidate_check,
}


def _success(operation: str, root: Path, result: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "version": PROTOCOL_VERSION,
        "operation": operation,
        "root": str(root),
        "result": result,
    }


def _error_envelope(
    operation: object,
    error: HostAPIError,
    root: Path | None,
) -> dict[str, object]:
    return {
        "ok": False,
        "version": PROTOCOL_VERSION,
        "operation": operation if isinstance(operation, str) else None,
        "root": str(root) if root is not None else str(Path.cwd()),
        "error": error.as_error(),
    }


def dispatch(
    payload: object,
    *,
    root: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Run one already-decoded version 1 request."""

    root_path = _root_path(root)
    if not isinstance(payload, dict):
        raise HostAPIError("invalid-request", "host API request must be a JSON object")

    version = payload.get("version")
    if type(version) is not int or version != PROTOCOL_VERSION:
        raise HostAPIError(
            "unsupported-version",
            f"host API request version must be {PROTOCOL_VERSION}",
            details={"expected": PROTOCOL_VERSION, "received": version},
        )
    operation = payload.get("operation")
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise HostAPIError(
            "unknown-operation",
            "operation must be one of: " + ", ".join(OPERATIONS),
            details={"received": operation},
        )
    timeout_ms = _timeout_value(payload)
    with _deadline(timeout_ms) as started:
        result = _OPERATIONS[operation](root_path, payload)
        elapsed_ms = round((time.monotonic() - started) * 1000.0, 3)
    result["timing"] = {"timeout_ms": timeout_ms, "elapsed_ms": elapsed_ms}
    return _success(operation, root_path, result)


def _operation_hint(payload: object) -> object:
    if isinstance(payload, dict):
        return payload.get("operation")
    return None


def cli_main(
    argv: list[str] | None = None,
    *,
    root: str | os.PathLike[str] | None = None,
    stdin: IO[Any] | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
) -> int:
    """Run the stdin/stdout protocol and return the process exit code."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    input_stream = sys.stdin.buffer if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    error_stream = sys.stderr if stderr is None else stderr
    operation: object = None
    root_path: Path | None = None

    try:
        if arguments:
            raise HostAPIError("invalid-request", "host-api does not accept command-line arguments")
        try:
            root_path = _root_path(root)
        except HostAPIError:
            raise
        try:
            raw = input_stream.read()  # type: ignore[union-attr]
        except OSError as exc:
            raise HostAPIError("invalid-request", f"cannot read host API request: {exc}") from exc
        if isinstance(raw, str):
            try:
                raw_bytes = raw.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise HostAPIError(
                    "invalid-encoding",
                    f"host API request is not valid UTF-8: {exc}",
                ) from exc
        elif isinstance(raw, (bytes, bytearray)):
            raw_bytes = bytes(raw)
        else:
            raise HostAPIError("invalid-request", "host API request must be text or bytes")
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HostAPIError("invalid-encoding", f"host API request is not valid UTF-8: {exc}") from exc
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HostAPIError("invalid-json", f"host API request must be valid JSON: {exc}") from exc
        operation = _operation_hint(payload)
        envelope = dispatch(payload, root=root_path)
        code = 0
        if (
            envelope.get("operation") == "candidate-check"
            and isinstance(envelope.get("result"), dict)
            and envelope["result"].get("decision") != "allow"  # type: ignore[union-attr]
        ):
            code = 1
    except HostAPIError as exc:
        envelope = _error_envelope(operation, exc, root_path)
        code = exc.exit_code
    except Exception as exc:  # noqa: BLE001 - CLI protocol boundary
        envelope = _error_envelope(
            operation,
            HostAPIError("internal-error", f"host API failed: {exc}"),
            root_path,
        )
        code = 2

    output_stream.write(
        json.dumps(envelope, ensure_ascii=True, separators=(",", ":")) + "\n"
    )
    output_stream.flush()
    if code != 0:
        if envelope.get("ok") is False:
            error = envelope.get("error", {})
            message = f"{error.get('code', 'error')}: {error.get('message', '')}"  # type: ignore[union-attr]
        else:
            result = envelope.get("result", {})
            message = str(result.get("message", "candidate-check denied"))  # type: ignore[union-attr]
        safe_message = message.encode("utf-8", "backslashreplace").decode("utf-8")
        error_stream.write(f"host-api: {safe_message}\n")
        error_stream.flush()
    return code
