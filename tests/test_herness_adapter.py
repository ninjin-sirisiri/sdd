from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.herness import integration
from sddlib.html_host_api import policy_identity
from sddlib.html_policy import check_registrations


CLI = ROOT / "adapters/herness/integration.py"
IDENTITY = policy_identity()


def valid_contract() -> dict[str, Any]:
    return {
        "schema": "herness-sdd-host-contract",
        "version": 1,
        "host": "herness",
        "project": "project-1",
        "integration": {
            "schema": "sdd-herness-integration",
            "version": 1,
            "revision": 1,
        },
        "approval": {
            "kind": "h3-configuration-approval",
            "source": "h3-configuration-registry",
            "approved_by": "human",
            "approval_id": "approval-1",
            "settings_version": "settings-1",
            "targets": ["CONTEXT.md", "docs/sdd/specs/example.md"],
            "automatic_companion": True,
        },
        "capabilities": {
            "html_worker": {"version": 1, "available": True},
            "authoring_dispatch": {"version": 1, "available": True},
            "policy_bridge": {"protocol": "sdd-html-host-api", "version": 1},
        },
        "policy": {"version": IDENTITY["version"], "digest": IDENTITY["digest"]},
    }


def contract_with(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    contract = valid_contract()
    mutator(contract)
    return contract


def run_cli(
    arguments: list[str],
    *,
    stdin: str = "",
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        cwd=cwd,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def cli_result(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(process.stdout)


def load_manifest() -> dict[str, Any]:
    return json.loads((ROOT / "adapters/herness/integration.json").read_text("utf-8"))


def write_manifest(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    path = tmp_path / "integration.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_definition_is_versioned_and_does_not_enable_the_html_worker() -> None:
    report = integration.definition_report()
    definition = report["definition"]

    assert report["schema"] == "sdd-herness-integration-status"
    assert report["version"] == 1
    assert report["declared"] is True
    assert report["available"] is False
    assert report["state"] == "definition"
    assert report["code"] == "definition-only"
    assert definition["schema"] == "sdd-herness-integration"
    assert definition["version"] == 1
    assert definition["revision"] == 1
    assert definition["host"] == "herness"
    assert definition["capability"]["name"] == "automatic-html-companion"
    assert definition["capability"]["version"] == 1
    assert definition["capability"]["mode"] == "host-delegated"
    assert definition["capability"]["worker"] == {
        "provided_by": "host",
        "enabled_by_definition": False,
    }
    assert report["worker"]["enabled_by_definition"] is False
    assert report["worker"]["host_attested"] is False
    assert report["worker"]["required_from_host"] is True
    assert "does not enable the herness HtmlWorker" in report["message"]


def test_definition_declares_host_delegation_and_approval_rules() -> None:
    definition = integration.load_definition()
    delegation = definition["capability"]["delegation"]

    assert delegation == {
        "parent_html_dispatch": "forbidden",
        "parent_html_authoring": "forbidden",
        "parent_unsynced_reporting": "host",
        "unsynced_state": "host",
        "common_validation": "host",
        "bootstrap": "host-explicit-common-policy",
        "publication": "host-after-h3-h2-gates",
    }
    approval = definition["capability"]["approval"]
    assert approval["source"] == "h3-configuration-registry"
    assert approval["kind"] == "h3-configuration-approval"
    assert approval["approved_by"] == "human"
    assert {
        "project",
        "settings_version",
        "approval_id",
        "targets",
        "automatic_companion",
    } <= set(approval["requires"])
    assert set(approval["forbidden_sources"]) == {
        "environment-variable",
        "document-declaration",
        "html-meta",
        "receipt",
        "request-actor",
        "owner-kind",
        "model-request",
    }
    activation = definition["activation"]
    assert activation["requires"] == "valid-host-contract"
    assert activation["without_contract"] == "unavailable"
    assert activation["environment_variables"] == "ignored"
    assert activation["document_declarations"] == "ignored"
    assert activation["receipts"] == "ignored"
    assert definition["fallback"] == {
        "other_hosts": "standard-unchanged",
        "herness_unavailable": "explicit-unavailable",
    }


def test_definition_alone_is_explicitly_unavailable() -> None:
    result = integration.status()

    assert result["declared"] is True
    assert result["available"] is False
    assert result["state"] == "unavailable"
    assert result["code"] == "host-contract-missing"
    assert result["delegation"] is None
    assert result["host"] is None
    assert result["worker"]["host_attested"] is False
    assert result["worker"]["enabled_by_definition"] is False
    assert result["pack"]["definition"] == {
        "schema": "sdd-herness-integration",
        "version": 1,
        "revision": 1,
    }
    assert result["pack"]["policy"]["version"] == IDENTITY["version"]
    assert result["pack"]["policy"]["digest"] == IDENTITY["digest"]
    assert result["pack"]["host_api"]["protocol"] == "sdd-html-host-api"
    assert result["pack"]["host_api"]["version"] == 1
    assert "Environment variables" in result["message"]


def test_valid_host_contract_activates_host_delegation() -> None:
    result = integration.status(valid_contract())

    assert result["declared"] is True
    assert result["available"] is True
    assert result["state"] == "active"
    assert result["code"] == "active"
    assert result["delegation"]["parent_html_dispatch"] == "forbidden"
    assert result["delegation"]["parent_html_authoring"] == "forbidden"
    assert result["delegation"]["parent_unsynced_reporting"] == "host"
    assert result["delegation"]["unsynced_state"] == "host"
    assert result["delegation"]["common_validation"] == "host"
    assert result["host"] == {
        "name": "herness",
        "project": "project-1",
        "approval_id": "approval-1",
        "settings_version": "settings-1",
        "targets": ["CONTEXT.md", "docs/sdd/specs/example.md"],
    }
    assert result["worker"] == {
        "host_attested": True,
        "source": "host-contract",
        "verified_by_pack": False,
        "enabled_by_definition": False,
    }
    assert result["pack"]["policy"]["digest"] == IDENTITY["digest"]
    assert any("cannot authenticate" in item for item in result["limitations"])
    assert "must not dispatch or author HTML" in result["message"]


def test_legacy_policy_alias_is_not_accepted_for_a_new_contract() -> None:
    contract = valid_contract()
    contract["policy"]["version"] = "semantic-v1"

    result = integration.status(contract)

    assert result["available"] is False
    assert result["code"] == "policy-version"


def test_environment_markers_and_document_declarations_do_not_activate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERNESS_HTML_SYNC", "active")
    monkeypatch.setenv("HERNESS_SDD_HOST_CONTRACT", json.dumps(valid_contract()))
    monkeypatch.setenv("SDD_HERNESS_CAPABILITY", "automatic-html-companion")
    (tmp_path / "CONTEXT.md").write_text(
        "# Context\n\n<!-- sdd-herness-integration: active -->\n",
        encoding="utf-8",
    )
    (tmp_path / "CONTEXT.html").write_text(
        '<html><head><meta name="sdd-herness-integration" content="active"></head></html>',
        encoding="utf-8",
    )
    receipt = tmp_path / "docs/sdd/html-evidence/receipt.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({"schema": "sdd-html-receipt", "conditions": {}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = integration.status()

    assert result["available"] is False
    assert result["code"] == "host-contract-missing"
    assert result["delegation"] is None
    assert "Environment variables" in result["message"]


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "request-actor-kind",
            lambda contract: contract["approval"].update({"kind": "RequestActor"}),
            "approval-kind",
        ),
        (
            "owner-kind",
            lambda contract: contract["approval"].update({"kind": "OwnerKind"}),
            "approval-kind",
        ),
        (
            "receipt-kind",
            lambda contract: contract["approval"].update({"kind": "receipt"}),
            "approval-kind",
        ),
        (
            "receipt-object",
            lambda contract: contract.update(
                {
                    "approval": {
                        "schema": "sdd-html-receipt",
                        "source": "h3-configuration-registry",
                        "approved_by": "human",
                    }
                }
            ),
            "approval-kind",
        ),
        (
            "environment-source",
            lambda contract: contract["approval"].update({"source": "environment-variable"}),
            "approval-source",
        ),
        (
            "document-source",
            lambda contract: contract["approval"].update({"source": "document-declaration"}),
            "approval-source",
        ),
        (
            "html-meta-source",
            lambda contract: contract["approval"].update({"source": "html-meta"}),
            "approval-source",
        ),
        (
            "receipt-source",
            lambda contract: contract["approval"].update({"source": "receipt"}),
            "approval-source",
        ),
    ),
)
def test_fake_approval_kinds_and_sources_are_rejected(
    label: str, mutator: Callable[[dict[str, Any]], None], code: str
) -> None:
    result = integration.status(contract_with(mutator))

    assert label
    assert result["available"] is False
    assert result["code"] == code
    assert result["state"] == "unavailable"
    assert result["delegation"] is None


@pytest.mark.parametrize("marker", ("request_actor", "requestActor", "owner_kind", "ownerKind"))
def test_actor_and_owner_kind_markers_on_the_contract_are_not_approval(
    marker: str,
) -> None:
    contract = valid_contract()
    contract[marker] = {"kind": "human"}

    result = integration.status(contract)

    assert result["available"] is False
    assert result["code"] == "approval-kind"
    assert marker in result["error"]["path"]


@pytest.mark.parametrize("approved_by", ("model", "agent", "system", "receipt"))
def test_approval_requires_a_human_approver(approved_by: str) -> None:
    result = integration.status(
        contract_with(lambda contract: contract["approval"].update({"approved_by": approved_by}))
    )

    assert result["available"] is False
    assert result["code"] == "approval-actor"


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "missing-approval-id",
            lambda contract: contract["approval"].pop("approval_id"),
            "approval-incomplete",
        ),
        (
            "empty-settings-version",
            lambda contract: contract["approval"].update({"settings_version": " "}),
            "approval-incomplete",
        ),
        (
            "missing-approval",
            lambda contract: contract.pop("approval"),
            "contract-schema",
        ),
        (
            "empty-targets",
            lambda contract: contract["approval"].update({"targets": []}),
            "approval-targets",
        ),
        (
            "automatic-companion-false",
            lambda contract: contract["approval"].update({"automatic_companion": False}),
            "approval-automatic",
        ),
        (
            "automatic-companion-missing",
            lambda contract: contract["approval"].pop("automatic_companion"),
            "approval-incomplete",
        ),
        (
            "absolute-target",
            lambda contract: contract["approval"].update({"targets": ["/CONTEXT.md"]}),
            "approval-targets",
        ),
        (
            "parent-target",
            lambda contract: contract["approval"].update({"targets": ["../CONTEXT.md"]}),
            "approval-targets",
        ),
        (
            "non-markdown-target",
            lambda contract: contract["approval"].update({"targets": ["CONTEXT.html"]}),
            "approval-targets",
        ),
        (
            "duplicate-target",
            lambda contract: contract["approval"].update(
                {"targets": ["CONTEXT.md", "CONTEXT.md"]}
            ),
            "approval-targets",
        ),
    ),
)
def test_approval_must_be_complete_and_bound_to_a_target_set(
    label: str, mutator: Callable[[dict[str, Any]], None], code: str
) -> None:
    result = integration.status(contract_with(mutator))

    assert label
    assert result["available"] is False
    assert result["code"] == code


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "worker-unavailable",
            lambda contract: contract["capabilities"]["html_worker"].update(
                {"available": False}
            ),
            "worker-unavailable",
        ),
        (
            "worker-version",
            lambda contract: contract["capabilities"]["html_worker"].update({"version": 2}),
            "worker-version",
        ),
        (
            "worker-missing",
            lambda contract: contract["capabilities"].pop("html_worker"),
            "capability-missing",
        ),
        (
            "dispatch-unavailable",
            lambda contract: contract["capabilities"]["authoring_dispatch"].update(
                {"available": False}
            ),
            "dispatch-unavailable",
        ),
        (
            "dispatch-version",
            lambda contract: contract["capabilities"]["authoring_dispatch"].update(
                {"version": 2}
            ),
            "dispatch-version",
        ),
        (
            "dispatch-missing",
            lambda contract: contract["capabilities"].pop("authoring_dispatch"),
            "capability-missing",
        ),
        (
            "bridge-protocol",
            lambda contract: contract["capabilities"]["policy_bridge"].update(
                {"protocol": "other-host-api"}
            ),
            "policy-bridge-protocol",
        ),
        (
            "bridge-version",
            lambda contract: contract["capabilities"]["policy_bridge"].update({"version": 2}),
            "policy-bridge-version",
        ),
    ),
)
def test_host_capabilities_must_be_attested_and_match_the_definition(
    label: str, mutator: Callable[[dict[str, Any]], None], code: str
) -> None:
    result = integration.status(contract_with(mutator))

    assert label
    assert result["available"] is False
    assert result["code"] == code


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "policy-version",
            lambda contract: contract["policy"].update({"version": "sdd-html-policy-v2"}),
            "policy-version",
        ),
        (
            "policy-digest",
            lambda contract: contract["policy"].update({"digest": "sha256:" + "0" * 64}),
            "policy-digest",
        ),
        (
            "policy-missing",
            lambda contract: contract.pop("policy"),
            "contract-schema",
        ),
    ),
)
def test_policy_identity_must_match_the_active_pack(
    label: str, mutator: Callable[[dict[str, Any]], None], code: str
) -> None:
    result = integration.status(contract_with(mutator))

    assert label
    assert result["available"] is False
    assert result["code"] == code


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "contract-version",
            lambda contract: contract.update({"version": 2}),
            "unsupported-contract-version",
        ),
        (
            "contract-schema",
            lambda contract: contract.update({"schema": "other-contract"}),
            "contract-schema",
        ),
        (
            "host",
            lambda contract: contract.update({"host": "claude"}),
            "host-mismatch",
        ),
        (
            "unknown-field",
            lambda contract: contract.update({"capability_override": "active"}),
            "contract-schema",
        ),
        (
            "missing-project",
            lambda contract: contract.pop("project"),
            "contract-schema",
        ),
        (
            "missing-integration",
            lambda contract: contract.pop("integration"),
            "contract-schema",
        ),
        (
            "integration-version",
            lambda contract: contract["integration"].update({"version": 2}),
            "integration-version",
        ),
        (
            "integration-schema",
            lambda contract: contract["integration"].update(
                {"schema": "other-integration"}
            ),
            "integration-version",
        ),
        (
            "integration-revision",
            lambda contract: contract["integration"].update({"revision": 2}),
            "integration-revision",
        ),
    ),
)
def test_contract_identity_and_shape_are_explicit(
    label: str, mutator: Callable[[dict[str, Any]], None], code: str
) -> None:
    result = integration.status(contract_with(mutator))

    assert label
    assert result["available"] is False
    assert result["code"] == code


