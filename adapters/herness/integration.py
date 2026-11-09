#!/usr/bin/env python3
"""Versioned herness host-integration contract for delegated HTML authoring.

The pack-side definition is ``adapters/herness/integration.json``.  A host is
allowed to take over HTML companion authoring only when it supplies a version 1
host contract from its approved H3 configuration registry.  Environment
variables, document declarations, receipts, ``RequestActor``/``OwnerKind``
markers, and model requests are not approval.

This module validates the definition and the contract shape.  It cannot
authenticate the host registry; the trusted herness boundary must supply the
contract.  The pack declaration does not implement or enable the herness
HtmlWorker.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import sys
from typing import Any


PACK_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PACK_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

DEFINITION_SCHEMA = "sdd-herness-integration"
DEFINITION_VERSION = 1
HOST_CONTRACT_SCHEMA = "herness-sdd-host-contract"
HOST_CONTRACT_VERSION = 1
STATUS_SCHEMA = "sdd-herness-integration-status"
STATUS_VERSION = 1
CAPABILITY_NAME = "automatic-html-companion"
CAPABILITY_VERSION = 1
HOST_NAME = "herness"
APPROVAL_SOURCE = "h3-configuration-registry"
APPROVAL_KIND = "h3-configuration-approval"
APPROVER = "human"

DEFAULT_DEFINITION_PATH = Path(__file__).with_name("integration.json")

FORBIDDEN_APPROVAL_SOURCES = frozenset(
    {
        "environment-variable",
        "document-declaration",
        "html-meta",
        "receipt",
        "request-actor",
        "owner-kind",
        "model-request",
    }
)
FORBIDDEN_APPROVAL_KINDS = frozenset(
    {
        "receipt",
        "environment-variable",
        "document-declaration",
        "html-meta",
        "request-actor",
        "requestactor",
        "owner-kind",
        "ownerkind",
        "model-request",
    }
)
ACTOR_MARKERS = ("request_actor", "requestActor", "owner_kind", "ownerKind")

BASE_LIMITATIONS = (
    "The pack declaration does not implement or enable the herness HtmlWorker.",
    "The pack validates the host contract shape but cannot authenticate the herness configuration registry.",
    "An active status is host-attested and does not replace H3 evaluation, H2 assessment, publication, Git, or CI.",
)


class IntegrationError(ValueError):
    """A definition or host contract that cannot produce an active status."""

    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result


def _fail(code: str, message: str, path: str | None = None) -> None:
    raise IntegrationError(code, message, path=path)


def _expect_object(
    value: Any,
    path: str,
    required: tuple[str, ...],
    *,
    code: str,
    optional: tuple[str, ...] = (),
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code, f"{path} must be a JSON object", path)
    missing = [name for name in required if name not in value]
    if missing:
        _fail(code, f"{path} is missing required field(s): {', '.join(missing)}", path)
    unknown = sorted(set(value) - set(required) - set(optional))
    if unknown:
        _fail(code, f"{path} contains unknown field(s): {', '.join(unknown)}", path)
    return value


def _string(value: Any, path: str, *, code: str, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value.strip()):
        _fail(code, f"{path} must be a non-empty string", path)
    return value


def _integer(value: Any, path: str, *, code: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(code, f"{path} must be an integer", path)
    if minimum is not None and value < minimum:
        _fail(code, f"{path} must be at least {minimum}", path)
    return value


def _boolean(value: Any, path: str, *, code: str) -> bool:
    if not isinstance(value, bool):
        _fail(code, f"{path} must be a JSON boolean", path)
    return value


def _strings(value: Any, path: str, *, code: str) -> list[str]:
    if not isinstance(value, list):
        _fail(code, f"{path} must be an array of strings", path)
    result: list[str] = []
    for index, entry in enumerate(value):
        result.append(_string(entry, f"{path}[{index}]", code=code))
    return result


def _validate_definition(definition: Any) -> dict[str, Any]:
    root = _expect_object(
        definition,
        "definition",
        (
            "schema",
            "version",
            "revision",
            "host",
            "capability",
            "activation",
            "fallback",
            "pack",
            "limitations",
        ),
        code="pack-definition-invalid",
    )
    if root["schema"] != DEFINITION_SCHEMA:
        _fail(
            "pack-definition-invalid",
            f"definition.schema must be {DEFINITION_SCHEMA!r}",
            "definition.schema",
        )
    if root["version"] != DEFINITION_VERSION:
        _fail(
            "unsupported-definition-version",
            f"definition.version {root['version']!r} is not supported; "
            f"this pack implements version {DEFINITION_VERSION}",
            "definition.version",
        )
    _integer(root["revision"], "definition.revision", code="pack-definition-invalid", minimum=1)
    if root["host"] != HOST_NAME:
        _fail(
            "pack-definition-invalid",
            f"definition.host must be {HOST_NAME!r}",
            "definition.host",
        )

    capability = _expect_object(
        root["capability"],
        "definition.capability",
        (
            "name",
            "version",
            "mode",
            "summary",
            "host_contract",
            "requires",
            "delegation",
            "approval",
            "worker",
        ),
        code="pack-definition-invalid",
    )
    if capability["name"] != CAPABILITY_NAME:
        _fail(
            "pack-definition-invalid",
            f"definition.capability.name must be {CAPABILITY_NAME!r}",
            "definition.capability.name",
        )
    if capability["version"] != CAPABILITY_VERSION:
        _fail(
            "unsupported-definition-version",
            f"definition.capability.version {capability['version']!r} is not supported",
            "definition.capability.version",
        )
    if capability["mode"] != "host-delegated":
        _fail(
            "pack-definition-invalid",
            "definition.capability.mode must be 'host-delegated'",
            "definition.capability.mode",
        )
    _string(capability["summary"], "definition.capability.summary", code="pack-definition-invalid")

    host_contract = _expect_object(
        capability["host_contract"],
        "definition.capability.host_contract",
        ("schema", "version"),
        code="pack-definition-invalid",
    )
    if host_contract["schema"] != HOST_CONTRACT_SCHEMA:
        _fail(
            "pack-definition-invalid",
            f"definition.capability.host_contract.schema must be {HOST_CONTRACT_SCHEMA!r}",
            "definition.capability.host_contract.schema",
        )
    if host_contract["version"] != HOST_CONTRACT_VERSION:
        _fail(
            "unsupported-definition-version",
            f"definition host contract version {host_contract['version']!r} "
            f"does not match this module's version {HOST_CONTRACT_VERSION}",
            "definition.capability.host_contract.version",
        )

    requires = _expect_object(
        capability["requires"],
        "definition.capability.requires",
        ("html_worker", "authoring_dispatch", "policy_bridge"),
        code="pack-definition-invalid",
    )
    for name in ("html_worker", "authoring_dispatch"):
        requirement = _expect_object(
            requires[name],
            f"definition.capability.requires.{name}",
            ("version", "provided_by"),
            code="pack-definition-invalid",
        )
        _integer(
            requirement["version"],
            f"definition.capability.requires.{name}.version",
            code="pack-definition-invalid",
            minimum=1,
        )
        if requirement["provided_by"] != "host":
            _fail(
                "pack-definition-invalid",
                f"definition.capability.requires.{name}.provided_by must be 'host'",
                f"definition.capability.requires.{name}.provided_by",
            )
    bridge = _expect_object(
        requires["policy_bridge"],
        "definition.capability.requires.policy_bridge",
        ("protocol", "version"),
        code="pack-definition-invalid",
    )
    _string(
        bridge["protocol"],
        "definition.capability.requires.policy_bridge.protocol",
        code="pack-definition-invalid",
    )
    _integer(
        bridge["version"],
        "definition.capability.requires.policy_bridge.version",
        code="pack-definition-invalid",
        minimum=1,
    )

    delegation = _expect_object(
        capability["delegation"],
        "definition.capability.delegation",
        (
            "parent_html_dispatch",
            "parent_html_authoring",
            "parent_unsynced_reporting",
            "unsynced_state",
            "common_validation",
            "bootstrap",
            "publication",
        ),
        code="pack-definition-invalid",
    )
    expected_delegation = {
        "parent_html_dispatch": "forbidden",
        "parent_html_authoring": "forbidden",
        "parent_unsynced_reporting": "host",
        "unsynced_state": "host",
        "common_validation": "host",
        "bootstrap": "host-explicit-common-policy",
        "publication": "host-after-h3-h2-gates",
    }
    for name, expected in expected_delegation.items():
        if delegation[name] != expected:
            _fail(
                "pack-definition-invalid",
                f"definition.capability.delegation.{name} must be {expected!r}",
                f"definition.capability.delegation.{name}",
            )

    approval = _expect_object(
        capability["approval"],
        "definition.capability.approval",
        ("source", "kind", "approved_by", "requires", "forbidden_sources"),
        code="pack-definition-invalid",
    )
    if approval["source"] != APPROVAL_SOURCE:
        _fail(
            "pack-definition-invalid",
            f"definition.capability.approval.source must be {APPROVAL_SOURCE!r}",
            "definition.capability.approval.source",
        )
    if approval["kind"] != APPROVAL_KIND:
        _fail(
            "pack-definition-invalid",
            f"definition.capability.approval.kind must be {APPROVAL_KIND!r}",
            "definition.capability.approval.kind",
        )
    if approval["approved_by"] != APPROVER:
        _fail(
            "pack-definition-invalid",
            f"definition.capability.approval.approved_by must be {APPROVER!r}",
            "definition.capability.approval.approved_by",
        )
    required_approval_fields = set(
        _strings(
            approval["requires"],
            "definition.capability.approval.requires",
            code="pack-definition-invalid",
        )
    )
    if not {
        "project",
        "settings_version",
        "approval_id",
        "targets",
        "automatic_companion",
    } <= required_approval_fields:
        _fail(
            "pack-definition-invalid",
            "definition.capability.approval.requires must include "
            "project, settings_version, approval_id, targets, and automatic_companion",
            "definition.capability.approval.requires",
        )
    forbidden_sources = set(
        _strings(
            approval["forbidden_sources"],
            "definition.capability.approval.forbidden_sources",
            code="pack-definition-invalid",
        )
    )
    if not FORBIDDEN_APPROVAL_SOURCES <= forbidden_sources:
        _fail(
            "pack-definition-invalid",
            "definition.capability.approval.forbidden_sources must include every "
            "non-human approval source",
            "definition.capability.approval.forbidden_sources",
        )

    worker = _expect_object(
        capability["worker"],
        "definition.capability.worker",
        ("provided_by", "enabled_by_definition"),
        code="pack-definition-invalid",
    )
    if worker["provided_by"] != "host":
        _fail(
            "pack-definition-invalid",
            "definition.capability.worker.provided_by must be 'host'",
            "definition.capability.worker.provided_by",
        )
    if worker["enabled_by_definition"] is not False:
        _fail(
            "pack-definition-invalid",
            "definition.capability.worker.enabled_by_definition must be false",
            "definition.capability.worker.enabled_by_definition",
        )

    activation = _expect_object(
        root["activation"],
        "definition.activation",
        (
            "requires",
            "environment_variables",
            "document_declarations",
            "receipts",
            "request_actors",
            "owner_kinds",
            "without_contract",
        ),
        code="pack-definition-invalid",
    )
    expected_activation = {
        "requires": "valid-host-contract",
        "environment_variables": "ignored",
        "document_declarations": "ignored",
        "receipts": "ignored",
        "request_actors": "ignored",
        "owner_kinds": "ignored",
        "without_contract": "unavailable",
    }
    for name, expected in expected_activation.items():
        if activation[name] != expected:
            _fail(
                "pack-definition-invalid",
                f"definition.activation.{name} must be {expected!r}",
                f"definition.activation.{name}",
            )

    fallback = _expect_object(
        root["fallback"],
        "definition.fallback",
        ("other_hosts", "herness_unavailable"),
        code="pack-definition-invalid",
    )
    if fallback["other_hosts"] != "standard-unchanged":
        _fail(
            "pack-definition-invalid",
            "definition.fallback.other_hosts must be 'standard-unchanged'",
            "definition.fallback.other_hosts",
        )
    if fallback["herness_unavailable"] != "explicit-unavailable":
        _fail(
            "pack-definition-invalid",
            "definition.fallback.herness_unavailable must be 'explicit-unavailable'",
            "definition.fallback.herness_unavailable",
        )

    pack = _expect_object(
        root["pack"],
        "definition.pack",
        ("policy",),
        code="pack-definition-invalid",
    )
    _string(pack["policy"], "definition.pack.policy", code="pack-definition-invalid")

    limitations = _strings(
        root["limitations"], "definition.limitations", code="pack-definition-invalid"
    )
    if not limitations:
        _fail(
            "pack-definition-invalid",
            "definition.limitations must not be empty",
            "definition.limitations",
        )
    return dict(root)


def load_definition(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the pack-side integration definition."""

    definition_path = Path(path) if path is not None else DEFAULT_DEFINITION_PATH
    if not definition_path.is_file():
        _fail(
            "pack-capability-missing",
            "the pack does not contain a herness integration definition at "
            f"{definition_path}; herness delegated authoring is unavailable",
            str(definition_path),
        )
    try:
        content = definition_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _fail(
            "pack-capability-missing",
            f"the herness integration definition cannot be read: {exc}",
            str(definition_path),
        )
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        _fail(
            "pack-definition-invalid",
            f"the herness integration definition is not valid JSON: {exc}",
            str(definition_path),
        )
    return _validate_definition(raw)


