"""Persistent DAG state for resumable multi-agent survey production."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .config import load_profile
from .schema_utils import validate_schema

STATE_REL = Path("_workspace/harness_state.json")
VALID_STATUSES = {"pending", "running", "completed", "blocked", "skipped"}
PLACEHOLDER_AGENT = re.compile(r"^(local|placeholder|mock|manual|single-agent|self|none)(?:[-_]|$)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root(path: str | Path | None = None) -> Path:
    root = Path(path or Path.cwd()).expanduser().resolve()
    if not (root / "build.py").exists() or not (root / "surveys").is_dir():
        raise ValueError(f"not a terry-surveys repository: {root}")
    return root


def content_repo_root(root: Path) -> Path:
    """Return the Git repository that owns survey content.

    Split workspaces expose ``root/surveys`` as a symlink into the private
    sibling repository. Legacy fixtures and historical checkouts keep the
    directory in the framework repository itself.
    """
    surveys = root / "surveys"
    candidate = surveys.resolve().parent
    return candidate if (candidate / ".git").exists() else root


def repository_layout(root: Path) -> str:
    return "split-v1" if content_repo_root(root) != root else "legacy-monorepo"


def survey_dir(root: Path, slug: str) -> Path:
    path = root / "surveys" / slug
    if not path.is_dir():
        raise FileNotFoundError(f"survey not found: {path}")
    return path


def chapter_numbers(path: Path) -> List[int]:
    data = json.loads((path / "survey.json").read_text(encoding="utf-8"))
    numbers = []
    for part in data.get("parts", []):
        for chapter in part.get("chapters", []):
            if chapter.get("num") is not None:
                numbers.append(int(chapter["num"]))
    if not numbers:
        raise ValueError(f"survey has no chapters: {path / 'survey.json'}")
    return sorted(set(numbers))


def _task(task_id: str, phase: str, owner: str, dependencies: Iterable[str], artifacts: Iterable[str], brief: str, resource_locks: Iterable[str] = ()) -> Dict[str, Any]:
    return {
        "id": task_id,
        "phase": phase,
        "owner": owner,
        "status": "pending",
        "dependencies": list(dependencies),
        "artifacts": list(artifacts),
        "brief": brief,
        "attempt": 0,
        "resource_locks": list(resource_locks),
        "agent_ids": [],
        "started_at": None,
        "completed_at": None,
        "blocked_reason": None,
    }


def build_tasks(chapters: Iterable[int]) -> List[Dict[str, Any]]:
    tasks = [
        _task("kg-seed", "research", "kg_mapper", [], ["_workspace/inputs/input_manifest.md", "_research/kg_seed.json", "_analysis/prior_survey_absorption.md"], "Read the normalized input manifest; resolve Terry paper-post and prior-survey IDs; map KG anchors, candidate gaps, and reusable links before external search."),
        _task("source-strategy", "research", "evidence_librarian", ["kg-seed"], ["_research/search_protocol.md"], "Define query families, sources, inclusion/exclusion rules, citation snowballing, and the saturation stop rule."),
        _task("research-foundations", "research", "deep_researcher_foundations", ["source-strategy"], ["_research/papers_foundations.json", "_research/groups_foundations.md", "_research/timeline_foundations.md"], "Research foundational lineages and primary sources; record methods, limits, and chapter hints."),
        _task("research-frontier", "research", "deep_researcher_frontier", ["source-strategy"], ["_research/papers_frontier.json", "_research/groups_frontier.md", "_research/timeline_frontier.md"], "Research current frontier, industry primary sources, disagreements, and freshness-sensitive claims."),
        _task("evidence-synthesis", "synthesize", "evidence_librarian", ["research-foundations", "research-frontier"], ["_research/papers.json", "_research/source_ledger.jsonl", "_analysis/claim_evidence.jsonl"], "Merge and deduplicate sources, create the claim ledger, and write one source packet per chapter."),
    ]
    evidence_task = tasks[-1]
    for ch in chapters:
        packet = f"_analysis/chapter_source_packets/ch{ch:02d}.json"
        evidence_task["artifacts"].append(packet)
        write_id = f"write-ch{ch:02d}"
        image_id = f"image-ch{ch:02d}"
        fact_id = f"factcheck-ch{ch:02d}"
        tasks.extend([
            _task(write_id, "write", "book_writer", ["evidence-synthesis"], [f"book/ko/ch{ch:02d}.md", f"book/en/ch{ch:02d}.md"], f"Write both languages for chapter {ch} from its source packet; preserve citations, argument, caveats, tables, and learning structure."),
            _task(image_id, "illustrate", "image_curator", [write_id], ["_workspace/image_plan.json"], f"Curate and distribute chapter {ch} figures; update the shared image plan and provenance log.", ["image-plan"]),
            _task(fact_id, "factcheck", "fact_checker", [write_id], ["_refs_extracted.json", "_factcheck_report.md", "_analysis/claim_evidence.jsonl"], f"Verify every high-risk chapter {ch} claim against primary sources and request prose corrections.", ["claim-ledger", "factcheck-report", "refs-extracted"]),
            _task(f"qa-ch{ch:02d}", "qa", "qa_reviewer", [image_id, fact_id], ["_qa_report.md", "_quality/reviewer_scores.json"], f"Independently review chapter {ch}; score synthesis and usability without editing the chapter directly.", ["qa-report", "reviewer-scores"]),
        ])
    return tasks


def new_state(root: Path, slug: str, profile_name: str = "full", deploy: str | None = None) -> Dict[str, Any]:
    path = survey_dir(root, slug)
    chapters = chapter_numbers(path)
    profile = load_profile(profile_name)
    stamp = now()
    return {
        "schema_version": "2.0",
        "revision": 0,
        "run_id": str(uuid.uuid4()),
        "slug": slug,
        "profile": profile_name,
        "repository_layout": repository_layout(root),
        "status": "running",
        "created_at": stamp,
        "updated_at": stamp,
        "chapter_count": len(chapters),
        "max_parallel": int(profile["max_parallel"]),
        "max_remediation_attempts": int(profile["max_remediation_attempts"]),
        "tasks": build_tasks(chapters),
        "quality": {"history": [], "remediation_attempts": {}, "last_scorecard": None},
        "release": {"policy": deploy or profile["deploy"], "status": "pending", "attempts": 0, "artifacts": {}, "blocked_reason": None},
    }


def state_path(root: Path, slug: str) -> Path:
    return survey_dir(root, slug) / STATE_REL


def save_state(root: Path, state: Dict[str, Any], replace: bool = False) -> Path:
    validate_state(state)
    path = state_path(root, state["slug"])
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current_revision = None
        if path.exists():
            current = json.loads(path.read_text(encoding="utf-8"))
            current_revision = int(current.get("revision", 0))
        expected = int(state.get("revision", 0))
        if not replace and current_revision is not None and current_revision != expected:
            raise ValueError(f"stale state revision: loaded {expected}, current {current_revision}; reload before saving")
        state["revision"] = (current_revision if current_revision is not None else expected) + 1
        state["updated_at"] = now()
        handle, temp_name = tempfile.mkstemp(prefix="harness-state-", suffix=".json.tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temp:
                temp.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
                temp.flush()
                os.fsync(temp.fileno())
            Path(temp_name).replace(path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    return path


def load_state(root: Path, slug: str) -> Dict[str, Any]:
    path = state_path(root, slug)
    if not path.exists():
        raise FileNotFoundError(f"harness state not found; run init first: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    validate_state(state)
    return state


def validate_state(state: Dict[str, Any]) -> None:
    required = {"schema_version", "revision", "run_id", "slug", "profile", "status", "tasks", "quality", "release"}
    missing = sorted(required - set(state))
    if missing:
        raise ValueError(f"state missing fields: {', '.join(missing)}")
    if state["schema_version"] != "2.0":
        raise ValueError(f"unsupported state schema: {state['schema_version']!r}")
    tasks = state["tasks"]
    if not isinstance(tasks, list):
        raise ValueError("state.tasks must be a list")
    ids = [task.get("id") for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("state contains duplicate task ids")
    known = set(ids)
    for task in tasks:
        for field in ("id", "phase", "owner", "status", "dependencies", "artifacts", "attempt"):
            if field not in task:
                raise ValueError(f"task missing {field}: {task.get('id')!r}")
        if task["status"] not in VALID_STATUSES:
            raise ValueError(f"invalid task status {task['status']!r}: {task['id']}")
        unknown = set(task["dependencies"]) - known
        if unknown:
            raise ValueError(f"task {task['id']} has unknown dependencies: {sorted(unknown)}")
    schema_errors = validate_schema(state, "harness-state.schema.json")
    if schema_errors:
        raise ValueError(f"state schema errors: {'; '.join(schema_errors[:8])}")


def _by_id(state: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    for task in state["tasks"]:
        if task["id"] == task_id:
            return task
    raise KeyError(f"unknown task: {task_id}")


def ready_tasks(state: Dict[str, Any], limit: int | None = None) -> List[Dict[str, Any]]:
    completed = {task["id"] for task in state["tasks"] if task["status"] in {"completed", "skipped"}}
    running = sum(task["status"] == "running" for task in state["tasks"])
    capacity = max(0, int(state.get("max_parallel", 3)) - running)
    if limit is not None:
        capacity = min(capacity, limit)
    held = {lock for task in state["tasks"] if task["status"] == "running" for lock in task.get("resource_locks", [])}
    selected = []
    for task in state["tasks"]:
        locks = set(task.get("resource_locks", []))
        if task["status"] == "pending" and set(task["dependencies"]) <= completed and not locks.intersection(held):
            selected.append(task)
            held.update(locks)
            if len(selected) >= capacity:
                break
    return selected


def start_task(state: Dict[str, Any], task_id: str, agent_id: str) -> None:
    task = _by_id(state, task_id)
    if task not in ready_tasks(state, limit=len(state["tasks"])):
        raise ValueError(f"task is not ready: {task_id}")
    if not agent_id.strip() or PLACEHOLDER_AGENT.search(agent_id.strip()):
        raise ValueError("a real worker agent id is required")
    task["status"] = "running"
    task["attempt"] = int(task.get("attempt", 0)) + 1
    task.setdefault("agent_ids", []).append(agent_id.strip())
    task["started_at"] = now()
    task["blocked_reason"] = None


def complete_task(root: Path, state: Dict[str, Any], task_id: str, extra_artifacts: Iterable[str] = ()) -> None:
    task = _by_id(state, task_id)
    if task["status"] != "running":
        raise ValueError(f"cannot complete task in status {task['status']}: {task_id}")
    for artifact in extra_artifacts:
        if artifact not in task["artifacts"]:
            task["artifacts"].append(artifact)
    base = survey_dir(root, state["slug"])
    missing = [rel for rel in task["artifacts"] if not (base / rel).exists()]
    if missing:
        raise ValueError(f"task artifacts missing for {task_id}: {', '.join(missing)}")
    _validate_task_content(base, state, task)
    task["status"] = "completed"
    task["completed_at"] = now()
    task["blocked_reason"] = None
    if task.get("phase") == "remediate":
        attempts = state["quality"].setdefault("remediation_attempts", {})
        for failure_id in task.get("failure_ids", []):
            attempts[failure_id] = int(attempts.get(failure_id, 0)) + 1


def _rough_words(text: str) -> int:
    reference_heading = re.search(r"^##+\s+(?:References|Bibliography|참고문헌)\s*$", text, flags=re.I | re.M)
    if reference_heading:
        text = text[:reference_heading.start()]
    text = re.sub(r"^---\s*$.*?^---\s*$", "", text, count=1, flags=re.M | re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"https?://\S+", "", text)
    englishish = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", text)
    korean_chunks = re.findall(r"[가-힣]+", text)
    return len(englishish) + sum(max(1, len(chunk) // 2) for chunk in korean_chunks)


def _jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _validate_task_content(base: Path, state: Dict[str, Any], task: Dict[str, Any]) -> None:
    task_id = task["id"]
    if task_id == "kg-seed":
        data = json.loads((base / "_research/kg_seed.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("anchors"):
            raise ValueError("kg-seed requires a non-empty anchors list")
    if task_id == "source-strategy":
        protocol = (base / "_research/search_protocol.md").read_text(encoding="utf-8", errors="ignore").lower()
        required_terms = ("query", "inclusion", "exclusion", "snowball", "saturation")
        missing = [term for term in required_terms if term not in protocol]
        if missing:
            raise ValueError(f"source-strategy search protocol missing: {', '.join(missing)}")
    if task_id in {"research-foundations", "research-frontier"}:
        paper_rel = next(rel for rel in task["artifacts"] if rel.endswith(".json"))
        papers = json.loads((base / paper_rel).read_text(encoding="utf-8"))
        if isinstance(papers, dict):
            papers = papers.get("papers") or papers.get("items")
        if not isinstance(papers, list) or not papers:
            raise ValueError(f"{task_id} requires a non-empty research shard")
    if task_id == "evidence-synthesis":
        for rel in ("_research/source_ledger.jsonl", "_analysis/claim_evidence.jsonl"):
            if not _jsonl_rows(base / rel):
                raise ValueError(f"{task_id} requires non-empty {rel}")
        minimum = int(load_profile(state["profile"])["min_sources_per_chapter"])
        for rel in task["artifacts"]:
            if "chapter_source_packets/" not in rel:
                continue
            packet = json.loads((base / rel).read_text(encoding="utf-8"))
            required = ("chapter", "thesis", "sections", "sources", "counterevidence", "visual_candidates")
            missing = [field for field in required if field not in packet]
            if missing:
                raise ValueError(f"{rel} missing fields: {', '.join(missing)}")
            if len(packet.get("sources", [])) < minimum:
                raise ValueError(f"{rel} has {len(packet.get('sources', []))} sources; requires {minimum}")
    if task.get("phase") == "remediate":
        evidence_path = base / f"_quality/remediation/{task_id}.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        required = ("failure_ids", "before", "after", "changed_artifacts", "evidence")
        missing = [field for field in required if not evidence.get(field)]
        if missing:
            raise ValueError(f"{task_id} remediation evidence missing: {', '.join(missing)}")
        if sorted(evidence["failure_ids"]) != sorted(task.get("failure_ids", [])):
            raise ValueError(f"{task_id} remediation evidence failure_ids mismatch")
    match = re.fullmatch(r"write-ch(\d+)", task_id)
    if match:
        profile = load_profile(state["profile"])
        minimum = int(profile["min_words_per_language_chapter"])
        for rel in task["artifacts"]:
            count = _rough_words((base / rel).read_text(encoding="utf-8", errors="ignore"))
            if count < minimum:
                raise ValueError(f"{task_id} artifact {rel} has {count} rough words; requires {minimum}")
    match = re.fullmatch(r"image-ch(\d+)", task_id)
    if match:
        ch_key = f"ch{int(match.group(1)):02d}"
        data = json.loads((base / "_workspace/image_plan.json").read_text(encoding="utf-8"))
        items = data.get("chapters", {}).get(ch_key, []) if isinstance(data, dict) else []
        if not items:
            raise ValueError(f"{task_id} requires image-plan entries for {ch_key}")
    match = re.fullmatch(r"factcheck-ch(\d+)", task_id)
    if match:
        chapter = int(match.group(1))
        rows = _jsonl_rows(base / "_analysis/claim_evidence.jsonl")
        if not any(int(row.get("chapter", 0)) == chapter for row in rows):
            raise ValueError(f"{task_id} requires claim-evidence rows for chapter {chapter}")
        report = (base / "_factcheck_report.md").read_text(encoding="utf-8", errors="ignore")
        if not re.search(rf"\b(?:ch(?:apter)?\.?\s*0?{chapter}|0?{chapter}\s*장)\b", report, flags=re.I):
            raise ValueError(f"{task_id} requires a chapter-level fact-check trail")
    match = re.fullmatch(r"qa-ch(\d+)", task_id)
    if match:
        chapter = int(match.group(1))
        report = (base / "_qa_report.md").read_text(encoding="utf-8", errors="ignore")
        if not re.search(rf"\b(?:ch(?:apter)?\.?\s*0?{chapter}|0?{chapter}\s*장)\b", report, flags=re.I):
            raise ValueError(f"{task_id} requires a chapter-level QA trail")


def block_task(state: Dict[str, Any], task_id: str, reason: str) -> None:
    if not reason.strip():
        raise ValueError("blocked reason is required")
    task = _by_id(state, task_id)
    task["status"] = "blocked"
    task["blocked_reason"] = reason.strip()
    state["status"] = "blocked"


def record_score(state: Dict[str, Any], scorecard_rel: str, scorecard: Dict[str, Any]) -> None:
    if scorecard.get("profile") != state.get("profile"):
        raise ValueError(f"score profile {scorecard.get('profile')!r} does not match state profile {state.get('profile')!r}")
    summary = {
        "recorded_at": now(),
        "score": scorecard["score"],
        "passed": scorecard["passed"],
        "blocker_count": len(scorecard.get("hard_blockers", [])),
        "dimensions": scorecard.get("dimensions", {}),
        "content_digest": scorecard.get("content_digest"),
    }
    state["quality"].setdefault("history", []).append(summary)
    state["quality"]["last_scorecard"] = scorecard_rel
    state["status"] = "ready" if scorecard["passed"] else "remediating"


def plan_remediation(state: Dict[str, Any], failures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    max_attempts = int(state.get("max_remediation_attempts", 3))
    attempts = state["quality"].setdefault("remediation_attempts", {})
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    exhausted = []
    active_failure_ids = {
        failure_id
        for task in state["tasks"]
        if task.get("phase") == "remediate" and task.get("status") in {"pending", "running"}
        for failure_id in task.get("failure_ids", [])
    }
    for failure in failures:
        gate = failure["id"]
        if gate in active_failure_ids:
            continue
        count = int(attempts.get(gate, 0))
        if count >= max_attempts:
            exhausted.append(gate)
            continue
        grouped.setdefault(failure["owner"], []).append(failure)
    created = []
    round_number = len(state["quality"].get("history", []))
    for owner, items in grouped.items():
        task_id = f"repair-{owner}-r{round_number}"
        suffix = 1
        existing = {task["id"] for task in state["tasks"]}
        while task_id in existing:
            suffix += 1
            task_id = f"repair-{owner}-r{round_number}-{suffix}"
        evidence_rel = f"_quality/remediation/{task_id}.json"
        task = _task(task_id, "remediate", owner, [], [evidence_rel], "\n".join(f"[{item['id']}] {item['message']}" for item in items), [f"repair-owner:{owner}"])
        task["failure_ids"] = [item["id"] for item in items]
        state["tasks"].append(task)
        created.append(task)
    if exhausted:
        state["status"] = "blocked"
        state["quality"]["blocked_reason"] = f"remediation attempts exhausted: {', '.join(sorted(exhausted))}"
    elif created:
        state["status"] = "remediating"
    return created


def completed_task_errors(root: Path, state: Dict[str, Any]) -> Dict[str, str]:
    base = survey_dir(root, state["slug"])
    errors = {}
    for task in state["tasks"]:
        if task["status"] != "completed":
            continue
        try:
            missing = [rel for rel in task["artifacts"] if not (base / rel).exists()]
            if missing:
                raise ValueError(f"missing artifacts: {', '.join(missing)}")
            _validate_task_content(base, state, task)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors[task["id"]] = str(exc)
    return errors


def release_receipt_errors(root: Path, state: Dict[str, Any]) -> List[str]:
    if state.get("status") != "released":
        return []
    evidence = state.get("release", {}).get("artifacts", {})
    rel = str(evidence.get("release_receipt") or "")
    if not rel:
        return ["release receipt path is missing"]
    base = survey_dir(root, state["slug"]).resolve()
    receipt_path = (base / rel).resolve()
    if base not in receipt_path.parents or not receipt_path.is_file():
        return ["release receipt is missing or outside the survey directory"]
    payload = receipt_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != str(evidence.get("release_receipt_sha256") or ""):
        return ["release receipt SHA256 mismatch"]
    try:
        receipt = json.loads(payload)
    except json.JSONDecodeError as exc:
        return [f"release receipt JSON is invalid: {exc}"]
    history = state.get("quality", {}).get("history", [])
    expected_digest = history[-1].get("content_digest") if history else None
    errors = []
    if receipt.get("slug") != state["slug"] or receipt.get("content_digest") != expected_digest:
        errors.append("release receipt is not bound to the current slug/content digest")
    labels = {check.get("label") for check in receipt.get("checks", []) if isinstance(check, dict) and check.get("exit_code") == 0}
    required = {"survey-commit", "survey-commit-remote", "gallery-commit", "gallery-commit-remote", "scored-content-commit", "workers-workflow", "pages_url", "live_ko_url", "live_en_url", "asset-validation", "kg-sync"}
    missing = sorted(required - labels)
    if missing:
        errors.append(f"release receipt checks missing: {', '.join(missing)}")
    return errors


def resume_state(root: Path, state: Dict[str, Any]) -> Dict[str, str]:
    errors = completed_task_errors(root, state)
    for task in state["tasks"]:
        if task["status"] in {"running", "blocked"} or task["id"] in errors:
            task["status"] = "pending"
            task["started_at"] = None
            task["completed_at"] = None
            task["blocked_reason"] = errors.get(task["id"])
    changed = True
    while changed:
        changed = False
        completed = {task["id"] for task in state["tasks"] if task["status"] in {"completed", "skipped"}}
        for task in state["tasks"]:
            if task["status"] == "completed" and not set(task["dependencies"]) <= completed:
                task["status"] = "pending"
                task["completed_at"] = None
                task["blocked_reason"] = "dependency reopened during resume revalidation"
                errors[task["id"]] = task["blocked_reason"]
                changed = True
    state["status"] = "running"
    state["quality"].pop("blocked_reason", None)
    return errors


def migrate_legacy_state(root: Path, slug: str, profile_name: str = "full") -> Dict[str, Any]:
    """Create v2 state while preserving auditable evidence from the v1 file."""
    base = survey_dir(root, slug)
    legacy_path = base / "_workspace" / "orchestration_state.json"
    if not legacy_path.exists():
        raise FileNotFoundError(f"legacy orchestration state not found: {legacy_path}")
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    state = new_state(root, slug, profile_name)
    state["migrated_from"] = {"path": "_workspace/orchestration_state.json", "schema": legacy.get("schema_version", "legacy"), "status": legacy.get("status"), "migrated_at": now()}
    gates = legacy.get("gates", {}) if isinstance(legacy.get("gates"), dict) else {}
    agents = legacy.get("agents", {}) if isinstance(legacy.get("agents"), dict) else {}
    role_gate = {
        "kg_mapper": "analysis",
        "evidence_librarian": "analysis",
        "deep_researcher_foundations": "research_shards",
        "deep_researcher_frontier": "research_shards",
        "book_writer": "writing",
        "image_curator": "images",
        "fact_checker": "factcheck",
        "qa_reviewer": "qa",
    }
    for task in state["tasks"]:
        gate = role_gate.get(task["owner"])
        agent = agents.get(task["owner"], {}) if isinstance(agents.get(task["owner"]), dict) else {}
        evidence_complete = gate and gates.get(gate) == "complete"
        artifacts_exist = all((base / rel).exists() for rel in task["artifacts"])
        if evidence_complete and artifacts_exist:
            task["status"] = "completed"
            task["completed_at"] = now()
            ids = agent.get("agent_ids") or ([agent.get("agent_id")] if agent.get("agent_id") else [])
            task["agent_ids"] = [str(item) for item in ids if item]
            task["attempt"] = 1
    return state


def update_release(state: Dict[str, Any], status: str, reason: str | None = None, artifacts: Dict[str, str] | None = None) -> None:
    if status not in {"running", "released", "blocked"}:
        raise ValueError(f"invalid release status: {status}")
    release = state["release"]
    if artifacts:
        release.setdefault("artifacts", {}).update(artifacts)
    if status == "running":
        if state.get("profile") != "full":
            raise ValueError("only the full quality profile can authorize release")
        if release.get("policy") != "auto":
            raise ValueError("release policy is off; initialize or explicitly change the run to deploy=auto")
        incomplete = [task["id"] for task in state["tasks"] if task["status"] not in {"completed", "skipped"}]
        if incomplete:
            raise ValueError(f"release blocked by incomplete tasks: {', '.join(incomplete[:12])}")
        unassigned = [task["id"] for task in state["tasks"] if task["status"] == "completed" and not task.get("agent_ids")]
        if unassigned:
            raise ValueError(f"release blocked by completed tasks without worker identity: {', '.join(unassigned[:12])}")
        role_identities: Dict[str, set] = {}
        for task in state["tasks"]:
            if task.get("phase") == "remediate":
                continue
            role_identities.setdefault(str(task.get("owner")), set()).update(str(item) for item in task.get("agent_ids", []) if item)
        required_roles = {"kg_mapper", "evidence_librarian", "deep_researcher_foundations", "deep_researcher_frontier", "book_writer", "image_curator", "fact_checker", "qa_reviewer"}
        missing_roles = sorted(role for role in required_roles if not role_identities.get(role))
        if missing_roles:
            raise ValueError(f"release blocked by missing role worker identities: {', '.join(missing_roles)}")
        overlaps = []
        role_names = sorted(required_roles)
        for index, left in enumerate(role_names):
            for right in role_names[index + 1:]:
                shared = role_identities[left].intersection(role_identities[right])
                if shared:
                    overlaps.append(f"{left}/{right}={','.join(sorted(shared))}")
        if overlaps:
            raise ValueError(f"release requires distinct role workers; overlapping identities: {'; '.join(overlaps[:12])}")
        history = state.get("quality", {}).get("history", [])
        if not history or history[-1].get("passed") is not True:
            raise ValueError("release requires the latest recorded full score to pass")
        if state["status"] not in {"ready", "deploy_blocked"}:
            raise ValueError("release can start only after the quality state is ready")
        release["attempts"] = int(release.get("attempts", 0)) + 1
        release["started_at"] = now()
        release["blocked_reason"] = None
        state["status"] = "ready"
    elif status == "released":
        if release.get("status") != "running":
            raise ValueError("release must be running before it can be completed")
        commit_keys = {"content_commit", "framework_commit"} if state.get("repository_layout") == "split-v1" else {"survey_commit"}
        required = {"pages_url", "live_ko_url", "live_en_url", "gallery_commit", "workflow_id", "kg_baseline_sha256", "live_ko", "live_en", "asset_validation", "workers_status", "source_push", "kg_sync", "iframe_check", "not_found_check", "release_receipt", "release_receipt_sha256"} | commit_keys
        missing = sorted(required - set(release.get("artifacts", {})))
        if missing:
            raise ValueError(f"release evidence missing: {', '.join(missing)}")
        evidence = release["artifacts"]
        for key in ("pages_url", "live_ko_url", "live_en_url"):
            parsed = urlparse(str(evidence[key]))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f"release {key} must be a credential-free HTTPS URL")
            if not (parsed.hostname.endswith("pages.dev") or parsed.hostname == "terryum.ai" or parsed.hostname.endswith(".terryum.ai")):
                raise ValueError(f"release {key} has an unexpected host: {parsed.hostname}")
        for key in sorted(commit_keys | {"gallery_commit"}):
            if not re.fullmatch(r"[0-9a-f]{7,40}", str(evidence[key]), flags=re.I):
                raise ValueError(f"release {key} must be a git SHA")
        if not re.fullmatch(r"\d+", str(evidence["workflow_id"])):
            raise ValueError("release workflow_id must be a numeric GitHub Actions run id")
        if not re.fullmatch(r"[0-9a-f]{64}", str(evidence["release_receipt_sha256"]), flags=re.I):
            raise ValueError("release receipt SHA256 is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(evidence["kg_baseline_sha256"]), flags=re.I):
            raise ValueError("release KG baseline SHA256 is invalid")
        expected = {"live_ko": "passed", "live_en": "passed", "asset_validation": "passed", "workers_status": "success", "source_push": "passed", "kg_sync": "passed", "iframe_check": "passed", "not_found_check": "passed"}
        invalid = [key for key, value in expected.items() if str(evidence.get(key)).lower() != value]
        if invalid:
            raise ValueError(f"release evidence is not successful: {', '.join(invalid)}")
        release["completed_at"] = now()
        state["status"] = "released"
    else:
        if not reason:
            raise ValueError("blocked release requires a reason")
        release["blocked_reason"] = reason
        state["status"] = "deploy_blocked"
    release["status"] = status


def summarize(state: Dict[str, Any]) -> Dict[str, Any]:
    counts = {status: 0 for status in VALID_STATUSES}
    for task in state["tasks"]:
        counts[task["status"]] += 1
    return {
        "slug": state["slug"],
        "run_id": state["run_id"],
        "profile": state["profile"],
        "status": state["status"],
        "tasks": counts,
        "ready_tasks": [task["id"] for task in ready_tasks(state)],
        "last_score": state["quality"]["history"][-1] if state["quality"].get("history") else None,
        "release": state["release"],
    }