def test_non_object_contract_is_rejected() -> None:
    result = integration.status(["not", "an", "object"])

    assert result["available"] is False
    assert result["code"] == "contract-schema"


def test_pack_without_the_capability_is_explicitly_unavailable(tmp_path: Path) -> None:
    missing = tmp_path / "integration.json"

    result = integration.status(valid_contract(), definition_path=missing)

    assert result["declared"] is False
    assert result["available"] is False
    assert result["code"] == "pack-capability-missing"
    assert result["state"] == "unavailable"
    assert result["delegation"] is None
    with pytest.raises(integration.IntegrationError) as raised:
        integration.load_definition(missing)
    assert raised.value.code == "pack-capability-missing"


@pytest.mark.parametrize(
    ("label", "mutator", "code"),
    (
        (
            "version",
            lambda manifest: manifest.update({"version": 2}),
            "unsupported-definition-version",
        ),
        (
            "unknown-field",
            lambda manifest: manifest.update({"unexpected": True}),
            "pack-definition-invalid",
        ),
        (
            "worker-enabled",
            lambda manifest: manifest["capability"]["worker"].update(
                {"enabled_by_definition": True}
            ),
            "pack-definition-invalid",
        ),
        (
            "delegation",
            lambda manifest: manifest["capability"]["delegation"].update(
                {"parent_html_dispatch": "allowed"}
            ),
            "pack-definition-invalid",
        ),
        (
            "stale-policy",
            lambda manifest: manifest["pack"].update({"policy": "sdd-html-policy-v0"}),
            "pack-definition-stale",
        ),
        (
            "host-contract-version",
            lambda manifest: manifest["capability"]["host_contract"].update({"version": 2}),
            "unsupported-definition-version",
        ),
    ),
)
def test_invalid_or_stale_definition_is_rejected(
    tmp_path: Path,
    label: str,
    mutator: Callable[[dict[str, Any]], None],
    code: str,
) -> None:
    manifest = load_manifest()
    mutator(manifest)
    path = write_manifest(tmp_path, manifest)

    result = integration.status(valid_contract(), definition_path=path)

    assert label
    assert result["available"] is False
    assert result["code"] == code
    assert result["state"] == "unavailable"