def _policy_identity() -> dict[str, Any]:
    try:
        from sddlib.html_host_api import policy_identity
    except Exception as exc:  # noqa: BLE001 - pack import boundary
        _fail(
            "pack-policy-unavailable",
            f"the common SDD policy identity is unavailable: {exc}",
        )
    try:
        identity = policy_identity()
    except Exception as exc:  # noqa: BLE001 - policy boundary
        _fail(
            "pack-policy-unavailable",
            f"the common SDD policy identity could not be computed: {exc}",
        )
    if not isinstance(identity, dict) or not identity.get("version") or not identity.get("digest"):
        _fail("pack-policy-unavailable", "the common SDD policy identity is incomplete")
    return identity


def _host_api_identity() -> dict[str, Any]:
    try:
        from sddlib.html_host_api import OPERATIONS, PROTOCOL_NAME, PROTOCOL_VERSION
    except Exception as exc:  # noqa: BLE001 - pack import boundary
        _fail(
            "pack-policy-unavailable",
            f"the versioned host API is unavailable: {exc}",
        )
    return {
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "operations": list(OPERATIONS),
    }


def _check_definition_against_pack(
    definition: Mapping[str, Any],
    policy: Mapping[str, Any],
    host_api: Mapping[str, Any],
) -> None:
    if definition["pack"]["policy"] != policy["version"]:
        _fail(
            "pack-definition-stale",
            "the herness integration definition pins policy "
            f"{definition['pack']['policy']!r}, but this pack provides {policy['version']!r}",
            "definition.pack.policy",
        )
    bridge = definition["capability"]["requires"]["policy_bridge"]
    if bridge["protocol"] != host_api["protocol"]:
        _fail(
            "pack-definition-stale",
            "the herness integration definition requires host API protocol "
            f"{bridge['protocol']!r}, but this pack provides {host_api['protocol']!r}",
            "definition.capability.requires.policy_bridge.protocol",
        )
    if bridge["version"] != host_api["version"]:
        _fail(
            "pack-definition-stale",
            "the herness integration definition requires host API version "
            f"{bridge['version']!r}, but this pack provides {host_api['version']!r}",
            "definition.capability.requires.policy_bridge.version",
        )


