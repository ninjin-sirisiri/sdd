from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


PACK_ROOT = Path(__file__).resolve().parents[1]
POLICY_TIMEOUT_SECONDS = 10


class AdapterInputError(ValueError):
    """A host payload cannot be translated to the policy contract."""


class PolicyExecutionError(RuntimeError):
    """The common policy CLI could not return a valid result."""


def invoke_policy(request: dict[str, Any]) -> dict[str, Any]:
    """Invoke the shared policy CLI without involving a shell."""

    command = [sys.executable, str(PACK_ROOT / "scripts" / "html-docs"), "edit-check"]
    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=POLICY_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PolicyExecutionError(
            "the html-docs policy timed out; run html-docs doctor and check the adapter setup"
        ) from exc
    except OSError as exc:
        raise PolicyExecutionError(
            f"the html-docs policy could not be invoked: {exc}; "
            "run html-docs doctor and check the adapter setup"
        ) from exc

    try:
        result = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PolicyExecutionError(
            "the html-docs policy returned invalid JSON; "
            "run html-docs doctor and check the adapter setup"
        ) from exc
    if not isinstance(result, dict) or result.get("decision") not in {"allow", "deny"}:
        raise PolicyExecutionError(
            "the html-docs policy returned an invalid decision; "
            "run html-docs doctor and check the adapter setup"
        )
    if completed.returncode not in {0, 1}:
        message = result.get("message")
        detail = message if isinstance(message, str) and message else "execution failure"
        raise PolicyExecutionError(
            f"the html-docs policy failed: {detail}; "
            "run html-docs doctor and check the adapter setup"
        )
    return result