def test_definition_with_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "integration.json"
    path.write_text("{not json", encoding="utf-8")

    result = integration.status(definition_path=path)

    assert result["available"] is False
    assert result["code"] == "pack-definition-invalid"


def test_cli_status_reads_only_stdin_and_reports_versioned_envelopes(
    tmp_path: Path,
) -> None:
    process = run_cli(
        ["status"],
        stdin=json.dumps(valid_contract()),
        cwd=tmp_path,
        env={**os.environ, "HERNESS_HTML_SYNC": "inactive"},
    )
    result = cli_result(process)

    assert process.returncode == 0
    assert process.stderr == ""
    assert result["schema"] == "sdd-herness-integration-status"
    assert result["version"] == 1
    assert result["available"] is True
    assert result["state"] == "active"


def test_cli_status_is_unavailable_without_contract_even_with_environment_markers(
    tmp_path: Path,
) -> None:
    process = run_cli(
        ["status"],
        cwd=tmp_path,
        env={
            **os.environ,
            "HERNESS_HTML_SYNC": "active",
            "HERNESS_SDD_HOST_CONTRACT": json.dumps(valid_contract()),
        },
    )
    result = cli_result(process)

    assert process.returncode == 1
    assert result["available"] is False
    assert result["code"] == "host-contract-missing"
    assert "Environment variables" in process.stderr