def _target_shape(path: str) -> bool:
    if path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} or part.startswith(".") for part in parts):
        return False
    return path.endswith(".md")


def _validate_approval(approval: Any) -> Mapping[str, Any]:
    if not isinstance(approval, Mapping):
        _fail("approval-incomplete", "host contract approval must be a JSON object", "approval")
    if (
        approval.get("schema") == "sdd-html-receipt"
        or approval.get("kind") in FORBIDDEN_APPROVAL_KINDS
    ):
        _fail(
            "approval-kind",
            "a receipt, environment marker, document declaration, RequestActor, "
            "OwnerKind, or model request is not human approval",
            "approval.kind",
        )
    if approval.get("source") in FORBIDDEN_APPROVAL_SOURCES:
        _fail(
            "approval-source",
            f"approval source {approval.get('source')!r} is not the approved "
            f"{APPROVAL_SOURCE!r}",
            "approval.source",
        )
    checked = _expect_object(
        approval,
        "approval",
        (
            "kind",
            "source",
            "approved_by",
            "approval_id",
            "settings_version",
            "targets",
            "automatic_companion",
        ),
        code="approval-incomplete",
    )
    if checked["kind"] != APPROVAL_KIND:
        _fail(
            "approval-kind",
            f"approval.kind must be {APPROVAL_KIND!r}; a RequestActor, OwnerKind, "
            "environment marker, document declaration, receipt, or model request is "
            "not human approval",
            "approval.kind",
        )
    if checked["source"] != APPROVAL_SOURCE:
        _fail(
            "approval-source",
            f"approval.source must be {APPROVAL_SOURCE!r}",
            "approval.source",
        )
    if checked["approved_by"] != APPROVER:
        _fail(
            "approval-actor",
            "approval.approved_by must be 'human' from the trusted configuration UI",
            "approval.approved_by",
        )
    _string(checked["approval_id"], "approval.approval_id", code="approval-incomplete")
    _string(
        checked["settings_version"],
        "approval.settings_version",
        code="approval-incomplete",
    )
    automatic = _boolean(
        checked["automatic_companion"],
        "approval.automatic_companion",
        code="approval-automatic",
    )
    if automatic is not True:
        _fail(
            "approval-automatic",
            "approval.automatic_companion must be true for the approved Target set",
            "approval.automatic_companion",
        )
    targets = _strings(checked["targets"], "approval.targets", code="approval-targets")
    if not targets:
        _fail(
            "approval-targets",
            "approval.targets must contain at least one approved Target Markdown path",
            "approval.targets",
        )
    if len(set(targets)) != len(targets):
        _fail(
            "approval-targets",
            "approval.targets contains duplicate paths",
            "approval.targets",
        )
    for index, target in enumerate(targets):
        if not _target_shape(target):
            _fail(
                "approval-targets",
                f"approval.targets[{index}] is not a canonical relative Target Markdown path: "
                f"{target!r}",
                f"approval.targets[{index}]",
            )
    return checked


