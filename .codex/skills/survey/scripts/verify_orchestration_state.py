#!/usr/bin/env python3
"""Verify Codex survey orchestration evidence.

Usage:
  python3 verify_orchestration_state.py <slug> [--repo-root /path/to/terry-surveys]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_REPO_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
REQUIRED_AGENTS = [
    "deep_researcher_foundations",
    "deep_researcher_frontier",
    "critical_analyst",
    "book_writer",
    "image_curator",
    "fact_checker",
    "qa_reviewer",
]
REQUIRED_GATES = [
    "scaffold",
    "survey_json",
    "research_shards",
    "analysis",
    "writing",
    "images",
    "factcheck",
    "qa",
]
PLACEHOLDER_AGENT_ID_RE = re.compile(
    r"^(local-codex|placeholder|mock|manual|single-agent|self|none)(?:[-_]|$)",
    re.I,
)


def repo_root(explicit: str | None) -> Path:
    root = Path(explicit).expanduser().resolve() if explicit else DEFAULT_REPO_ROOT
    if not (root / "build.py").exists() or not (root / "surveys").is_dir():
        raise SystemExit(f"ERROR: repo root is not terry-surveys: {root}")
    return root


def load(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: invalid JSON ({exc})")
        return None


def agent_ids(entry: dict) -> list[str]:
    values: list[str] = []
    single = entry.get("agent_id")
    if isinstance(single, str) and single.strip():
        values.append(single.strip())
    many = entry.get("agent_ids")
    if isinstance(many, list):
        values.extend(str(item).strip() for item in many if str(item).strip())
    return values


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--repo-root")
    args = parser.parse_args(argv)
    root = repo_root(args.repo_root)
    survey_dir = root / "surveys" / args.slug
    state_path = survey_dir / "_workspace" / "orchestration_state.json"
    errors: list[str] = []
    if not state_path.exists():
        errors.append("missing _workspace/orchestration_state.json")
    state = load(state_path, errors) if state_path.exists() else None

    if isinstance(state, dict):
        if state.get("slug") != args.slug:
            errors.append(f"state slug mismatch: {state.get('slug')!r}")
        if state.get("mode") not in {"full_survey", "major_refresh", "exhaustive_refresh"}:
            errors.append(f"unexpected mode: {state.get('mode')!r}")
        agents = state.get("agents")
        if not isinstance(agents, dict):
            errors.append("state.agents missing or not an object")
        else:
            for role in REQUIRED_AGENTS:
                entry = agents.get(role)
                if not isinstance(entry, dict):
                    errors.append(f"missing agent state: {role}")
                    continue
                status = entry.get("status")
                if status not in {"completed", "blocked", "running", "pending"}:
                    errors.append(f"{role}: invalid status {status!r}")
                if status == "completed" and not entry.get("artifacts"):
                    errors.append(f"{role}: completed without artifacts")
                ids = agent_ids(entry)
                if status in {"completed", "running"} and not ids:
                    errors.append(f"{role}: missing agent_id evidence")
                for agent_id in ids:
                    if PLACEHOLDER_AGENT_ID_RE.search(agent_id):
                        errors.append(f"{role}: placeholder agent_id is not orchestration evidence: {agent_id!r}")
                if status == "blocked" and not entry.get("blocked_reason"):
                    errors.append(f"{role}: blocked state requires blocked_reason")

        gates = state.get("gates")
        if not isinstance(gates, dict):
            errors.append("state.gates missing or not an object")
        else:
            for gate in REQUIRED_GATES:
                if gate not in gates:
                    errors.append(f"missing gate state: {gate}")
            release = gates.get("release")
            qa = gates.get("qa")
            if release == "complete" and qa != "complete":
                errors.append("release gate complete before qa gate complete")

        tasks = state.get("tasks")
        if tasks is not None and not isinstance(tasks, list):
            errors.append("state.tasks must be a list when present")
        if isinstance(tasks, list):
            for task in tasks:
                if not isinstance(task, dict):
                    errors.append("state.tasks contains non-object item")
                    continue
                for field in ("id", "owner", "status", "artifacts"):
                    if field not in task:
                        errors.append(f"task missing {field}: {task.get('id')!r}")

    if errors:
        print("ERRORS:")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"OK: orchestration state passed for {args.slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