def test_cli_rejects_invalid_json_and_reports_the_definition(tmp_path: Path) -> None:
    invalid = run_cli(["status"], stdin="{not json", cwd=tmp_path)
    invalid_result = cli_result(invalid)

    assert invalid.returncode == 2
    assert invalid_result["available"] is False
    assert invalid_result["code"] == "host-contract-invalid-json"

    definition = run_cli(["definition"], cwd=tmp_path)
    definition_result = cli_result(definition)

    assert definition.returncode == 0
    assert definition_result["state"] == "definition"
    assert definition_result["available"] is False
    assert definition_result["definition"]["version"] == 1
    assert definition_result["worker"]["enabled_by_definition"] is False
    assert definition_result["pack"]["policy"]["digest"] == IDENTITY["digest"]


def test_cli_usage_is_explicit(tmp_path: Path) -> None:
    process = run_cli([], cwd=tmp_path)
    result = cli_result(process)

    assert process.returncode == 2
    assert result["available"] is False
    assert result["code"] == "usage"


def test_other_hosts_keep_their_standard_registration_and_behavior(tmp_path: Path) -> None:
    result = check_registrations(tmp_path)

    assert [item["host"] for item in result["registrations"]] == [
        "cursor",
        "claude",
        "opencode",
    ]
    assert {item["status"] for item in result["registrations"]} == {"missing"}
    assert "herness" not in result["paths"]
    assert "registration" in result["message"]
    assert all(item["host"] != "herness" for item in result["registrations"])