def _validate_capabilities(
    capabilities: Any,
    definition: Mapping[str, Any],
) -> Mapping[str, Any]:
    checked = _expect_object(
        capabilities,
        "capabilities",
        ("html_worker", "authoring_dispatch", "policy_bridge"),
        code="capability-missing",
    )
    requirements = definition["capability"]["requires"]

    worker = _expect_object(
        checked["html_worker"],
        "capabilities.html_worker",
        ("version", "available"),
        code="capability-missing",
    )
    worker_version = _integer(
        worker["version"],
        "capabilities.html_worker.version",
        code="worker-version",
        minimum=1,
    )
    _boolean(
        worker["available"],
        "capabilities.html_worker.available",
        code="worker-unavailable",
    )
    if worker_version != requirements["html_worker"]["version"]:
        _fail(
            "worker-version",
            f"capabilities.html_worker.version {worker_version} does not match the "
            f"required version {requirements['html_worker']['version']}",
            "capabilities.html_worker.version",
        )
    if worker["available"] is not True:
        _fail(
            "worker-unavailable",
            "the host contract does not attest an available herness HtmlWorker",
            "capabilities.html_worker.available",
        )

    dispatch = _expect_object(
        checked["authoring_dispatch"],
        "capabilities.authoring_dispatch",
        ("version", "available"),
        code="capability-missing",
    )
    dispatch_version = _integer(
        dispatch["version"],
        "capabilities.authoring_dispatch.version",
        code="dispatch-version",
        minimum=1,
    )
    _boolean(
        dispatch["available"],
        "capabilities.authoring_dispatch.available",
        code="dispatch-unavailable",
    )
    if dispatch_version != requirements["authoring_dispatch"]["version"]:
        _fail(
            "dispatch-version",
            f"capabilities.authoring_dispatch.version {dispatch_version} does not match "
            f"the required version {requirements['authoring_dispatch']['version']}",
            "capabilities.authoring_dispatch.version",
        )
    if dispatch["available"] is not True:
        _fail(
            "dispatch-unavailable",
            "the host contract does not attest host-owned authoring dispatch",
            "capabilities.authoring_dispatch.available",
        )

    bridge = _expect_object(
        checked["policy_bridge"],
        "capabilities.policy_bridge",
        ("protocol", "version"),
        code="capability-missing",
    )
    required_bridge = requirements["policy_bridge"]
    if bridge["protocol"] != required_bridge["protocol"]:
        _fail(
            "policy-bridge-protocol",
            f"capabilities.policy_bridge.protocol must be {required_bridge['protocol']!r}",
            "capabilities.policy_bridge.protocol",
        )
    bridge_version = _integer(
        bridge["version"],
        "capabilities.policy_bridge.version",
        code="policy-bridge-version",
        minimum=1,
    )
    if bridge_version != required_bridge["version"]:
        _fail(
            "policy-bridge-version",
            f"capabilities.policy_bridge.version {bridge_version} does not match the "
            f"required version {required_bridge['version']}",
            "capabilities.policy_bridge.version",
        )
    return checked


