"""Governance v2 generator, verifier, and evidence contracts.

The generator observes.  The verifier evaluates a previously generated context.
Neither operation fetches, changes refs, updates the index, or edits Machine State.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

import jsonschema


SCHEMA_VERSION = "2.0.0"
ENGINE_MAJOR = 2
EXIT_CONTINUE = 0
EXIT_HOLD = 10
EXIT_HARD_STOP = 20
EXIT_USAGE = 64
EXIT_INTERNAL = 70

OBSERVATIONS = {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE", "NOT_RUN"}
CONSEQUENCES = {"CONTINUE", "HOLD", "HARD_STOP"}
SHAREABLE_KEYS = {
    "schema_version",
    "canonical",
    "canonical_sha256",
    "observations",
    "git_identity",
    "volatile",
    "generated_at",
    "records",
    "id",
    "observation",
    "value",
    "reason_code",
    "source_ref",
    "repository_id",
    "state",
    "config_version",
    "config_hashes",
    "classification",
    "components",
    "protected_capabilities",
    "task",
    "head",
    "tree",
    "branch",
    "base",
    "merge_base",
    "dirty",
    "changed_files",
    "status",
    "old_path",
    "new_path",
    "old_mode",
    "new_mode",
    "profile_id",
    "decision",
    "requirements",
    "requirement",
    "level",
    "consequence",
    "evidence_ids",
    "warnings",
    "blockers",
    "verification_input_hash",
    "owner_acceptance_ready",
    "summary_binding",
    "title",
    "sections",
    "acceptance_target",
    "change_scope",
    "non_targets",
    "existing_operations_impact",
    "major_risks",
    "verified_evidence",
    "known_limits",
    "meaning_after_acceptance",
    "rollback",
}


class GovernanceError(RuntimeError):
    """A structured governance failure with a stable reason and exit code."""

    def __init__(self, reason_code: str, message: str, exit_code: int = EXIT_HARD_STOP):
        super().__init__(message)
        self.reason_code = reason_code
        self.safe_message = message
        self.exit_code = exit_code


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GovernanceError("DUPLICATE_JSON_KEY", "JSONに重複キーがあります。")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise GovernanceError("JSON_BOM_FORBIDDEN", "JSONのBOMは許可されません。")
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                GovernanceError("NON_FINITE_NUMBER", f"JSONの非有限数は許可されません: {value}")
            ),
        )
    except GovernanceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("INVALID_JSON", f"JSONを安全に読み取れません: {path.name}") from exc


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _schema_validate(instance: Any, schema: Mapping[str, Any], label: str) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)
    except jsonschema.SchemaError as exc:
        raise GovernanceError("BROKEN_SCHEMA", f"schema自体が不正です: {label}") from exc
    except jsonschema.ValidationError as exc:
        raise GovernanceError("SCHEMA_VALIDATION_FAILED", f"schema検証に失敗しました: {label}") from exc


@dataclass(frozen=True)
class GovernanceBundle:
    root: Path
    manifest: dict[str, Any]
    state: dict[str, Any]
    ownership: dict[str, Any]
    capabilities: dict[str, Any]
    classification: dict[str, Any]
    gates: dict[str, Any]
    profiles: dict[str, Any]
    schemas: dict[str, dict[str, Any]]
    hashes: dict[str, str]

    @property
    def config_version(self) -> str:
        return str(self.manifest["config_version"])


def _records_by_id(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        record_id = str(record.get("id", ""))
        if not record_id or record_id in indexed:
            raise GovernanceError("DUPLICATE_OR_EMPTY_ID", f"{label}に重複または空のIDがあります。")
        indexed[record_id] = record
    return indexed


def _check_dependency_cycles(components: Mapping[str, Mapping[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visiting:
            raise GovernanceError("COMPONENT_DEPENDENCY_CYCLE", "component依存にcycleがあります。")
        if component_id in visited:
            return
        visiting.add(component_id)
        for dependency in components[component_id].get("depends_on", []):
            if dependency not in components:
                raise GovernanceError("UNKNOWN_COMPONENT_REFERENCE", "存在しないcomponent参照があります。")
            visit(dependency)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in components:
        visit(component_id)


def _git_json_at_ref(root: Path, ref: str, relative: str) -> dict[str, Any] | None:
    completed = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{relative}"],
        check=False, capture_output=True, text=True, encoding="utf-8", errors="strict"
    )
    if completed.returncode:
        return None
    try:
        return json.loads(
            completed.stdout,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                GovernanceError("NON_FINITE_NUMBER", "baseline JSON contains a non-finite number")
            ),
        )
    except (json.JSONDecodeError, UnicodeError, GovernanceError) as exc:
        raise GovernanceError("BASELINE_CONFIG_INVALID", "Baseline Governance Config is invalid.") from exc


def _enforce_baseline_policy(root: Path, gates: Mapping[str, Any], capabilities: Mapping[str, Any]) -> None:
    ref = os.environ.get("GOVERNANCE_BASELINE_REF", "refs/remotes/origin/main")
    baseline_gates = _git_json_at_ref(root, ref, "governance/gates.json")
    baseline_capabilities = _git_json_at_ref(root, ref, "governance/capabilities.json")
    if baseline_gates is not None:
        old_ids = {item["id"] for item in baseline_gates.get("gates", [])}
        new_ids = {item["id"] for item in gates.get("gates", [])}
        if not old_ids.issubset(new_ids):
            raise GovernanceError("BASELINE_MANDATORY_GATE_REMOVED", "A baseline mandatory gate was removed.")
    if baseline_capabilities is not None:
        old = {item["id"]: item for item in baseline_capabilities.get("capabilities", [])}
        new = {item["id"]: item for item in capabilities.get("capabilities", [])}
        if not set(old).issubset(new):
            raise GovernanceError("BASELINE_PROTECTED_CAPABILITY_REMOVED", "A baseline protected capability was removed.")
        for capability_id, baseline in old.items():
            current = new[capability_id]
            if not set(baseline.get("gate_ids", [])).issubset(current.get("gate_ids", [])):
                raise GovernanceError("BASELINE_CAPABILITY_GATE_WEAKENED", "A protected capability gate was weakened.")
            if not set(baseline.get("invariants", [])).issubset(current.get("invariants", [])):
                raise GovernanceError("BASELINE_CAPABILITY_INVARIANT_WEAKENED", "A protected capability invariant was weakened.")


def load_bundle(repository: Path) -> GovernanceBundle:
    root = repository.resolve()
    governance_root = root / "governance"
    manifest = load_json(governance_root / "manifest.json")
    if manifest.get("engine_major") != ENGINE_MAJOR:
        raise GovernanceError("UNSUPPORTED_ENGINE_MAJOR", "未対応のGovernance engine majorです。")
    if manifest.get("config_version") != SCHEMA_VERSION:
        raise GovernanceError("UNSUPPORTED_CONFIG_VERSION", "未対応のGovernance Config versionです。")

    hashes: dict[str, str] = {}
    loaded: dict[str, Any] = {}
    for item in manifest.get("files", []):
        relative = item.get("path", "")
        if not relative or relative.startswith(("/", "\\")) or ".." in Path(relative).parts:
            raise GovernanceError("CONFIG_PATH_ESCAPE", "Config pathがbundle外を参照しています。")
        path = governance_root / relative
        document = load_json(path)
        actual = sha256_bytes(canonical_bytes(document))
        if actual != item.get("sha256"):
            raise GovernanceError("CONFIG_HASH_MISMATCH", f"Config hashが一致しません: {relative}")
        hashes[relative] = actual
        loaded[relative] = document

    required = {
        "schemas/state.schema.json",
        "schemas/task-context.schema.json",
        "schemas/evidence.schema.json",
        "schemas/context.schema.json",
        "schemas/verification.schema.json",
        "ownership.json",
        "capabilities.json",
        "classification.json",
        "gates.json",
        "task-profiles.json",
    }
    if not required.issubset(loaded):
        raise GovernanceError("INCOMPLETE_CONFIG_BUNDLE", "Governance Configの必須ファイルが不足しています。")

    state = load_json(governance_root / "state.json")
    schemas = {key: loaded[key] for key in required if key.startswith("schemas/")}
    _schema_validate(state, schemas["schemas/state.schema.json"], "state")
    if state["config_version"] != manifest["config_version"]:
        raise GovernanceError("STATE_CONFIG_VERSION_MISMATCH", "StateとConfigのversionが一致しません。")

    ownership = loaded["ownership.json"]
    capabilities = loaded["capabilities.json"]
    classification = loaded["classification.json"]
    gates = loaded["gates.json"]
    profiles = loaded["task-profiles.json"]
    for label, document in (
        ("ownership", ownership),
        ("capabilities", capabilities),
        ("classification", classification),
        ("gates", gates),
        ("task-profiles", profiles),
    ):
        if document.get("format_version") != SCHEMA_VERSION:
            raise GovernanceError("UNSUPPORTED_CONFIG_FORMAT", f"未対応のConfig formatです: {label}")

    components = _records_by_id(ownership["components"], "components")
    _enforce_baseline_policy(root, gates, capabilities)

    capability_records = _records_by_id(capabilities["capabilities"], "capabilities")
    gate_records = _records_by_id(gates["gates"], "gates")
    _records_by_id(gates["checks"], "checks")
    _records_by_id(profiles["profiles"], "profiles")
    _check_dependency_cycles(components)
    for capability in capability_records.values():
        if capability["market"] not in state["markets"]:
            raise GovernanceError("UNKNOWN_MARKET_REFERENCE", "capabilityの市場参照が不正です。")
        for component_id in capability["components"]:
            if component_id not in components:
                raise GovernanceError("UNKNOWN_COMPONENT_REFERENCE", "capabilityのcomponent参照が不正です。")
        for gate_id in capability["gate_ids"]:
            if gate_id not in gate_records:
                raise GovernanceError("UNKNOWN_GATE_REFERENCE", "capabilityのgate参照が不正です。")

    for capability_id, capability_state in state["capabilities"].items():
        if capability_id not in capability_records:
            raise GovernanceError("UNKNOWN_CAPABILITY_REFERENCE", "Stateに未知のcapabilityがあります。")
        if capability_state["lifecycle"] == "ACCEPTED" and not capability_state["acceptance_refs"]:
            raise GovernanceError("ACCEPTED_WITHOUT_REFERENCE", "受入済みcapabilityに根拠がありません。")
    for market_id, market in state["markets"].items():
        if market["operation"] == "ACTIVE":
            accepted = [
                capability_id
                for capability_id, capability_state in state["capabilities"].items()
                if capability_state["lifecycle"] == "ACCEPTED"
                and capability_records[capability_id]["market"] == market_id
            ]
            if not accepted:
                raise GovernanceError("ACTIVE_MARKET_WITHOUT_CAPABILITY", "ACTIVE市場に受入済みcapabilityがありません。")

    return GovernanceBundle(
        root=root,
        manifest=manifest,
        state=state,
        ownership=ownership,
        capabilities=capabilities,
        classification=classification,
        gates=gates,
        profiles=profiles,
        schemas=schemas,
        hashes=hashes,
    )


def _run_git(repository: Path, arguments: Sequence[str], *, allow_failure: bool = False) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        if allow_failure:
            return None
        raise GovernanceError("GIT_OBSERVATION_FAILED", "Git観測に失敗しました。", EXIT_INTERNAL)
    return completed.stdout.rstrip("\r\n")


def _normalize_remote(remote: str) -> tuple[str, str, str] | None:
    value = remote.strip()
    if not value:
        return None
    if re.match(r"^[^@\s]+@[^:]+:.+$", value):
        host, path = value.split("@", 1)[1].split(":", 1)
    else:
        split = urlsplit(value)
        host = split.hostname or ""
        path = split.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    pieces = path.split("/")
    if len(pieces) != 2 or not host:
        return None
    return host.lower(), pieces[0].lower(), pieces[1].lower()


def _load_anchor() -> tuple[dict[str, Any] | None, str]:
    env_value = os.environ.get("GOVERNANCE_TRUST_ANCHOR_JSON")
    file_value: dict[str, Any] | None = None
    env_anchor: dict[str, Any] | None = None
    if env_value:
        try:
            env_anchor = json.loads(env_value, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, GovernanceError) as exc:
            raise GovernanceError("TRUST_ANCHOR_INVALID", "Trust Anchor環境値が不正です。") from exc
    app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if app_data:
        anchor_path = Path(app_data) / "ShopeeGovernance" / "trust" / "1296080967.json"
        if anchor_path.is_file():
            file_value = load_json(anchor_path)
    if env_anchor is not None and file_value is not None and env_anchor != file_value:
        raise GovernanceError("TRUST_ANCHOR_CONFLICT", "複数Trust Anchorが一致しません。")
    anchor = env_anchor if env_anchor is not None else file_value
    if anchor is None:
        return None, "TRUST_ANCHOR_MISSING"
    required = {
        "anchor_version",
        "provider",
        "host",
        "repository_id",
        "repository_full_name",
        "default_branch",
        "owner_actor_id",
        "bootstrap_formal_commit",
    }
    if set(anchor) != required or anchor.get("anchor_version") != "1.0.0":
        raise GovernanceError("TRUST_ANCHOR_INVALID", "Trust Anchorの契約が不正です。")
    return anchor, "TRUST_ANCHOR_LOADED"


def _path_components(path: str, components: Sequence[Mapping[str, Any]]) -> set[str]:
    normalized = path.replace("\\", "/")
    matched: set[str] = set()
    for component in components:
        if any(fnmatch.fnmatchcase(normalized, pattern) for pattern in component["paths"]):
            matched.add(component["id"])
    return matched


def classify_changes(
    changes: Sequence[Mapping[str, Any]], ownership: Mapping[str, Any]
) -> dict[str, Any]:
    components = ownership["components"]
    matched: set[str] = set()
    unknown_paths: set[str] = set()
    statuses: list[dict[str, Any]] = []
    for change in changes:
        paths = [change.get("old_path"), change.get("new_path")]
        path_matches: set[str] = set()
        for path in (value for value in paths if value):
            current_matches = _path_components(str(path), components)
            if not current_matches:
                unknown_paths.add(str(path))
            path_matches.update(current_matches)
        matched.update(path_matches)
        statuses.append(dict(change))

    indexed = {record["id"]: record for record in components}
    if not changes:
        classification = "GOVERNANCE_ONLY"
    elif unknown_paths:
        classification = "SHARED_CORE"
    else:
        scopes = {indexed[component_id]["scope"] for component_id in matched}
        runtime = {component_id for component_id in matched if indexed[component_id]["scope"].endswith("RUNTIME")}
        if not runtime and scopes <= {"GOVERNANCE", "DOCUMENTATION"}:
            classification = "GOVERNANCE_ONLY"
        elif runtime:
            markets: set[str] = set()
            local_only = True
            for component_id in runtime:
                component = indexed[component_id]
                if component["scope"] != "MARKET_RUNTIME":
                    local_only = False
                markets.update(component["markets"])
            non_runtime = matched - runtime
            if local_only and len(markets) == 1 and not {
                item for item in non_runtime if indexed[item]["scope"] == "GOVERNANCE"
            }:
                classification = "MARKET_LOCAL"
            else:
                classification = "SHARED_CORE"
        else:
            classification = "SHARED_CORE"
    return {
        "classification": classification,
        "components": sorted(matched),
        "unknown_paths": sorted(unknown_paths),
        "changes": statuses,
    }


def _parse_status(repository: Path, base: str | None, head: str) -> list[dict[str, Any]]:
    if base and base != head:
        output = _run_git(repository, ["diff", "--name-status", "-M", f"{base}..{head}"]) or ""
        lines = output.splitlines()
    else:
        output = _run_git(repository, ["status", "--porcelain=v1", "--untracked-files=all"]) or ""
        lines = output.splitlines()
    changes: list[dict[str, Any]] = []
    for line in lines:
        if base and base != head:
            parts = line.split("\t")
            status = parts[0]
            if status.startswith("R") and len(parts) >= 3:
                changes.append({"status": "R", "old_path": parts[1], "new_path": parts[2], "old_mode": None, "new_mode": None})
            elif len(parts) >= 2:
                changes.append({"status": status[0], "old_path": parts[1] if status[0] in {"D"} else None, "new_path": parts[1] if status[0] != "D" else None, "old_mode": None, "new_mode": None})
        else:
            status = line[:2].strip() or "M"
            path_text = line[3:]
            if " -> " in path_text:
                old_path, new_path = path_text.split(" -> ", 1)
                changes.append({"status": "R", "old_path": old_path, "new_path": new_path, "old_mode": None, "new_mode": None})
            else:
                changes.append({"status": status[-1], "old_path": path_text if "D" in status else None, "new_path": None if "D" in status else path_text, "old_mode": None, "new_mode": None})
    return changes


def _protected_capabilities(bundle: GovernanceBundle, classification: Mapping[str, Any]) -> list[str]:
    definitions = {item["id"]: item for item in bundle.capabilities["capabilities"]}
    accepted = {
        capability_id
        for capability_id, state in bundle.state["capabilities"].items()
        if state["lifecycle"] == "ACCEPTED"
    }
    if classification["classification"] == "GOVERNANCE_ONLY":
        return []
    if classification["classification"] == "SHARED_CORE" or classification["unknown_paths"]:
        return sorted(accepted)
    changed = set(classification["components"])
    return sorted(
        capability_id
        for capability_id in accepted
        if changed.intersection(definitions[capability_id]["components"])
    )


def _load_task_context(bundle: GovernanceBundle, path: Path | None, anchor: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if path is None:
        return None
    task = load_json(path)
    _schema_validate(task, bundle.schemas["schemas/task-context.schema.json"], "task-context")
    profiles = {profile["id"] for profile in bundle.profiles["profiles"]}
    gates = {gate["id"] for gate in bundle.gates["gates"]}
    if task["profile_id"] not in profiles or any(gate not in gates for gate in task["additional_gate_ids"]):
        raise GovernanceError("TASK_CONTEXT_REFERENCE_INVALID", "Task Contextの参照が不正です。")
    if anchor and task["repository_id"] != anchor["repository_id"]:
        raise GovernanceError("TASK_CONTEXT_REPOSITORY_MISMATCH", "Task Contextのrepositoryが一致しません。")
    return task


def _safe_record(identifier: str, observation: str, value: Any, reason: str, source: str) -> dict[str, Any]:
    if observation not in OBSERVATIONS:
        raise GovernanceError("INVALID_OBSERVATION", "観測値が不正です。")
    return {"id": identifier, "observation": observation, "value": value, "reason_code": reason, "source_ref": source}


def _assert_shareable(value: Any, key: str | None = None) -> None:
    # JSON schemas are the structural allowlists. This pass rejects unsafe content.
    pass
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            _assert_shareable(child_value, str(child_key))
    elif isinstance(value, list):
        for child in value:
            _assert_shareable(child, None)
    elif isinstance(value, str):
        forbidden = [
            r"(?i)\b[a-z]:[\\/]",
            r"^\\\\",
            r"(?i)file://",
            r"(?<![A-Za-z0-9._-])/(?:home|Users|tmp|var|etc)/",
            r"(?i)(authorization|access[_-]?token|refresh[_-]?token|api[_-]?key)\s*[:=]",
            r"(?i)https?://[^\s/@]+:[^\s/@]+@",
        ]
        if any(re.search(pattern, value) for pattern in forbidden):
            raise GovernanceError("SHAREABLE_CONTENT_LEAK", "共有出力に禁止情報が含まれています。", EXIT_INTERNAL)


def generate_context(
    repository: Path,
    *,
    base: str | None = None,
    provider: Mapping[str, Any] | None = None,
    task_context_path: Path | None = None,
    clock: datetime | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(repository)
    anchor, anchor_reason = _load_anchor()
    head = _run_git(bundle.root, ["rev-parse", "HEAD"])
    tree = _run_git(bundle.root, ["rev-parse", "HEAD^{tree}"])
    branch = _run_git(bundle.root, ["branch", "--show-current"], allow_failure=True) or None
    selected_base = base
    if selected_base is None:
        selected_base = _run_git(bundle.root, ["rev-parse", "refs/remotes/origin/main"], allow_failure=True)
    merge_base = None
    if selected_base:
        merge_base = _run_git(bundle.root, ["merge-base", selected_base, head], allow_failure=True)
    changes = _parse_status(bundle.root, merge_base or selected_base, head)
    classified = classify_changes(changes, bundle.ownership)
    protected = _protected_capabilities(bundle, classified)
    remote = _run_git(bundle.root, ["remote", "get-url", "origin"], allow_failure=True)
    remote_identity = _normalize_remote(remote or "")
    records: list[dict[str, Any]] = []
    if anchor is None:
        records.append(_safe_record("trust-anchor", "UNKNOWN", None, anchor_reason, "trust-anchor"))
        repository_id = None
    else:
        repository_id = anchor["repository_id"]
        expected_remote = _normalize_remote(
            f"https://{anchor['host']}/{anchor['repository_full_name']}.git"
        )
        if remote_identity and remote_identity != expected_remote:
            records.append(_safe_record("repository-remote", "FAIL", None, "REPOSITORY_IDENTITY_MISMATCH", "git"))
        elif remote_identity:
            records.append(_safe_record("repository-remote", "PASS", True, "REMOTE_IDENTITY_MATCH", "git"))
        else:
            records.append(_safe_record("repository-remote", "UNKNOWN", None, "REMOTE_NOT_AVAILABLE", "git"))
        provider_id = (provider or {}).get("repository_id")
        if provider_id is None:
            records.append(_safe_record("provider-repository-id", "UNKNOWN", None, "PROVIDER_NOT_AVAILABLE", "provider"))
        elif str(provider_id) == str(anchor["repository_id"]):
            records.append(_safe_record("provider-repository-id", "PASS", True, "PROVIDER_ID_MATCH", "provider"))
        else:
            records.append(_safe_record("provider-repository-id", "FAIL", None, "REPOSITORY_IDENTITY_MISMATCH", "provider"))
        records.append(_safe_record("trust-anchor", "PASS", True, "TRUST_ANCHOR_LOADED", "trust-anchor"))
    task = _load_task_context(bundle, task_context_path, anchor)
    canonical: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repository_id": repository_id,
        "state": bundle.state,
        "config_version": bundle.config_version,
        "config_hashes": dict(sorted(bundle.hashes.items())),
        "classification": classified["classification"],
        "components": classified["components"],
        "protected_capabilities": protected,
        "task": task,
    }
    canonical_hash = sha256_bytes(canonical_bytes(canonical))
    now = clock or datetime.now(UTC)
    context = {
        "schema_version": SCHEMA_VERSION,
        "canonical": canonical,
        "canonical_sha256": canonical_hash,
        "observations": {
            "git_identity": {
                "head": head,
                "tree": tree,
                "branch": branch,
                "base": selected_base,
                "merge_base": merge_base,
                "dirty": bool(changes),
                "changed_files": changes,
            },
            "records": records,
            "volatile": {"generated_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z")},
        },
    }
    _schema_validate(context, bundle.schemas["schemas/context.schema.json"], "context")
    _assert_shareable(context)
    return context


def evidence_digest(record: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(record))


def load_evidence(bundle: GovernanceBundle, paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        record = load_json(path)
        _schema_validate(record, bundle.schemas["schemas/evidence.schema.json"], "evidence")
        digest = evidence_digest(record)
        if re.fullmatch(r"[0-9a-f]{64}", path.stem) and path.stem != digest:
            raise GovernanceError("EVIDENCE_DIGEST_MISMATCH", "Evidence recordのdigestが一致しません。")
        records.append(record)
    return records


def generate_ci_evidence(repository: Path, gate_id: str) -> tuple[str, dict[str, Any]]:
    """Build one content-addressed PASS record from the current GitHub Actions job."""
    bundle = load_bundle(repository)
    check = next((item for item in bundle.gates["checks"] if item["id"] == gate_id), None)
    if check is None or not check.get("ci_identity"):
        raise GovernanceError("CI_EVIDENCE_GATE_INVALID", "CI Evidence対象gateが不正です。", EXIT_USAGE)
    required = [
        "GITHUB_ACTIONS", "GITHUB_REPOSITORY_ID", "GOVERNANCE_EVIDENCE_SHA", "GITHUB_WORKFLOW_REF",
        "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_ACTOR_ID", "GITHUB_EVENT_NAME",
    ]
    values = {key: os.environ.get(key, "") for key in required}
    if values["GITHUB_ACTIONS"].lower() != "true" or any(not values[key] for key in required[1:]):
        raise GovernanceError("CI_EVIDENCE_ENVIRONMENT_REQUIRED", "GitHub Actionsの検証済み実行環境が必要です。", EXIT_USAGE)
    identity = check["ci_identity"]
    workflow_path = str(identity["workflow_path"])
    if (
        values["GITHUB_EVENT_NAME"] != "pull_request"
        or values["GITHUB_JOB"] != identity["job_id"]
        or f"/{workflow_path}@" not in values["GITHUB_WORKFLOW_REF"]
    ):
        raise GovernanceError("CI_EVIDENCE_IDENTITY_MISMATCH", "CI jobまたはworkflow identityがgate定義と一致しません。", EXIT_HARD_STOP)
    head = _run_git(bundle.root, ["rev-parse", "HEAD"])
    if head != values["GOVERNANCE_EVIDENCE_SHA"]:
        raise GovernanceError("CI_EVIDENCE_HEAD_MISMATCH", "checkout HEADがGitHub Actions対象commitと一致しません。", EXIT_HARD_STOP)
    tree = _run_git(bundle.root, ["rev-parse", "HEAD^{tree}"])
    base = _run_git(bundle.root, ["rev-parse", "refs/remotes/origin/main"], allow_failure=True)
    merge_base = _run_git(bundle.root, ["merge-base", base, head], allow_failure=True) if base else None
    changes = _parse_status(bundle.root, merge_base or base, head)
    classification = classify_changes(changes, bundle.ownership)
    profile = next(item for item in bundle.profiles["profiles"] if item["id"] == "formal-acceptance")
    registry_hash = sha256_bytes(canonical_bytes(bundle.hashes))
    record: dict[str, Any] = {
        "evidence_id": f"ci-{gate_id}-{values['GITHUB_RUN_ID']}-{values['GITHUB_RUN_ATTEMPT']}",
        "schema_version": SCHEMA_VERSION,
        "kind": "TEST",
        "repository_id": values["GITHUB_REPOSITORY_ID"],
        "object_format": "sha1",
        "tested_commit": head,
        "tested_tree": tree,
        "base_commit": base,
        "merge_base": merge_base,
        "capability_ids": [],
        "component_ids": classification["components"],
        "component_manifest": None,
        "state_schema_hash": bundle.hashes["schemas/state.schema.json"],
        "config_version": bundle.config_version,
        "registry_hash": registry_hash,
        "gate_id": gate_id,
        "gate_definition_hash": sha256_bytes(canonical_bytes(check)),
        "profile_hash": sha256_bytes(canonical_bytes(profile)),
        "test_plan_hash": sha256_bytes(canonical_bytes({"test_plan_id": check["test_plan_id"]})),
        "test_source_hash": sha256_file(bundle.root / workflow_path),
        "fixture_hash": None,
        "environment": {"provider": "github", "runner_os": os.environ.get("RUNNER_OS", "unknown")},
        "runner_version": values["GITHUB_RUN_ATTEMPT"],
        "observation": "PASS",
        "reason_codes": ["CI_JOB_SUCCESS"],
        "report_sha256": None,
        "provenance": "CI",
        "executed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "external_validity": None,
        "source": {
            "type": "GITHUB_ACTIONS", "provider": "github", "workflow_path": workflow_path,
            "workflow_ref": values["GITHUB_WORKFLOW_REF"], "job_id": values["GITHUB_JOB"],
            "check_name": identity["check_name"], "run_id": values["GITHUB_RUN_ID"],
            "run_attempt": values["GITHUB_RUN_ATTEMPT"], "actor_id": values["GITHUB_ACTOR_ID"],
            "event_name": values["GITHUB_EVENT_NAME"], "commit": head, "result": "SUCCESS",
        },
    }
    _schema_validate(record, bundle.schemas["schemas/evidence.schema.json"], "evidence")
    _assert_shareable(record)
    return evidence_digest(record), record


def _ci_evidence_matches(check: Mapping[str, Any], record: Mapping[str, Any], current_head: str) -> bool:
    source = record.get("source", {})
    identity = check.get("ci_identity", {})
    return (
        source.get("type") == "GITHUB_ACTIONS"
        and source.get("provider") == identity.get("provider")
        and source.get("workflow_path") == identity.get("workflow_path")
        and source.get("job_id") == identity.get("job_id")
        and source.get("check_name") == identity.get("check_name")
        and source.get("commit") == current_head
        and source.get("result") == "SUCCESS"
    )


def _required_checks(bundle: GovernanceBundle, context: Mapping[str, Any], profile_id: str) -> list[Mapping[str, Any]]:
    classification = context["canonical"]["classification"]
    components = set(context["canonical"]["components"])
    protected = set(context["canonical"]["protected_capabilities"])
    result: list[Mapping[str, Any]] = []
    for check in bundle.gates["checks"]:
        applies = check["applies_when"]
        if applies.get("profiles") and profile_id not in applies["profiles"]:
            continue
        if applies.get("classifications") and classification not in applies["classifications"]:
            continue
        if applies.get("components") and not components.intersection(applies["components"]):
            continue
        if applies.get("capabilities") and not protected.intersection(applies["capabilities"]):
            continue
        result.append(check)
    task = context["canonical"].get("task")
    if task:
        known = {item["id"]: item for item in bundle.gates["checks"]}
        for gate_id in task["additional_gate_ids"]:
            gate = next(item for item in bundle.gates["gates"] if item["id"] == gate_id)
            for requirement_id in gate["evidence_requirements"]:
                if requirement_id in known and known[requirement_id] not in result:
                    result.append(known[requirement_id])
    return result


def _evidence_for_check(
    bundle: GovernanceBundle,
    check: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    profile_id: str,
    clock: datetime | None = None,
) -> tuple[str, list[str], str]:
    matches = [record for record in evidence if record.get("gate_id") == check["id"]]
    if not matches:
        return "NOT_RUN", [], "EVIDENCE_MISSING"
    current_head = context["observations"]["git_identity"]["head"]
    current_tree = context["observations"]["git_identity"]["tree"]
    repository_id = context["canonical"].get("repository_id")
    state_schema_hash = context["canonical"]["config_hashes"].get("schemas/state.schema.json")
    registry_hash = sha256_bytes(canonical_bytes(context["canonical"]["config_hashes"]))
    gate_definition_hash = sha256_bytes(canonical_bytes(check))
    profile = next(item for item in bundle.profiles["profiles"] if item["id"] == profile_id)
    profile_hash = sha256_bytes(canonical_bytes(profile))
    test_plan_hash = sha256_bytes(canonical_bytes({"test_plan_id": check["test_plan_id"]}))
    valid: list[Mapping[str, Any]] = []
    for record in matches:
        validity = record.get("external_validity")
        if validity and validity.get("not_after"):
            try:
                expires = datetime.fromisoformat(str(validity["not_after"]).replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
            except ValueError:
                continue
            if (clock or datetime.now(UTC)) > expires:
                continue
        if record.get("kind") == "OVERRIDE":
            anchor, _ = _load_anchor()
            source = record.get("source", {})
            if (
                anchor is not None
                and record.get("provenance") == "GITHUB_OWNER"
                and record.get("observation") == "PASS"
                and record.get("tested_commit") == current_head
                and source.get("head") == current_head
                and source.get("authority") == "repository-owner"
                and str(source.get("actor_id")) == str(anchor["owner_actor_id"])
            ):
                valid.append(record)
            continue
        if record["provenance"] not in check["accepted_provenance"]:
            continue
        if record["provenance"] == "CI" and not _ci_evidence_matches(check, record, current_head):
            continue
        if str(record["repository_id"]) != str(repository_id):
            continue
        if check["reuse_policy"] == "CURRENT_HEAD_ONLY" and record["tested_commit"] != current_head:
            continue
        if check["reuse_policy"] == "BINDING_MATCH" and any((
            record["tested_commit"] != current_head,
            record["tested_tree"] != current_tree,
            record["state_schema_hash"] != state_schema_hash,
            record["registry_hash"] != registry_hash,
            record["gate_definition_hash"] != gate_definition_hash,
            record["profile_hash"] != profile_hash,
            record["test_plan_hash"] != test_plan_hash,
        )):
            continue
        if record["observation"] == "FAIL":
            return "FAIL", [record["evidence_id"]], "EVIDENCE_FAILURE"
        if record["observation"] == "PASS":
            valid.append(record)
    if valid:
        return "PASS", [record["evidence_id"] for record in valid], "EVIDENCE_BOUND"
    return "UNKNOWN", [record["evidence_id"] for record in matches], "STALE_BINDING"


def _owner_evidence_matches(
    evidence: Sequence[Mapping[str, Any]], verification_input_hash: str, owner_actor_id: str
) -> tuple[bool, str]:
    records = [record for record in evidence if record.get("kind") == "OWNER_ACCEPTANCE"]
    if not records:
        return False, "OWNER_ACCEPTANCE_REQUIRED"
    for record in records:
        source = record.get("source", {})
        if (
            record.get("provenance") == "GITHUB_OWNER"
            and record.get("observation") == "PASS"
            and str(source.get("actor_id")) == str(owner_actor_id)
            and source.get("verification_input_hash") == verification_input_hash
            and bool(source.get("summary_binding"))
        ):
            return True, "OWNER_ACCEPTANCE_BOUND"
    return False, "OWNER_ACCEPTANCE_BINDING_MISMATCH"


def verify_context(
    repository: Path,
    context: Mapping[str, Any],
    *,
    profile_id: str,
    evidence: Sequence[Mapping[str, Any]] = (),
    clock: datetime | None = None,
    provider: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(repository)
    _schema_validate(context, bundle.schemas["schemas/context.schema.json"], "context")
    if sha256_bytes(canonical_bytes(context["canonical"])) != context["canonical_sha256"]:
        raise GovernanceError("CONTEXT_DIGEST_MISMATCH", "Contextのcanonical digestが一致しません。")
    profiles = {item["id"]: item for item in bundle.profiles["profiles"]}
    if profile_id not in profiles:
        raise GovernanceError("UNKNOWN_PROFILE", "未知のtask profileです.", EXIT_USAGE)
    requirements: list[dict[str, Any]] = []
    decision = "CONTINUE"
    warnings: list[str] = []
    blockers: list[str] = []
    if profiles[profile_id].get("task_context_required") and context["canonical"].get("task") is None:
        if decision != "HARD_STOP":
            decision = "HOLD"
        blockers.append("TASK_CONTEXT_REQUIRED")


    observation_map = {item["id"]: item for item in context["observations"]["records"]}
    hard_stop_reasons = {
        item["reason_code"]
        for item in observation_map.values()
        if item["observation"] == "FAIL"
    }
    if hard_stop_reasons:
        decision = "HARD_STOP"
        blockers.extend(sorted(hard_stop_reasons))

    anchor_observation = observation_map.get("trust-anchor", {})
    if anchor_observation.get("observation") != "PASS" and decision != "HARD_STOP":
        decision = "HOLD"
        blockers.append(anchor_observation.get("reason_code", "TRUST_ANCHOR_MISSING"))

    if profile_id == "formal-acceptance":
        provider_identity = observation_map.get("provider-repository-id", {})
        if provider_identity.get("observation") != "PASS" and decision != "HARD_STOP":
            decision = "HOLD"
            blockers.append("PROVIDER_REPOSITORY_ID_REQUIRED")

    for check in _required_checks(bundle, context, profile_id):
        observation, evidence_ids, reason = _evidence_for_check(bundle, check, evidence, context, profile_id, clock)
        consequence = "CONTINUE"
        if observation in {"NOT_RUN", "UNKNOWN"}:
            consequence = "HOLD"
        elif observation == "FAIL":
            consequence = "HARD_STOP"
        if consequence == "HARD_STOP":
            decision = "HARD_STOP"
            blockers.append(reason)
        elif consequence == "HOLD" and decision != "HARD_STOP":
            decision = "HOLD"
            blockers.append(reason)
        requirements.append(
            {
                "id": check["id"],
                "requirement": "MANDATORY",
                "level": "MANDATORY",
                "observation": observation,
                "consequence": consequence,
                "reason_code": reason,
                "evidence_ids": evidence_ids,
            }
        )

    owner_ready = (
        profile_id == "formal-acceptance"
        and decision == "CONTINUE"
        and bool(requirements)
        and all(item["observation"] == "PASS" for item in requirements)
    )
    verification_input = {
        "context_sha256": context["canonical_sha256"],
        "profile_id": profile_id,
        "requirements": requirements,
        "provider": provider or {},
    }
    verification_input_hash = sha256_bytes(canonical_bytes(verification_input))
    if owner_ready:
        current_anchor, _ = _load_anchor()
        if current_anchor is None:
            decision = "HOLD"
            blockers.append("TRUST_ANCHOR_MISSING")
            owner_ready = False
        else:
            accepted, reason = _owner_evidence_matches(
                evidence, verification_input_hash, str(current_anchor["owner_actor_id"])
            )
            if not accepted:
                decision = "HOLD"
                blockers.append(reason)

    result = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "decision": decision,
        "requirements": requirements,
        "warnings": warnings,
        "blockers": sorted(set(blockers)),
        "verification_input_hash": verification_input_hash,
        "owner_acceptance_ready": owner_ready,
    }
    _schema_validate(result, bundle.schemas["schemas/verification.schema.json"], "verification")
    _assert_shareable(result)
    return result


def build_owner_acceptance_summary(
    verification: Mapping[str, Any], summary_input: Mapping[str, Any]
) -> dict[str, Any]:
    if not verification.get("owner_acceptance_ready") or verification.get("decision") == "HARD_STOP":
        raise GovernanceError(
            "OWNER_ACCEPTANCE_NOT_READY",
            "mandatory technical gate未完了のためOwner Acceptanceを要求できません。",
            EXIT_HOLD,
        )
    required_sections = [
        "acceptance_target",
        "change_scope",
        "non_targets",
        "existing_operations_impact",
        "major_risks",
        "verified_evidence",
        "known_limits",
        "meaning_after_acceptance",
        "rollback",
    ]
    if set(summary_input) != set(required_sections) or any(not summary_input[key] for key in required_sections):
        raise GovernanceError("OWNER_SUMMARY_INCOMPLETE", "Owner Acceptance Summaryの必須説明が不足しています。")
    sections = {key: summary_input[key] for key in required_sections}
    binding = sha256_bytes(
        canonical_bytes(
            {
                "verification_input_hash": verification["verification_input_hash"],
                "sections": sections,
            }
        )
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "title": "Owner Acceptance Summary",
        "sections": sections,
        "summary_binding": binding,
    }
    _assert_shareable(result)
    return result


def _context_markdown(context: Mapping[str, Any]) -> str:
    canonical = context["canonical"]
    git = context["observations"]["git_identity"]
    lines = [
        "# Governance Context",
        "",
        f"- repository_id: {canonical['repository_id'] or 'UNVERIFIED'}",
        f"- config_version: {canonical['config_version']}",
        f"- classification: {canonical['classification']}",
        f"- HEAD: {git['head']}",
        f"- branch: {git['branch'] or '(detached)'}",
        f"- protected capabilities: {', '.join(canonical['protected_capabilities']) or '(none)'}",
        "",
        "## Observations",
        "",
    ]
    for record in context["observations"]["records"]:
        lines.append(f"- {record['id']}: {record['observation']} ({record['reason_code']})")
    return "\n".join(lines) + "\n"


def _verification_markdown(result: Mapping[str, Any]) -> str:
    lines = ["# Governance Verification", "", f"- profile: {result['profile_id']}", f"- decision: {result['decision']}", "", "## Requirements", ""]
    for requirement in result["requirements"]:
        lines.append(f"- {requirement['id']}: {requirement['observation']} / {requirement['consequence']}")
    if result["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in result["blockers"])
    return "\n".join(lines) + "\n"


def _write_output(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _read_provider(path: str | None) -> dict[str, Any] | None:
    return load_json(Path(path)) if path else None


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="governance-v2")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--repository", default=".")
    generate = subparsers.add_parser("generate")
    generate.add_argument("--repository", default=".")
    generate.add_argument("--output-dir", default="outputs/governance")
    generate.add_argument("--base")
    generate.add_argument("--provider")
    generate.add_argument("--task-context")
    ci_evidence = subparsers.add_parser("ci-evidence")
    ci_evidence.add_argument("--repository", default=".")
    ci_evidence.add_argument("--gate-id", required=True)
    ci_evidence.add_argument("--output-dir", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--repository", default=".")
    verify.add_argument("--context", required=True)
    verify.add_argument("--profile", required=True)
    verify.add_argument("--output-dir", default="outputs/governance")
    verify.add_argument("--provider")
    verify.add_argument("--evidence", action="append", default=[])
    summary = subparsers.add_parser("owner-summary")
    summary.add_argument("--verification", required=True)
    summary.add_argument("--input", required=True)
    summary.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _cli_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            load_bundle(Path(args.repository))
            print("PASS: governance v2 config")
            return EXIT_CONTINUE
        if args.command == "generate":
            context = generate_context(
                Path(args.repository),
                base=args.base,
                provider=_read_provider(args.provider),
                task_context_path=Path(args.task_context) if args.task_context else None,
            )
            output = Path(args.output_dir)
            _write_output(output / "context.json", canonical_bytes(context))
            _write_output(output / "context.md", _context_markdown(context).encode("utf-8"))
            print("PASS: governance context generated")
            return EXIT_CONTINUE
        if args.command == "ci-evidence":
            digest, record = generate_ci_evidence(Path(args.repository), args.gate_id)
            output = Path(args.output_dir) / f"{digest}.json"
            _write_output(output, canonical_bytes(record))
            print(f"PASS: CI evidence generated for {args.gate_id}: {output.name}")
            return EXIT_CONTINUE
        if args.command == "verify":
            repository = Path(args.repository)
            bundle = load_bundle(repository)
            context = load_json(Path(args.context))
            records = load_evidence(bundle, [Path(item) for item in args.evidence])
            result = verify_context(
                repository,
                context,
                profile_id=args.profile,
                evidence=records,
                provider=_read_provider(args.provider),
            )
            output = Path(args.output_dir)
            _write_output(output / "verification.json", canonical_bytes(result))
            _write_output(output / "verification.md", _verification_markdown(result).encode("utf-8"))
            print(f"GOVERNANCE_DECISION: {result['decision']}")
            return {"CONTINUE": EXIT_CONTINUE, "HOLD": EXIT_HOLD, "HARD_STOP": EXIT_HARD_STOP}[result["decision"]]
        if args.command == "owner-summary":
            result = build_owner_acceptance_summary(
                load_json(Path(args.verification)), load_json(Path(args.input))
            )
            _write_output(Path(args.output), canonical_bytes(result))
            print("PASS: owner acceptance summary generated")
            return EXIT_CONTINUE
    except GovernanceError as exc:
        print(f"{exc.reason_code}: {exc.safe_message}", file=sys.stderr)
        return exc.exit_code
    except SystemExit as exc:
        return int(exc.code)
    except Exception:
        print("UNEXPECTED_INTERNAL_ERROR: 詳細はlocal diagnosticsで確認してください。", file=sys.stderr)
        return EXIT_INTERNAL
    return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
