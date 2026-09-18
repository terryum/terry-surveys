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
        failures.extend(finding_failure(finding, key) for finding in blocking)
        warnings.extend(finding_failure(finding, key) for finding in data["findings"] if finding["severity"] == "warning")
        if score < float(profile["dimension_floor"]):
            failures.append({
                "id": f"chapter-synthesis-{key}", "owner": "qa_reviewer",
                "message": "Chapter synthesis is below the required floor; return concrete located defects before assigning a writer repair.",
                "metric": score, "threshold": profile["dimension_floor"],
            })
    return metrics, failures, warnings