def _validate_contract(
    contract: Any,
    definition: Mapping[str, Any],
    policy: Mapping[str, Any],
    host_api: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if not isinstance(contract, Mapping):
        _fail(
            "contract-schema",
            "the herness host contract must be a JSON object",
            "contract",
        )
    for marker in ACTOR_MARKERS:
        if marker in contract:
            _fail(
                "approval-kind",
                f"{marker} is not human approval; the approved H3 configuration "
                "registry must supply the contract",
                marker,
            )
    checked = _expect_object(
        contract,
        "contract",
        (
            "schema",
            "version",
            "host",
            "project",
            "integration",
            "approval",
            "capabilities",
            "policy",
        ),
        code="contract-schema",
    )
    if checked["schema"] != HOST_CONTRACT_SCHEMA:
        _fail(
            "contract-schema",
            f"contract.schema must be {HOST_CONTRACT_SCHEMA!r}",
            "contract.schema",
        )
    _integer(checked["version"], "contract.version", code="contract-schema", minimum=1)
    if checked["version"] != HOST_CONTRACT_VERSION:
        _fail(
            "unsupported-contract-version",
            f"contract.version {checked['version']!r} is not supported; "
            f"this pack implements version {HOST_CONTRACT_VERSION}",
            "contract.version",
        )
    if checked["host"] != HOST_NAME:
        _fail(
            "host-mismatch",
            f"contract.host must be {HOST_NAME!r}",
            "contract.host",
        )
    _string(checked["project"], "contract.project", code="contract-schema")

    integration_block = _expect_object(
        checked["integration"],
        "integration",
        ("schema", "version", "revision"),
        code="contract-schema",
    )
    if (
        integration_block["schema"] != definition["schema"]
        or integration_block["version"] != definition["version"]
    ):
        _fail(
            "integration-version",
            "contract.integration must name the active "
            f"{definition['schema']!r} version {definition['version']}",
            "integration",
        )
    if integration_block["revision"] != definition["revision"]:
        _fail(
            "integration-revision",
            f"contract.integration.revision {integration_block['revision']!r} does not "
            f"match the active pack definition revision {definition['revision']}",
            "integration.revision",
        )

    approval = _validate_approval(checked["approval"])
    _validate_capabilities(checked["capabilities"], definition)

    policy_block = _expect_object(
        checked["policy"],
        "policy",
        ("version", "digest"),
        code="contract-schema",
    )
    if policy_block["version"] != policy["version"]:
        _fail(
            "policy-version",
            f"contract.policy.version {policy_block['version']!r} does not match the "
            f"active pack policy {policy['version']!r}",
            "policy.version",
        )
    if policy_block["digest"] != policy["digest"]:
        _fail(
            "policy-digest",
            "contract.policy.digest does not match the active pack policy fingerprint",
            "policy.digest",
        )
    if checked["capabilities"]["policy_bridge"]["version"] != host_api["version"]:
        _fail(
            "policy-bridge-version",
            "capabilities.policy_bridge.version does not match the active host API",
            "capabilities.policy_bridge.version",
        )
    return checked, approval


def _pack_report(
    definition: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    host_api: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "definition": (
            {
                "schema": definition["schema"],
                "version": definition["version"],
                "revision": definition["revision"],
            }
            if definition is not None
            else None
        ),
        "policy": dict(policy) if policy is not None else None,
        "host_api": dict(host_api) if host_api is not None else None,
    }


def _unavailable(
    error: IntegrationError,
    definition: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    host_api: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    limitations = list(
        definition["limitations"] if definition is not None else BASE_LIMITATIONS
    )
    return {
        "schema": STATUS_SCHEMA,
        "version": STATUS_VERSION,
        "declared": definition is not None,
        "available": False,
        "state": "unavailable",
        "code": error.code,
        "message": error.message,
        "error": error.as_dict(),
        "host": None,
        "capability": CAPABILITY_NAME,
        "delegation": None,
        "worker": {
            "host_attested": False,
            "source": "none",
            "verified_by_pack": False,
            "enabled_by_definition": False,
        },
        "pack": _pack_report(definition, policy, host_api),
        "limitations": limitations,
    }


def status(
    contract: Any = None,
    *,
    definition_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return an explicit active or unavailable herness integration status.

    ``contract`` must be the object supplied by the trusted herness host from
    its approved H3 configuration registry.  No environment variable, document,
    receipt, RequestActor, or OwnerKind is consulted.
    """

    definition: Mapping[str, Any] | None = None
    policy: Mapping[str, Any] | None = None
    host_api: Mapping[str, Any] | None = None
    try:
        definition = load_definition(definition_path)
        policy = _policy_identity()
        host_api = _host_api_identity()
        _check_definition_against_pack(definition, policy, host_api)
    except IntegrationError as exc:
        return _unavailable(exc, definition, policy, host_api)

    if contract is None:
        return _unavailable(
            IntegrationError(
                "host-contract-missing",
                "no approved herness host contract was supplied; host-delegated "
                "HTML authoring is unavailable. Environment variables, document "
                "declarations, receipts, RequestActor/OwnerKind markers, and model "
                "requests are not approval.",
            ),
            definition,
            policy,
            host_api,
        )

    try:
        checked, approval = _validate_contract(contract, definition, policy, host_api)
    except IntegrationError as exc:
        return _unavailable(exc, definition, policy, host_api)

    return {
        "schema": STATUS_SCHEMA,
        "version": STATUS_VERSION,
        "declared": True,
        "available": True,
        "state": "active",
        "code": "active",
        "message": (
            "The approved herness host contract is active. The parent agent must not "
            "dispatch or author HTML companions; the host owns unsynced state and "
            "common static validation."
        ),
        "error": None,
        "host": {
            "name": HOST_NAME,
            "project": checked["project"],
            "approval_id": approval["approval_id"],
            "settings_version": approval["settings_version"],
            "targets": list(approval["targets"]),
        },
        "capability": CAPABILITY_NAME,
        "delegation": dict(definition["capability"]["delegation"]),
        "worker": {
            "host_attested": True,
            "source": "host-contract",
            "verified_by_pack": False,
            "enabled_by_definition": False,
        },
        "pack": _pack_report(definition, policy, host_api),
        "limitations": list(definition["limitations"]),
    }


def definition_report(*, definition_path: str | Path | None = None) -> dict[str, Any]:
    """Return the pack-side definition with the current pack identity."""

    definition = load_definition(definition_path)
    policy = _policy_identity()
    host_api = _host_api_identity()
    _check_definition_against_pack(definition, policy, host_api)
    return {
        "schema": STATUS_SCHEMA,
        "version": STATUS_VERSION,
        "declared": True,
        "available": False,
        "state": "definition",
        "code": "definition-only",
        "message": (
            "The pack declares the herness host-delegated HTML capability. This "
            "declaration does not enable the herness HtmlWorker; a valid host "
            "contract is still required."
        ),
        "definition": definition,
        "worker": {
            "host_attested": False,
            "source": "none",
            "verified_by_pack": False,
            "enabled_by_definition": False,
            "required_from_host": True,
        },
        "pack": _pack_report(definition, policy, host_api),
        "limitations": list(definition["limitations"]),
    }


def _write(payload: Mapping[str, Any], exit_code: int) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    if exit_code != 0:
        message = payload.get("message")
        if isinstance(message, str) and message:
            sys.stderr.write(f"herness-integration: {message}\n")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments not in (["definition"], ["status"]):
        return _write(
            {
                "schema": STATUS_SCHEMA,
                "version": STATUS_VERSION,
                "available": False,
                "state": "unavailable",
                "code": "usage",
                "message": "usage: integration.py {definition|status}",
            },
            2,
        )

    if arguments == ["definition"]:
        try:
            return _write(definition_report(), 0)
        except IntegrationError as exc:
            return _write(_unavailable(exc), 1)

    if sys.stdin.isatty():
        return _write(status(None), 1)
    text = sys.stdin.read()
    if not text.strip():
        return _write(status(None), 1)
    try:
        contract = json.loads(text)
    except json.JSONDecodeError as exc:
        return _write(
            _unavailable(
                IntegrationError(
                    "host-contract-invalid-json",
                    f"the herness host contract is not valid JSON: {exc}",
                )
            ),
            2,
        )
    result = status(contract)
    return _write(result, 0 if result["available"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