def test_herness_definition_does_not_register_a_standard_host_hook() -> None:
    assert not (ROOT / "adapters/herness/hooks.json.example").exists()
    assert not (ROOT / "adapters/herness/html_docs_hook.py").exists()
    assert not (ROOT / "adapters/herness/html_docs_plugin.ts").exists()
    assert integration.load_definition()["capability"]["worker"]["enabled_by_definition"] is False


def test_manifest_on_disk_matches_the_module_version() -> None:
    manifest = load_manifest()

    assert manifest["schema"] == integration.DEFINITION_SCHEMA
    assert manifest["version"] == integration.DEFINITION_VERSION
    assert (
        manifest["capability"]["host_contract"]["schema"]
        == integration.HOST_CONTRACT_SCHEMA
    )
    assert (
        manifest["capability"]["host_contract"]["version"]
        == integration.HOST_CONTRACT_VERSION
    )
    assert manifest["capability"]["name"] == integration.CAPABILITY_NAME
    assert manifest["capability"]["version"] == integration.CAPABILITY_VERSION
    assert manifest["host"] == integration.HOST_NAME
    assert manifest["capability"]["approval"]["source"] == integration.APPROVAL_SOURCE
    assert manifest["capability"]["approval"]["kind"] == integration.APPROVAL_KIND
    assert manifest["capability"]["approval"]["approved_by"] == integration.APPROVER


def test_deepcopy_is_not_mutated_by_validation() -> None:
    contract = valid_contract()
    snapshot = deepcopy(contract)

    integration.status(contract)

    assert contract == snapshot
