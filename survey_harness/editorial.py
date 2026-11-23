"""Evidence-bound independent editorial reviews, separate from prose metrics."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .schema_utils import validate_schema


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def manuscript_digests(path: Path, chapter: int) -> Dict[str, str]:
    """Hash the exact reviewed KO/EN bytes, including metadata and claim markers."""
    return {
        lang: hashlib.sha256(target.read_bytes()).hexdigest()
        for lang in ("ko", "en")
        if (target := path / f"book/{lang}/ch{chapter:02d}.md").is_file()
    }


def _identity_errors(data: Dict[str, Any], task_id: str, state: Dict[str, Any]) -> List[str]:
    tasks = state.get("tasks", []) if isinstance(state, dict) else []
    reviewer_id = data.get("reviewer_id")
    bound_ids = {
        agent_id for task in tasks if isinstance(task, dict)
        and task.get("id") == task_id and task.get("owner") == "qa_reviewer"
        for agent_id in task.get("agent_ids", [])[-1:]
    }
    non_qa_ids = {
        agent_id for task in tasks if isinstance(task, dict) and task.get("owner") != "qa_reviewer"
        for agent_id in task.get("agent_ids", [])
    }
    errors = []
    if not reviewer_id or reviewer_id not in bound_ids:
        errors.append(f"reviewer_id is not bound to the actual {task_id} QA worker")
    if reviewer_id in non_qa_ids:
        errors.append("reviewer_id also performed a non-QA task in this run")
    return errors


def _finding_errors(path: Path, findings: List[Dict[str, Any]], chapters: Iterable[int]) -> List[str]:
    allowed_paths = {f"book/{lang}/ch{ch:02d}.md" for ch in chapters for lang in ("ko", "en")}
    errors = []
    seen = set()
    for finding in findings:
        finding_id = finding["id"]
        if finding_id in seen:
            errors.append(f"duplicate finding id: {finding_id}")
        seen.add(finding_id)
        location = finding["location"]["path"]
        if location not in allowed_paths:
            errors.append(f"finding {finding_id}: location must name a reviewed manuscript")
            continue
        target = path / location
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        excerpt = re.sub(r"\s+", " ", finding["excerpt"]).strip()
        if not excerpt or excerpt not in re.sub(r"\s+", " ", text):
            errors.append(f"finding {finding_id}: excerpt is absent from {location}")
        for field in ("problem", "impact", "expected"):
            if not finding[field].strip():
                errors.append(f"finding {finding_id}: {field} must be concrete and nonempty")
        if not finding["location"]["anchor"].strip():
            errors.append(f"finding {finding_id}: location anchor must be nonempty")
    return errors


def _passage_errors(row: Dict[str, Any], manuscripts: Dict[str, str], label: str) -> List[str]:
    location = row.get("path")
    excerpt = row.get("excerpt")
    reason = row.get("reason")
    if not isinstance(location, str) or location not in manuscripts:
        return [f"{label}: path must name a reviewed manuscript"]
    errors = []
    if not isinstance(excerpt, str) or len(" ".join(excerpt.split())) < 12 or " ".join(excerpt.split()) not in manuscripts[location]:
        errors.append(f"{label}: cite a real passage from {location}")
    if not isinstance(reason, str) or len(reason.strip()) < 12:
        errors.append(f"{label}: explain the judgment about the cited passage")
    return errors


def chapter_review_errors(path: Path, chapter: int, state: Dict[str, Any]) -> List[str]:
    """Validate one review without requiring other chapters or a passing verdict."""
    data = _read(path / f"_quality/chapters/ch{chapter:02d}.json")
    errors = validate_schema(data, "chapter-review.schema.json")
    if errors:
        return errors
    if data["chapter"] != chapter:
        errors.append("chapter does not match the reviewed task")
    if not math.isfinite(data["synthesis"]["score"]) or len(data["synthesis"]["evidence"].strip()) < 12:
        errors.append("synthesis requires a finite score and substantive review evidence")
    expected = manuscript_digests(path, chapter)
    if len(expected) != 2 or data["manuscript_digests"] != expected:
        errors.append("manuscript_digests do not match the current KO/EN manuscript bytes")
    errors.extend(_identity_errors(data, f"qa-ch{chapter:02d}", state))
    errors.extend(_finding_errors(path, data["findings"], [chapter]))
    manuscripts = {}
    for lang in expected:
        rel = f"book/{lang}/ch{chapter:02d}.md"
        text = (path / rel).read_text(encoding="utf-8")
        # Editorial evidence comes from reader-visible passages.
        text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.S)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        manuscripts[rel] = " ".join(text.split())
    blockers = {finding["id"]: finding for finding in data["findings"] if finding["severity"] == "blocker"}
    for name, rows in data["judgments"].items():
        paths = {f"book/ko/ch{chapter:02d}.md"} if name == "korean_prose" else set(manuscripts)
        covered = set()
        for index, row in enumerate(rows):
            label = f"{name}[{index}]"
            errors.extend(_passage_errors(row, {key: manuscripts[key] for key in paths if key in manuscripts}, label))
            location = row.get("path")
            if isinstance(location, str) and location in paths:
                covered.add(location)
            if row.get("verdict") == "needs_revision":
                finding_id = row.get("finding_id")
                if not isinstance(finding_id, str) or blockers.get(finding_id, {}).get("location", {}).get("path") != location:
                    errors.append(f"{label}: needs_revision requires a blocking finding in the same manuscript")
            elif row.get("verdict") != "pass":
                errors.append(f"{label}: verdict must be pass or needs_revision")
        if paths != covered:
            errors.append(f"{name}: cite passages from {', '.join(sorted(paths - covered))}")
    tasks = [task for task in state.get("tasks", []) if isinstance(task, dict) and isinstance(task.get("id"), str)]
    chapter_tasks = [task for task in tasks if re.fullmatch(r"qa-ch\d+", task["id"])]
    review_task = next((task for task in chapter_tasks if task["id"] == f"qa-ch{chapter:02d}"), {})
    if chapter_tasks and review_task is min(chapter_tasks, key=lambda task: int(task["id"][5:])) and not data.get("editorial_principles"):
        errors.append("representative review requires reusable editorial_principles")
    for index, row in enumerate(data.get("editorial_principles", [])):
        label = f"editorial_principles[{index}]"
        errors.extend(_passage_errors(row, manuscripts, label))
        if not isinstance(row.get("principle"), str) or len(row["principle"].strip()) < 12:
            errors.append(f"{label}: state a reusable editorial principle")
    requested = set(review_task.get("repair_requests", []))
    repairs = {task["id"]: task for task in tasks if task["id"] in requested}
    if requested != repairs.keys():
        errors.append("requested repair task is missing from the current run")
    rechecks = data.get("rechecks", {})
    if rechecks.keys() != repairs.keys():
        errors.append("rechecks must match the requested repair task IDs")
    for repair_id, repair in repairs.items():
        outcomes = rechecks.get(repair_id, {})
        findings = repair["review_findings"]
        if outcomes.keys() != findings.keys():
            errors.append(f"{repair_id}: rechecks must cover each original failure ID")
        for failure_id, finding in findings.items():
            if failure_id not in outcomes:
                continue
            row = outcomes[failure_id]
            label = f"{repair_id}/{failure_id}"
            location = finding["location"]["path"]
            errors.extend(_passage_errors(row, {location: manuscripts[location]} if location in manuscripts else {}, label))
            expected_status = "open" if finding["id"] in blockers else "resolved"
            if row.get("status") != expected_status:
                errors.append(f"{label}: status must be {expected_status} given the current blocking findings")
    return errors


def book_review_errors(path: Path, chapters: Iterable[int], state: Dict[str, Any]) -> List[str]:
    """Validate the current full-book review; legacy artifacts remain readable."""
    chapters = list(chapters)
    data = _read(path / "_quality/reviewer_scores.json")
    errors = validate_schema(data, "reviewer-scores.schema.json")
    if errors:
        return errors
    if data.get("schema_version") != "2.1":
        return ["book review requires schema_version 2.1 and a fresh independent review"]
    for name, dimension in data["dimensions"].items():
        if not math.isfinite(dimension["score"]) or len(dimension["evidence"].strip()) < 12:
            errors.append(f"{name} requires a finite score and substantive review evidence")
    expected = {f"ch{ch:02d}": manuscript_digests(path, ch) for ch in chapters}
    if any(len(value) != 2 for value in expected.values()) or data["manuscript_digests"] != expected:
        errors.append("manuscript_digests must bind every current KO/EN chapter")
    errors.extend(_identity_errors(data, "qa-book", state))
    errors.extend(_finding_errors(path, data["findings"], chapters))
    return errors


def finding_failure(finding: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Retain the review's concrete edit instruction through remediation dispatch."""
    return {
        "id": f"editorial-{prefix}-{finding['id']}", "owner": "book_writer",
        "message": finding["problem"], "metric": finding["excerpt"], "threshold": finding["expected"],
        "finding": finding,
        **{key: finding[key] for key in ("location", "excerpt", "problem", "impact", "expected", "action")},
    }


