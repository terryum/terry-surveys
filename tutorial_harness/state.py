"""Durable DAG and artifact contracts for tutorial production."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from harness_runtime import ownership_conflicts, revalidate_inputs, snapshot_inputs

STATE_REL = Path("_workspace/tutorial_harness_state.json")
TASK_STATUSES = {"pending", "running", "completed", "blocked", "skipped"}
PLACEHOLDER_AGENT = re.compile(r"^(local|placeholder|mock|manual|single-agent|self|none)(?:[-_]|$)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root(path: str | Path | None = None) -> Path:
    root = Path(path or Path.cwd()).expanduser().resolve()
    if not (root / "build.py").is_file() or not (root / "surveys").is_dir():
        raise ValueError(f"not a terry-surveys repository: {root}")
    return root


def tutorial_dir(root: Path, slug: str) -> Path:
    path = root / "surveys" / slug
    if not path.is_dir():
        raise FileNotFoundError(f"tutorial not found: {path}")
    data = json.loads((path / "survey.json").read_text(encoding="utf-8"))
    if data.get("content_type", "survey") != "tutorial":
        raise ValueError(f"content is not a tutorial: {slug}")
    return path


def config(path: Path) -> dict[str, Any]:
    return json.loads((path / "survey.json").read_text(encoding="utf-8"))


def chapter_rows(path: Path) -> list[dict[str, Any]]:
    return [chapter for part in config(path).get("parts", []) for chapter in part.get("chapters", [])]


def chapter_numbers(path: Path) -> list[int]:
    numbers = sorted({int(row["num"]) for row in chapter_rows(path) if row.get("num") is not None})
    if not numbers:
        raise ValueError("tutorial roadmap has no chapters")
    return numbers


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ready_chapter_digests(path: Path, excluded: set[int]) -> dict[str, str]:
    result = {}
    for row in chapter_rows(path):
        chapter = int(row["num"])
        if row.get("status", "ready") != "ready" or chapter in excluded:
            continue
        for lang in ("ko", "en"):
            rel = f"book/{lang}/ch{chapter:02d}.md"
            candidate = path / rel
            if candidate.is_file():
                result[rel] = _digest(candidate)
    return result


def verify_protected(path: Path, protected: dict[str, str]) -> None:
    changed = [rel for rel, digest in protected.items() if not (path / rel).is_file() or _digest(path / rel) != digest]
    if changed:
        raise ValueError("non-target ready chapters changed: " + ", ".join(changed))


def _task(task_id: str, phase: str, owner: str, dependencies: Iterable[str], artifacts: Iterable[str], brief: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "phase": phase,
        "owner": owner,
        "status": "pending",
        "dependencies": list(dependencies),
        "artifacts": list(artifacts),
        "write_scopes": list(artifacts),
        "brief": brief,
        "attempt": 0,
        "agent_ids": [],
        "started_at": None,
        "completed_at": None,
        "blocked_reason": None,
    }


def build_tasks(chapters: Iterable[int]) -> list[dict[str, Any]]:
    chapters = list(chapters)
    tasks = [
        _task("normalize-input", "normalize", "curriculum_architect", [], ["_workspace/inputs/input_manifest.md"], "Confirm the normalized authoring contract and keep imported material briefing-only."),
        _task("roadmap", "roadmap", "curriculum_architect", ["normalize-input"], ["_tutorial/roadmap.md", "survey.json"], "Define audience, final goal, first success, prerequisites, chapter flow, and planned/ready states."),
        _task("version-research", "research", "source_version_researcher", ["roadmap"], ["_tutorial/environment_matrix.json", "_tutorial/source_ledger.jsonl"], "Verify supported versions and each installation/API path against official documentation."),
    ]
    qa_ids = []
    for chapter in chapters:
        suffix = f"ch{chapter:02d}"
        lab = f"lab-{suffix}"
        write = f"write-{suffix}"
        verify = f"verify-{suffix}"
        qa = f"qa-{suffix}"
        qa_ids.append(qa)
        tasks.extend([
            _task(lab, "lab", "lab_builder", ["version-research"], [f"_tutorial/chapter_packets/{suffix}.json", f"labs/{suffix}/manifest.json"], f"Build chapter {chapter} around a small observable result and explicit recovery paths."),
            _task(write, "write", "chapter_writer", [lab], [f"book/ko/{suffix}.md", f"book/en/{suffix}.md"], f"Write Korean and English together from the chapter packet; put the first action within 200 rough words."),
            _task(verify, "verify", "example_verifier", [write], [f"_quality/example_verification/{suffix}.json"], f"Check official links, syntax, and only safe lightweight smoke tests for chapter {chapter}."),
            _task(qa, "qa", "pedagogy_reviewer", [verify], [f"_quality/pedagogy/{suffix}.json"], f"Independently review action flow, cognitive load, translation parity, and transitions for chapter {chapter}."),
        ])
    tasks.append(_task("deploy-preview", "release", "release_orchestrator", qa_ids, ["_quality/releases/preview.json"], "Commit scoped source, deploy the Access-protected preview, update the private registry entry, and verify the access matrix."))
    for task in tasks:
        if task["phase"] == "lab":
            task["write_scopes"].append(f"labs/{task['id'].rsplit('-', 1)[-1]}")
        if task["phase"] == "write":
            # Writers update readiness in one shared config: serialize those writes.
            task["write_scopes"].append("survey.json")
        task["inputs"] = _input_selectors(task)
    return tasks


def new_state(root: Path, slug: str, selected: Iterable[int] | None = None) -> dict[str, Any]:
    path = tutorial_dir(root, slug)
    available = chapter_numbers(path)
    selection_mode = "selected" if selected is not None else "all"
    targets = sorted(set(int(item) for item in (selected or available)))
    unknown = sorted(set(targets) - set(available))
    if unknown:
        raise ValueError(f"unknown tutorial chapters: {unknown}")
    stamp = now()
    return {
        "schema_version": "2.1",
        "project_root": str(root.resolve()),
        "revision": 0,
        "run_id": str(uuid.uuid4()),
        "slug": slug,
        "status": "running",
        "selected_chapters": targets,
        "selection_mode": selection_mode,
        "max_parallel": 3,
        "created_at": stamp,
        "updated_at": stamp,
        "tasks": build_tasks(targets),
        "protected_ready_chapters": ready_chapter_digests(path, set(targets)),
        "quality": {"last_scorecard": None},
        "release": {"preview": "pending", "production": "pending", "blocked_reason": None},
    }


def state_path(root: Path, slug: str) -> Path:
    return tutorial_dir(root, slug) / STATE_REL


def validate_state(state: dict[str, Any]) -> None:
    required = {"schema_version", "revision", "run_id", "slug", "status", "selected_chapters", "tasks", "quality", "release"}
    missing = required - set(state)
    if missing:
        raise ValueError(f"tutorial state missing fields: {sorted(missing)}")
    if state["schema_version"] not in {"1.0", "2.0", "2.1"}:
        raise ValueError("unsupported tutorial state schema")
    ids = [task.get("id") for task in state["tasks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate tutorial task ids")
    known = set(ids)
    for task in state["tasks"]:
        if task.get("status") not in TASK_STATUSES:
            raise ValueError(f"invalid task status: {task.get('id')}")
        unknown = set(task.get("dependencies", [])) - known
        if unknown:
            raise ValueError(f"task {task.get('id')} has unknown dependencies: {sorted(unknown)}")


def save_state(root: Path, state: dict[str, Any], replace: bool = False) -> Path:
    validate_state(state)
    path = state_path(root, state["slug"])
    path.parent.mkdir(parents=True, exist_ok=True)
    current_revision = None
    if path.exists():
        current_revision = int(json.loads(path.read_text(encoding="utf-8")).get("revision", 0))
    if current_revision is not None and not replace and current_revision != int(state.get("revision", 0)):
        raise ValueError("stale tutorial state revision")
    state["revision"] = (current_revision if current_revision is not None else int(state.get("revision", 0))) + 1
    state["updated_at"] = now()
    handle, temporary = tempfile.mkstemp(prefix="tutorial-state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def load_state(root: Path, slug: str) -> dict[str, Any]:
    state = json.loads(state_path(root, slug).read_text(encoding="utf-8"))
    validate_state(state)
    return state


def _by_id(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in state["tasks"]:
        if task["id"] == task_id:
            return task
    raise KeyError(task_id)


def ready_tasks(state: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    completed = {task["id"] for task in state["tasks"] if task["status"] in {"completed", "skipped"}}
    capacity = max(0, int(state.get("max_parallel", 3)) - sum(task["status"] == "running" for task in state["tasks"]))
    if limit is not None:
        capacity = min(capacity, limit)
    running_scopes = [scope for task in state["tasks"] if task["status"] == "running" for scope in task.get("write_scopes", task["artifacts"])]
    ready = []
    for task in state["tasks"]:
        if task["status"] != "pending" or not set(task["dependencies"]) <= completed:
            continue
        scopes = task.get("write_scopes", task["artifacts"])
        if ownership_conflicts(scopes, running_scopes):
            continue
        ready.append(task)
        running_scopes.extend(scopes)
        if len(ready) >= capacity:
            break
    return ready if capacity else []


def _input_selectors(task: dict[str, Any]) -> list[dict[str, Any]]:
    content = lambda path, **extra: {"root": "content", "path": path, **extra}
    selectors = [
        {"root": "repo", "path": f".codex/skills/tutorial/{rel}"}
        for rel in ("SKILL.md", "references/orchestration.md", "references/role-contracts.md")
    ]
    selectors.append(content("_workspace/decisions.md"))
    phase = task["phase"]
    if phase == "normalize":
        selectors.extend([content("_workspace/inputs", exclude_paths=["input_manifest.md"]), content("_workspace/inputs/input_manifest.md")])
    elif phase in {"roadmap", "research"}:
        selectors.extend([content("_workspace/inputs/input_manifest.md"), content("survey.json", ignore_keys=["status"])])
        if phase == "research":
            selectors.append(content("_tutorial/roadmap.md"))
    elif phase == "release":
        selectors.extend([content("book"), content("survey.json"), content("_quality/pedagogy"), content("_quality/example_verification")])
        selectors.append({"root": "repo", "path": ".codex/skills/tutorial/references/quality-and-release.md"})
    else:
        chapter = int(task["id"].rsplit("ch", 1)[1])
        suffix = f"ch{chapter:02d}"
        selectors.extend([content("survey.json", chapter=chapter, ignore_keys=["status"]), content("_tutorial/source_ledger.jsonl", chapter=chapter)])
        if phase in {"lab", "verify"}:
            selectors.append(content("_tutorial/environment_matrix.json"))
        if phase == "lab":
            selectors.append(content("_tutorial/roadmap.md"))
        else:
            selectors.append(content(f"_tutorial/chapter_packets/{suffix}.json"))
            selectors.append(content(f"labs/{suffix}"))
        if phase in {"verify", "qa"}:
            selectors.extend(content(f"book/{lang}/{suffix}.md") for lang in ("ko", "en"))
        if phase == "qa":
            selectors.append(content(f"_quality/example_verification/{suffix}.json"))
    return selectors


def _output_selectors(task: dict[str, Any]) -> list[dict[str, Any]]:
    paths = list(task["artifacts"])
    if task["phase"] == "lab":
        paths.append(f"labs/{task['id'].rsplit('-', 1)[-1]}")
    return [
        {"root": "content", "path": path, **({"ignore_keys": ["status"]} if path == "survey.json" else {})}
        for path in paths
    ]


def start_task(state: dict[str, Any], task_id: str, agent_id: str, root: Path | None = None) -> None:
    task = _by_id(state, task_id)
    if task not in ready_tasks(state, limit=len(state["tasks"])):
        raise ValueError(f"task is not ready: {task_id}")
    if not agent_id.strip() or PLACEHOLDER_AGENT.search(agent_id.strip()):
        raise ValueError("a real agent id is required")
    if any(item["status"] == "running" and agent_id in item.get("agent_ids", []) for item in state["tasks"]):
        raise ValueError("one agent id cannot own simultaneous running tasks")
    if task["owner"] == "pedagogy_reviewer":
        chapter = task_id.rsplit("-", 1)[-1]
        writer_ids = set(_by_id(state, f"write-{chapter}").get("agent_ids", []))
        if agent_id in writer_ids:
            raise ValueError("pedagogy reviewer must be independent from the chapter writer")
    root = Path(root or state.get("project_root") or Path.cwd()).resolve()
    base = tutorial_dir(root, state["slug"])
    verify_protected(base, state.get("protected_ready_chapters", {}))
    roots = {"repo": root, "content": base}
    ancestors = set(task["dependencies"])
    pending = list(ancestors)
    while pending:
        for dependency in _by_id(state, pending.pop())["dependencies"]:
            if dependency not in ancestors:
                ancestors.add(dependency)
                pending.append(dependency)
    for predecessor in state["tasks"]:
        if predecessor["status"] == "completed" and predecessor["id"] in ancestors:
            stale = revalidate_inputs(roots, predecessor.get("input_snapshot")) + revalidate_inputs(roots, predecessor.get("output_snapshot"))
            if stale or not predecessor.get("completed_by"):
                raise ValueError("dependency is stale or unverified; resume before starting: " + predecessor["id"])
        if predecessor["status"] == "completed" and predecessor.get("output_snapshot"):
            overlaps = ownership_conflicts(task.get("write_scopes", task["artifacts"]), predecessor.get("write_scopes", predecessor["artifacts"]))
            if overlaps and revalidate_inputs(roots, predecessor["output_snapshot"]):
                raise ValueError("predecessor outputs changed; resume before starting: " + predecessor["id"])
    task["input_snapshot"] = snapshot_inputs(roots, _input_selectors(task))
    task["active_agent_id"] = agent_id
    task.update({"status": "running", "started_at": now(), "blocked_reason": None})
    task["attempt"] += 1
    task["agent_ids"].append(agent_id)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _contains_secret(value: Any, key: str = "") -> bool:
    if re.search(r"(?:secret|token|cookie|authorization|password)", key, re.I):
        return bool(value)
    if isinstance(value, dict):
        return any(_contains_secret(child, str(child_key)) for child_key, child in value.items())
    if isinstance(value, list):
        return any(_contains_secret(child, key) for child in value)
    return False


def _validate_completion(base: Path, task: dict[str, Any]) -> None:
    if task["id"] == "normalize-input":
        manifest = (base / task["artifacts"][0]).read_text(encoding="utf-8")
        if "authoring contract" not in manifest.casefold() or "briefing-only" not in manifest.casefold():
            raise ValueError("input manifest must separate authoring contract from briefing-only material")
    if task["id"] == "roadmap":
        roadmap = (base / "_tutorial/roadmap.md").read_text(encoding="utf-8")
        required = (("audience", "독자"), ("final goal", "최종 목표"), ("first success", "첫 성공"))
        if any(not any(term in roadmap.casefold() for term in choices) for choices in required) or "pending" in roadmap.casefold():
            raise ValueError("roadmap requires finalized audience, final goal, and first success")
    if task["id"] == "version-research":
        environment = _json(base / "_tutorial/environment_matrix.json")
        ledger = [json.loads(line) for line in (base / "_tutorial/source_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if not environment or not ledger or not all(row.get("official") is True and str(row.get("url", "")).startswith("https://") for row in ledger):
            raise ValueError("version research requires a non-empty environment matrix and official HTTPS source ledger")
    if task["phase"] == "lab":
        packet_path = next(base / rel for rel in task["artifacts"] if "chapter_packets" in rel)
        packet = _json(packet_path)
        required = ("chapter", "first_action", "first_success_minutes", "steps")
        missing = [field for field in required if not packet.get(field)]
        if missing:
            raise ValueError(f"chapter packet missing: {', '.join(missing)}")
        if float(packet["first_success_minutes"]) > 10:
            raise ValueError("first observable success must be designed for 10 minutes or less")
        if not isinstance(packet["steps"], list) or not packet["steps"]:
            raise ValueError("chapter packet requires steps")
        for index, step in enumerate(packet["steps"], 1):
            absent = [field for field in ("action", "expected", "recovery", "validation") if not step.get(field)]
            if absent:
                raise ValueError(f"step {index} missing: {', '.join(absent)}")
            if step["validation"] not in {"checked", "reader_test_required"}:
                raise ValueError(f"step {index} has invalid validation state")
    if task["phase"] == "verify":
        evidence = _json(base / task["artifacts"][0])
        if evidence.get("broken_links"):
            raise ValueError("example verification contains broken links")
        if not isinstance(evidence.get("checks"), list) or not evidence["checks"]:
            raise ValueError("example verification requires checks")
        for check in evidence["checks"]:
            if check.get("status") not in {"checked", "reader_test_required"}:
                raise ValueError("verification check status must be checked or reader_test_required")
    if task["phase"] == "write":
        chapter = int(task["id"].rsplit("ch", 1)[1])
        survey = config(base)
        rows = [row for part in survey.get("parts", []) for row in part.get("chapters", [])]
        row = next((row for row in rows if int(row.get("num", -1)) == chapter), None)
        if not row or row.get("status", "ready") != "ready":
            raise ValueError("chapter writer must mark the completed bilingual chapter ready")
        all_ready = all(item.get("status", "ready") == "ready" for item in rows)
        if survey.get("status") != ("active" if all_ready else "wip"):
            raise ValueError("tutorial status must be active only when every chapter is ready")
    if task["phase"] == "qa":
        review = _json(base / task["artifacts"][0])
        if review.get("verdict") != "pass" or not review.get("independent"):
            raise ValueError("pedagogy QA must be independent and pass")
    if task["id"] == "deploy-preview":
        receipt = _json(base / task["artifacts"][0])
        required = ("channel", "content_digest", "content_commit", "framework_commit", "gallery_commit", "pages_url", "workflow_id", "access")
        missing = [field for field in required if not receipt.get(field)]
        if missing or receipt.get("channel") != "preview":
            raise ValueError("preview receipt is incomplete")
        access = receipt.get("access", {})
        if access != {"anonymous": "denied", "member": "denied", "admin_ko": "passed", "admin_en": "passed"}:
            raise ValueError("preview access matrix was not verified")
        if _contains_secret(receipt):
            raise ValueError("release receipts must not contain secrets or tokens")


def complete_task(root: Path, state: dict[str, Any], task_id: str) -> None:
    task = _by_id(state, task_id)
    if task["status"] != "running":
        raise ValueError(f"cannot complete task in status {task['status']}")
    base = tutorial_dir(root, state["slug"])
    verify_protected(base, state.get("protected_ready_chapters", {}))
    if not task.get("active_agent_id") or task["active_agent_id"] != task.get("agent_ids", [None])[-1]:
        raise ValueError("task completion requires the recorded active agent identity")
    roots = {"repo": root, "content": base}
    changed = revalidate_inputs(roots, task.get("input_snapshot"), task.get("write_scopes", task["artifacts"]))
    if changed:
        raise ValueError("task inputs changed while running: " + ", ".join(changed))
    missing = [rel for rel in task["artifacts"] if not (base / rel).exists()]
    if missing:
        raise ValueError(f"task artifacts missing: {', '.join(missing)}")
    _validate_completion(base, task)
    if task_id == "deploy-preview":
        receipt = _json(base / task["artifacts"][0])
        expected = state.get("quality", {}).get("last_scorecard", {}).get("content_digest")
        if not expected or receipt.get("content_digest") != expected:
            raise ValueError("preview receipt is not bound to the approved content digest")
    task.update({"status": "completed", "completed_at": now(), "blocked_reason": None})
    # The worker may normalize its own input or update readiness. Record that
    # final authorized state, while changed read-only inputs were rejected above.
    task["input_snapshot"] = snapshot_inputs(roots, _input_selectors(task))
    task["output_snapshot"] = snapshot_inputs(roots, _output_selectors(task))
    task["completed_by"] = task["active_agent_id"]
    if task_id == "deploy-preview":
        state["status"] = "preview_ready"
        state["release"]["preview"] = "released"


def block_task(state: dict[str, Any], task_id: str, reason: str) -> None:
    task = _by_id(state, task_id)
    task.update({"status": "blocked", "blocked_reason": reason})
    state["status"] = "deploy_blocked" if task["phase"] == "release" else "blocked"
    state["release"]["blocked_reason"] = reason


def resume_state(root: Path, state: dict[str, Any]) -> list[str]:
    base = tutorial_dir(root, state["slug"])
    verify_protected(base, state.get("protected_ready_chapters", {}))
    previous = state_path(root, state["slug"])
    if previous.exists():
        archive = base / "_workspace/state_history"
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(previous, archive / f"tutorial-{state['run_id']}-r{state['revision']}-{uuid.uuid4().hex[:8]}.json")
    state["schema_version"] = "2.1"
    state["project_root"] = str(root.resolve())
    contracts = {task["id"]: task for task in build_tasks(state["selected_chapters"])}
    roots = {"repo": root, "content": base}
    reopened = []
    for task in state["tasks"]:
        if task["id"] in contracts:
            task["write_scopes"] = contracts[task["id"]]["write_scopes"]
            task["inputs"] = contracts[task["id"]]["inputs"]
        missing = any(not (base / rel).exists() for rel in task["artifacts"])
        stale = []
        if task["status"] == "completed":
            stale = revalidate_inputs(roots, task.get("input_snapshot")) + revalidate_inputs(roots, task.get("output_snapshot"))
            if not task.get("completed_by") or task.get("completed_by") not in task.get("agent_ids", []):
                stale.append("unverified completed agent identity")
        if task["status"] in {"running", "blocked"} or (task["status"] == "completed" and (missing or stale)):
            task["status"] = "pending"
            task["blocked_reason"] = None
            task["reopened_reason"] = stale or (["missing output"] if missing else ["interrupted task"])
            task["completed_at"] = None
            reopened.append(task["id"])
    changed = True
    while changed:
        changed = False
        completed = {task["id"] for task in state["tasks"] if task["status"] in {"completed", "skipped"}}
        for task in state["tasks"]:
            if task["status"] == "completed" and not set(task["dependencies"]) <= completed:
                task["status"] = "pending"
                task["reopened_reason"] = ["dependency reopened"]
                task["completed_at"] = None
                reopened.append(task["id"])
                changed = True
    state["status"] = "running"
    if reopened:
        state["quality"]["last_scorecard"] = None
        state["release"]["preview"] = "pending"
        state["release"]["blocked_reason"] = None
    return reopened


def summarize(state: dict[str, Any]) -> dict[str, Any]:
    counts = {status: sum(task["status"] == status for task in state["tasks"]) for status in TASK_STATUSES}
    return {
        "slug": state["slug"],
        "run_id": state["run_id"],
        "status": state["status"],
        "selected_chapters": state["selected_chapters"],
        "counts": counts,
        "ready_tasks": [task["id"] for task in ready_tasks(state)],
        "release": state["release"],
    }
