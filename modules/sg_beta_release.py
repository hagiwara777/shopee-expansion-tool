"""SG manual-preparation release boundary; import never enables operation."""

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


class SGBetaNotAdopted(ValueError):
    pass


def require_sg_beta_operation():
    """Read current canonical state every time, including immediately before output.

    No environment switch or UI checkbox can adopt a release. Activation of
    canonical state remains a separately reviewed formal change.
    """
    try:
        state = json.loads((ROOT / "governance/state.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "governance/schemas/state.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(state, schema)
        allowed = (
            state["markets"]["SG"] == {"operation": "ACTIVE", "development_policy": "ALLOWED"}
            and all(state["capabilities"][name]["lifecycle"] == "ACCEPTED"
                    for name in ("ph.beta.operation", "sg.safety.baseline"))
            and not any(item["blocking"] for item in state["open_items"])
        )
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError):
        raise SGBetaNotAdopted("SG beta operation has not been adopted.") from None
    if not allowed:
        raise SGBetaNotAdopted("SG beta operation has not been adopted.")