def review_chapters(path: Path, chapters: Iterable[int], profile: Dict[str, Any], state: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return semantic scores, hard defects and editorial warnings for each chapter."""
    metrics, failures, warnings = {}, [], []
    for chapter in chapters:
        key = f"ch{chapter:02d}"
        data = _read(path / f"_quality/chapters/{key}.json")
        errors = chapter_review_errors(path, chapter, state)
        metrics[key] = {"errors": errors, "score": None, "reviewer_id": data.get("reviewer_id") if isinstance(data, dict) else None}
        if errors:
            failures.append({"id": f"chapter-review-{key}", "owner": "qa_reviewer", "message": "Chapter review is missing, stale, unbound, or malformed.", "metric": errors, "threshold": "current independent chapter review"})
            continue
        score = float(data["synthesis"]["score"])
        metrics[key].update({"score": score, "evidence": data["synthesis"]["evidence"], "findings": data["findings"]})
        blocking = [finding for finding in data["findings"] if finding["severity"] == "blocker"]
        repair_ids = {
            failure_id for outcomes in data.get("rechecks", {}).values()
            for failure_id, outcome in outcomes.items() if outcome["status"] == "open"
        }
        for finding in blocking:
            failure = finding_failure(finding, key)
            # A book finding rechecked in its chapter retains the original retry budget.
            failure["id"] = next((failure_id for failure_id in sorted(repair_ids)
                                  if failure_id == f"editorial-book-{finding['id']}"), failure["id"])
            failures.append(failure)
        warnings.extend(finding_failure(finding, key) for finding in data["findings"] if finding["severity"] == "warning")
        if not blocking and score < float(profile["dimension_floor"]):
            failures.append({
                "id": f"chapter-synthesis-{key}", "owner": "qa_reviewer",
                "message": "Chapter synthesis is below the required floor; return concrete located defects before assigning a writer repair.",
                "metric": score, "threshold": profile["dimension_floor"],
            })
    return metrics, failures, warnings
