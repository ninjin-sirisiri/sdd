# herness host integration

`integration.json` is the versioned pack-side declaration for the herness host
(schema `sdd-herness-integration`, version `1`, revision `1`). It is not a host
edit hook. Cursor, Claude Code, and OpenCode keep their existing adapters,
`html-docs bootstrap`, and `html-docs doctor` behavior.

The declaration names the `automatic-html-companion` capability. A host may use
it only when the trusted herness host supplies a version `1`
`herness-sdd-host-contract` from its approved H3 configuration registry. In that
state the host owns unsynced-state observation, companion authoring dispatch,
explicit bootstrap recording, and calls to the common static validation
commands. The parent agent must not author companion HTML or ask the parent
model to dispatch an HTML worker.

## Host contract version 1

The contract is a JSON object supplied by the host, never discovered from an
environment variable, a document, an HTML meta element, a receipt,
`RequestActor`, `OwnerKind`, or a model request.

```json
{
  "schema": "herness-sdd-host-contract",
  "version": 1,
  "host": "herness",
  "project": "project-id",
  "integration": {
    "schema": "sdd-herness-integration",
    "version": 1,
    "revision": 1
  },
  "approval": {
    "kind": "h3-configuration-approval",
    "source": "h3-configuration-registry",
    "approved_by": "human",
    "approval_id": "approval-id",
    "settings_version": "settings-id",
    "targets": ["CONTEXT.md", "docs/sdd/specs/example.md"],
    "automatic_companion": true
  },
  "capabilities": {
    "html_worker": {"version": 1, "available": true},
    "authoring_dispatch": {"version": 1, "available": true},
    "policy_bridge": {"protocol": "sdd-html-host-api", "version": 1}
  },
  "policy": {
    "version": "sdd-html-policy-v1",
    "digest": "<current policy fingerprint>"
  }
}
```

- `integration` must name the active pack definition schema, version, and
  revision.
- `approval` must cite the H3 configuration registry and an H3 configuration
  approval recorded by a human for the project and approved Target set, with
  `automatic_companion: true` explicitly approving automatic companion
  handling.
- `capabilities` must attest the host-owned HtmlWorker and authoring dispatch,
  and the version 1 pack host API. The pack cannot verify these claims; the
  contract is trusted only because the herness boundary supplies it from its
  own registry.
- `policy` must match the current `html-docs host-api capabilities` version and
  digest exactly. A stale or different checkout is unavailable, not a silent
  fallback.

## Versioned status

```bash
python3 adapters/herness/integration.py definition
python3 adapters/herness/integration.py status   # host contract JSON on stdin
```

`status` returns `{"schema":"sdd-herness-integration-status","version":1,...}`
with `declared`, `available`, `state`, `code`, `delegation`, `worker`, and
`pack` fields. It exits `0` only when active, `1` when unavailable, and `2` for
malformed input or usage. It does not read the worktree or environment. An
unavailable result is explicit; it never falls back to parent-authored HTML.
`definition` reports the validated declaration with `declared: true`,
`available: false`, and `state: "definition"`; inspecting the definition does
not activate the capability.

The definition declares the contract but does not implement or enable the
herness HtmlWorker (`capability.worker.enabled_by_definition` is `false`). Later
herness phases must provide the worker and dispatch capability before a host
contract can truthfully attest it. The status is host-attested and does not
replace H3 evaluation, H2 assessment, publication, Git, or CI.

## Codes

Definition: `pack-capability-missing`, `pack-definition-invalid`,
`unsupported-definition-version`, `pack-definition-stale`,
`pack-policy-unavailable`.

Contract: `host-contract-missing`, `host-contract-invalid-json`,
`contract-schema`, `unsupported-contract-version`, `host-mismatch`,
`integration-version`, `integration-revision`, `approval-incomplete`,
`approval-source`, `approval-kind`, `approval-actor`, `approval-targets`,
`approval-automatic`, `capability-missing`, `worker-unavailable`,
`worker-version`, `dispatch-unavailable`, `dispatch-version`,
`policy-bridge-protocol`, `policy-bridge-version`, `policy-version`,
`policy-digest`.
