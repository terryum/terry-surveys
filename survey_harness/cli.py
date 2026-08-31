"""Command line controller for the survey v2 harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.parse import urljoin
from pathlib import Path
from typing import Any, Dict, Tuple

from .quality import content_digest, evaluate, write_scorecard
from .state import (
    block_task,
    completed_task_errors,
    complete_task,
    content_repo_root,
    load_state,
    migrate_legacy_state,
    new_state,
    plan_remediation,
    ready_tasks,
    record_score,
    release_receipt_errors,
    repo_root,
    resume_state,
    save_state,
    start_task,
    state_path,
    summarize,
    update_release,
    validate_state,
)


def emit(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _checked(command, cwd: Path, label: str, timeout: int = 45, env: Dict[str, str] | None = None) -> Dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:1200]
        raise ValueError(f"release verification failed ({label}): {detail}")
    return {"label": label, "command": command, "exit_code": result.returncode, "stdout": result.stdout.strip()}


class _IframeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "iframe":
            values = dict(attrs)
            if values.get("src"):
                self.sources.append(values["src"])


def _survey_visibility(root: Path, slug: str) -> str:
    try:
        payload = json.loads((root / "surveys" / slug / "survey.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "public"
    return str(payload.get("visibility") or "public").casefold()


def _normalize_kg_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def _expected_kg_ids(root: Path, slug: str) -> set[str]:
    try:
        payload = json.loads((root / "bibtex" / "refs_index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    expected = set()
    for paper in payload.get("papers", {}).values():
        if not isinstance(paper, dict) or not any(
            isinstance(location, dict) and location.get("survey") == slug
            for location in paper.get("locations", [])
        ):
            continue
        ids = paper.get("ids", {}) if isinstance(paper.get("ids"), dict) else {}
        arxiv = [re.sub(r"v\d+$", "", str(item).casefold().replace("arxiv:", "").strip()) for item in ids.get("arxiv", []) if str(item).strip()]
        doi = [str(item).casefold().replace("https://doi.org/", "").replace("doi:", "").strip() for item in ids.get("doi", []) if str(item).strip()]
        nature = [str(item).casefold().strip() for item in ids.get("nature", []) if str(item).strip()]
        bibtex_keys = [str(item).strip() for item in paper.get("bibtex_keys", []) if str(item).strip()]
        title = _normalize_kg_title(str(paper.get("title") or ""))
        if arxiv:
            expected.add(f"arxiv:{arxiv[0]}")
        elif doi:
            expected.add(f"doi:{doi[0]}")
        elif nature:
            expected.add(f"doi:{nature[0] if nature[0].startswith('10.') else '10.1038/' + nature[0]}")
        elif bibtex_keys:
            expected.add(f"bib:{bibtex_keys[0]}")
        elif title:
            expected.add(f"title:{title}")
    return expected


def _committed_content_digest(root: Path, slug: str, content_commit: str, framework_commit: str | None = None) -> str:
    with tempfile.TemporaryDirectory(prefix="survey-release-commit-") as tmp:
        temp = Path(tmp)
        extracted = temp / "repo"
        extracted.mkdir()
        if framework_commit:
            archives = (
                (content_repo_root(root), content_commit, [f"surveys/{slug}"], "content"),
                (root, framework_commit, ["survey_harness/config/quality_profiles.yaml", "survey_harness/quality.py"], "framework"),
            )
        else:
            archives = ((root, content_commit, [f"surveys/{slug}", "survey_harness/config/quality_profiles.yaml", "survey_harness/quality.py"], "legacy"),)
        for repository, commit, paths, label in archives:
            archive = temp / f"{label}.tar"
            command = ["git", "archive", "--format=tar", f"--output={archive}", commit, *paths]
            result = subprocess.run(command, cwd=repository, capture_output=True, text=True, timeout=45)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()[:1200]
                raise ValueError(f"release verification failed ({label} commit archive): {detail}")
            with tarfile.open(archive) as bundle:
                bundle.extractall(extracted)
        return content_digest(extracted / "surveys" / slug, extracted / "survey_harness/config/quality_profiles.yaml", extracted / "survey_harness/quality.py")


def _verify_release_evidence(root: Path, slug: str, evidence: Dict[str, str], expected_digest: str, expected_kg_min: int, layout: str = "legacy-monorepo") -> Tuple[str, str]:
    commit_keys = ("content_commit", "framework_commit") if layout == "split-v1" else ("survey_commit",)
    required = ("pages_url", "live_ko_url", "live_en_url", "gallery_commit", "workflow_id", *commit_keys)
    missing = [key for key in required if not evidence.get(key)]
    if missing:
        raise ValueError(f"external release verification missing: {', '.join(missing)}")
    if not re.fullmatch(r"\d+", str(evidence["workflow_id"])):
        raise ValueError("workflow_id must be numeric before GitHub verification")
    gallery_root = root.parent / "terryum-ai"
    if not (gallery_root / ".git").exists():
        raise ValueError(f"gallery repository unavailable for release verification: {gallery_root}")
    checks = []
    repositories = [(gallery_root, evidence["gallery_commit"], "gallery-commit")]
    if layout == "split-v1":
        repositories.extend(((content_repo_root(root), evidence["content_commit"], "content-commit"), (root, evidence["framework_commit"], "framework-commit")))
    else:
        repositories.append((root, evidence["survey_commit"], "survey-commit"))
    for repo, sha, label in repositories:
        checks.append(_checked(["git", "cat-file", "-e", f"{sha}^{{commit}}"], repo, label))
        remote = _checked(["git", "branch", "-r", "--contains", sha], repo, f"{label}-remote")
        if not remote["stdout"]:
            raise ValueError(f"release verification failed ({label}): commit is not on a fetched remote branch")
        checks.append(remote)
    committed_digest = _committed_content_digest(
        root,
        slug,
        evidence["content_commit"] if layout == "split-v1" else evidence["survey_commit"],
        evidence.get("framework_commit") if layout == "split-v1" else None,
    )
    if committed_digest != expected_digest:
        raise ValueError("release verification failed: committed content/framework do not reproduce the scored manuscript/evidence digest")
    checks.append({"label": "scored-content-commit", "content_digest": committed_digest, "expected_digest": expected_digest, "exit_code": 0})
    workflow = _checked(["gh", "run", "view", str(evidence["workflow_id"]), "--json", "conclusion,headSha,url"], gallery_root, "workers-workflow")
    workflow_data = json.loads(workflow["stdout"])
    if workflow_data.get("conclusion") != "success" or not str(workflow_data.get("headSha", "")).startswith(str(evidence["gallery_commit"])):
        raise ValueError("release verification failed: workflow is not successful or is not bound to gallery_commit")
    checks.append(workflow)
    parsed_urls = {key: urlparse(str(evidence[key])) for key in ("pages_url", "live_ko_url", "live_en_url")}
    if parsed_urls["live_ko_url"].path.rstrip("/") != f"/ko/surveys/{slug}" or parsed_urls["live_en_url"].path.rstrip("/") != f"/en/surveys/{slug}":
        raise ValueError("release verification failed: live KO/EN URLs must be the exact survey detail routes")
    live_content = {}
    for key in ("pages_url", "live_ko_url", "live_en_url"):
        check = _checked(["curl", "-fsSL", "--max-time", "30", str(evidence[key])], root, key)
        content = check["stdout"].casefold()
        if "<html" not in content or slug.casefold() not in content:
            raise ValueError(f"release verification failed ({key}): response is not HTML bound to the survey slug")
        live_content[key] = content
        checks.append(check)
    pages_origin = f"{parsed_urls['pages_url'].scheme}://{parsed_urls['pages_url'].netloc}"
    if _survey_visibility(root, slug) == "private":
        private_env = dict(os.environ)
        private_env["TEST_BASE_URL"] = f"{parsed_urls['live_ko_url'].scheme}://{parsed_urls['live_ko_url'].netloc}"
        checks.append(_checked(
            ["node", "scripts/test-visibility-access.mjs"],
            gallery_root,
            "private-live-access",
            timeout=300,
            env=private_env,
        ))
    else:
        for lang, key in (("ko", "live_ko_url"), ("en", "live_en_url")):
            parser = _IframeParser()
            parser.feed(live_content[key])
            resolved = [urljoin(str(evidence[key]), source) for source in parser.sources]
            expected_prefix = urljoin(str(evidence["pages_url"]).rstrip("/") + "/", f"{lang}/")
            matching = [source for source in resolved if source.startswith(expected_prefix) and source.startswith(pages_origin)]
            if not matching or any(marker in live_content[key] for marker in ("404 not found", "page not found", "페이지를 찾을 수")):
                raise ValueError(f"release verification failed ({key}): an iframe bound to {expected_prefix} is missing or not-found content was detected")
            iframe_check = _checked(["curl", "-fsSL", "--max-time", "30", matching[0]], root, f"iframe-{lang}")
            if "<html" not in iframe_check["stdout"].casefold():
                raise ValueError(f"release verification failed (iframe-{lang}): iframe document is not HTML")
            checks.append(iframe_check)
    asset_script = root / ".codex/skills/survey/scripts/validate_gallery_assets.py"
    checks.append(_checked([sys.executable, str(asset_script), slug, "--terryum-ai-root", str(gallery_root)], root, "asset-validation"))
    kg_path = root.parent / "terry-papers" / "knowledge-index.json"
    try:
        kg_data = json.loads(kg_path.read_text(encoding="utf-8"))
        candidates = kg_data.get("candidate_index", {}).get("candidates", [])
        backref_count = sum(
            1 for candidate in candidates if isinstance(candidate, dict)
            and any(isinstance(backref, dict) and backref.get("survey") == slug for backref in candidate.get("survey_backrefs", []))
        )
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"release verification failed (kg-sync): {exc}")
    expected_ids = _expected_kg_ids(root, slug)
    if not expected_ids:
        raise ValueError("release verification failed (kg-sync): current reference index has no canonical IDs for the survey")
    actual_ids = {
        str(candidate.get("canonical_id")) for candidate in candidates if isinstance(candidate, dict)
        and any(isinstance(backref, dict) and backref.get("survey") == slug for backref in candidate.get("survey_backrefs", []))
    }
    coverage = len(expected_ids.intersection(actual_ids)) / max(1, len(expected_ids))
    current_kg_sha = hashlib.sha256(kg_path.read_bytes()).hexdigest()
    baseline_kg_sha = str(evidence.get("kg_baseline_sha256") or "")
    if backref_count < expected_kg_min or coverage < 0.9 or not baseline_kg_sha or current_kg_sha == baseline_kg_sha:
        raise ValueError(f"release verification failed (kg-sync): {backref_count} candidate backrefs; requires {expected_kg_min}")
    checks.append({"label": "kg-sync", "path": str(kg_path), "backref_count": backref_count, "minimum": expected_kg_min, "expected_id_coverage": round(coverage, 4), "before_sha256": baseline_kg_sha, "sha256": current_kg_sha, "exit_code": 0})
    receipt_checks = []
    for check in checks:
        item = dict(check)
        stdout = str(item.pop("stdout", ""))
        if stdout:
            item["stdout_sha256"] = hashlib.sha256(stdout.encode("utf-8")).hexdigest()
            item["stdout_preview"] = stdout[:4000]
        receipt_checks.append(item)
    receipt = {"schema_version": "2.0", "slug": slug, "content_digest": expected_digest, "checks": receipt_checks}
    receipt_path = root / "surveys" / slug / "_quality" / "release_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    receipt_path.write_bytes(payload)
    return str(receipt_path.relative_to(root / "surveys" / slug)), hashlib.sha256(payload).hexdigest()


def command_init(args, root: Path) -> int:
    path = state_path(root, args.slug)
    if path.exists() and not args.force:
        raise FileExistsError(f"state already exists: {path}; use --force to reinitialize")
    state = new_state(root, args.slug, args.profile, args.deploy)
    save_state(root, state, replace=args.force)
    emit(summarize(state))
    return 0


def command_status(args, root: Path) -> int:
    emit(summarize(load_state(root, args.slug)))
    return 0


def command_next(args, root: Path) -> int:
    state = load_state(root, args.slug)
    tasks = ready_tasks(state, args.limit)
    emit({"slug": args.slug, "capacity": len(tasks), "tasks": tasks})
    return 0


def command_start(args, root: Path) -> int:
    state = load_state(root, args.slug)
    start_task(state, args.task, args.agent_id)
    save_state(root, state)
    emit({"task": args.task, "status": "running"})
    return 0


def command_complete(args, root: Path) -> int:
    state = load_state(root, args.slug)
    complete_task(root, state, args.task, args.artifact)
    save_state(root, state)
    emit({"task": args.task, "status": "completed"})
    return 0


def command_block(args, root: Path) -> int:
    state = load_state(root, args.slug)
    block_task(state, args.task, args.reason)
    save_state(root, state)
    emit({"task": args.task, "status": "blocked", "reason": args.reason})
    return 0


def command_score(args, root: Path) -> int:
    if (args.record or args.plan_remediation) and not args.write:
        raise ValueError("recorded scoring and remediation planning require --write for an auditable scorecard")
    scorecard = evaluate(root, args.slug, args.profile)
    output = write_scorecard(root, args.slug, scorecard) if args.write else None
    if args.record or args.plan_remediation:
        state = load_state(root, args.slug)
        incomplete = [task["id"] for task in state["tasks"] if task["status"] not in {"completed", "skipped"}]
        if incomplete:
            raise ValueError(f"cannot record quality before production tasks complete: {', '.join(incomplete[:12])}")
        invalid = completed_task_errors(root, state)
        if invalid:
            preview = "; ".join(f"{task}: {error}" for task, error in list(invalid.items())[:8])
            raise ValueError(f"cannot record quality with invalid completed tasks: {preview}")
        rel = str(output.relative_to(root / "surveys" / args.slug)) if output else "_quality/scorecard.json"
        record_score(state, rel, scorecard)
        created = plan_remediation(state, scorecard["hard_blockers"]) if args.plan_remediation and not scorecard["passed"] else []
        save_state(root, state)
        scorecard["remediation_tasks"] = [task["id"] for task in created]
    emit(scorecard)
    return 0 if scorecard["passed"] else 2


def command_remediate(args, root: Path) -> int:
    score_path = root / "surveys" / args.slug / "_quality" / "scorecard.json"
    if not score_path.exists():
        raise FileNotFoundError(f"scorecard missing; run score --write first: {score_path}")
    scorecard = json.loads(score_path.read_text(encoding="utf-8"))
    state = load_state(root, args.slug)
    tasks = plan_remediation(state, scorecard.get("hard_blockers", []))
    save_state(root, state)
    emit({"status": state["status"], "created": tasks, "blocked_reason": state["quality"].get("blocked_reason")})
    return 0 if tasks else 2


def command_resume(args, root: Path) -> int:
    state = load_state(root, args.slug)
    reopened = resume_state(root, state)
    save_state(root, state)
    result = summarize(state)
    result["reopened_tasks"] = reopened
    emit(result)
    return 0


def command_verify(args, root: Path) -> int:
    state = load_state(root, args.slug)
    validate_state(state)
    errors = completed_task_errors(root, state)
    receipt_errors = release_receipt_errors(root, state)
    result = {"valid": not errors and not receipt_errors, "completed_task_errors": errors, "release_receipt_errors": receipt_errors, "summary": summarize(state)}
    emit(result)
    return 0 if not errors and not receipt_errors else 1


def command_migrate(args, root: Path) -> int:
    path = state_path(root, args.slug)
    if path.exists() and not args.force:
        raise FileExistsError(f"v2 state already exists: {path}; use --force to replace it")
    state = migrate_legacy_state(root, args.slug, args.profile)
    save_state(root, state, replace=args.force)
    emit(summarize(state))
    return 0


def command_release(args, root: Path) -> int:
    state = load_state(root, args.slug)
    if args.status in {"running", "released"}:
        invalid = completed_task_errors(root, state)
        if invalid:
            preview = "; ".join(f"{task}: {error}" for task, error in list(invalid.items())[:8])
            raise ValueError(f"release blocked by invalid completed tasks: {preview}")
        fresh = evaluate(root, args.slug, state["profile"])
        history = state.get("quality", {}).get("history", [])
        if not fresh["passed"]:
            blockers = ", ".join(item["id"] for item in fresh.get("hard_blockers", [])[:12])
            raise ValueError(f"release blocked because fresh quality evaluation failed: {blockers}")
        if not history or history[-1].get("content_digest") != fresh.get("content_digest"):
            raise ValueError("release blocked because the manuscript changed after the latest recorded score; rerun score --write --record")
    artifacts = {}
    for item in args.artifact:
        if "=" not in item:
            raise ValueError(f"release artifact must be KEY=VALUE: {item!r}")
        key, value = item.split("=", 1)
        artifacts[key] = value
    if args.status == "running":
        kg_path = root.parent / "terry-papers" / "knowledge-index.json"
        if not kg_path.is_file():
            raise ValueError(f"KG baseline unavailable: {kg_path}")
        artifacts["kg_baseline_sha256"] = hashlib.sha256(kg_path.read_bytes()).hexdigest()
    if args.status == "released":
        effective = dict(state.get("release", {}).get("artifacts", {}))
        effective.update(artifacts)
        expected_digest = str(state.get("quality", {}).get("history", [])[-1].get("content_digest") or "")
        expected_kg_min = int(fresh.get("metrics", {}).get("primary_id_references", 1))
        receipt_rel, receipt_sha = _verify_release_evidence(root, args.slug, effective, expected_digest, expected_kg_min, str(state.get("repository_layout") or "legacy-monorepo"))
        artifacts["release_receipt"] = receipt_rel
        artifacts["release_receipt_sha256"] = receipt_sha
        artifacts.update({"asset_validation": "passed", "workers_status": "success", "source_push": "passed", "kg_sync": "passed", "iframe_check": "passed", "not_found_check": "passed", "live_ko": "passed", "live_en": "passed"})
    update_release(state, args.status, args.reason, artifacts)
    receipt_errors = release_receipt_errors(root, state)
    if receipt_errors:
        raise ValueError("; ".join(receipt_errors))
    save_state(root, state)
    emit({"status": state["status"], "release": state["release"]})
    return 0


def _release_artifacts(items) -> Dict[str, str]:
    artifacts = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"release artifact must be KEY=VALUE: {item!r}")
        key, value = item.split("=", 1)
        if re.search(r"(?:secret|cookie|authorization|password)", key, re.I):
            raise ValueError("release receipts must not contain secrets, cookies, or authorization values")
        artifacts[key] = value
    return artifacts


def command_publication(args, root: Path) -> int:
    state = load_state(root, args.slug)
    base = root / "surveys" / args.slug
    channel = args.channel
    if args.status == "blocked":
        state["status"] = "deploy_blocked"
        state["release"]["status"] = "blocked"
        state["release"]["blocked_reason"] = args.reason
        save_state(root, state)
        emit({"channel": channel, "status": "blocked", "reason": args.reason})
        return 0
    fresh = evaluate(root, args.slug, state["profile"])
    history = state.get("quality", {}).get("history", [])
    if not fresh["passed"] or not history or history[-1].get("content_digest") != fresh.get("content_digest"):
        raise ValueError("publication requires a passing score for the current recorded digest")
    if args.status == "running":
        state["release"]["status"] = f"{channel}_running"
        save_state(root, state)
        emit({"channel": channel, "status": "running", "content_digest": fresh["content_digest"]})
        return 0
    artifacts = _release_artifacts(args.artifact)
    common = {"content_commit", "framework_commit", "gallery_commit", "workflow_id", "pages_url"}
    if channel == "preview":
        required = common | {"anonymous", "member", "admin_ko", "admin_en"}
        expected_host = f"{args.slug}-preview.pages.dev"
    else:
        required = common | {"live_ko", "live_en"}
        expected_host = f"{args.slug}.pages.dev"
    missing = sorted(required - set(artifacts))
    if missing:
        raise ValueError(f"{channel} publication artifacts missing: {', '.join(missing)}")
    if urlparse(artifacts["pages_url"]).hostname != expected_host:
        raise ValueError(f"{channel} pages_url must use {expected_host}")
    releases = base / "_quality/releases"
    releases.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": "1.0", "channel": channel, "content_digest": fresh["content_digest"], **artifacts}
    if channel == "preview":
        expected_access = {"anonymous": "denied", "member": "denied", "admin_ko": "passed", "admin_en": "passed"}
        if any(artifacts[key] != value for key, value in expected_access.items()):
            raise ValueError("preview access matrix failed")
        state["status"] = "preview_ready"
        state["release"]["status"] = "preview_released"
    else:
        preview = releases / "preview.json"
        if not preview.is_file() or json.loads(preview.read_text(encoding="utf-8")).get("content_digest") != fresh["content_digest"]:
            raise ValueError("production must promote the exact approved preview digest")
        survey_path = base / "survey.json"
        survey = json.loads(survey_path.read_text(encoding="utf-8"))
        survey["visibility"] = "public"
        survey_path.write_text(json.dumps(survey, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state["status"] = "released"
        state["release"]["status"] = "released"
    path = releases / f"{channel}.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_state(root, state)
    emit({"channel": channel, "status": "released", "receipt": str(path.relative_to(base))})
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", help="terry-surveys repository root; defaults to cwd")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a v2 task DAG")
    init.add_argument("slug")
    init.add_argument("--profile", choices=["full", "mini", "legacy_baseline"], default="full")
    init.add_argument("--deploy", choices=["auto", "off"])
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    status = sub.add_parser("status")
    status.add_argument("slug")
    status.set_defaults(func=command_status)

    nxt = sub.add_parser("next", help="emit runnable worker task packets")
    nxt.add_argument("slug")
    nxt.add_argument("--limit", type=int)
    nxt.set_defaults(func=command_next)

    start = sub.add_parser("start")
    start.add_argument("slug")
    start.add_argument("task")
    start.add_argument("--agent-id", required=True)
    start.set_defaults(func=command_start)

    complete = sub.add_parser("complete")
    complete.add_argument("slug")
    complete.add_argument("task")
    complete.add_argument("--artifact", action="append", default=[])
    complete.set_defaults(func=command_complete)

    block = sub.add_parser("block")
    block.add_argument("slug")
    block.add_argument("task")
    block.add_argument("--reason", required=True)
    block.set_defaults(func=command_block)

    score = sub.add_parser("score")
    score.add_argument("slug")
    score.add_argument("--profile", choices=["full", "mini", "legacy_baseline"], default="full")
    score.add_argument("--write", action="store_true")
    score.add_argument("--record", action="store_true")
    score.add_argument("--plan-remediation", action="store_true")
    score.set_defaults(func=command_score)

    remediate = sub.add_parser("remediate")
    remediate.add_argument("slug")
    remediate.set_defaults(func=command_remediate)

    resume = sub.add_parser("resume")
    resume.add_argument("slug")
    resume.set_defaults(func=command_resume)

    verify = sub.add_parser("verify")
    verify.add_argument("slug")
    verify.set_defaults(func=command_verify)

    migrate = sub.add_parser("migrate", help="convert legacy orchestration evidence to v2 state")
    migrate.add_argument("slug")
    migrate.add_argument("--profile", choices=["full", "mini", "legacy_baseline"], default="full")
    migrate.add_argument("--force", action="store_true")
    migrate.set_defaults(func=command_migrate)

    release = sub.add_parser("release", help="record the gated publication chain")
    release.add_argument("slug")
    release.add_argument("status", choices=["running", "released", "blocked"])
    release.add_argument("--reason")
    release.add_argument("--artifact", action="append", default=[], help="KEY=VALUE evidence such as pages_url=...")
    release.set_defaults(func=command_release)
    publication = sub.add_parser("publication", help="record protected preview or explicit production promotion")
    publication.add_argument("slug")
    publication.add_argument("channel", choices=["preview", "production"])
    publication.add_argument("status", choices=["running", "released", "blocked"])
    publication.add_argument("--artifact", action="append", default=[])
    publication.add_argument("--reason")
    publication.set_defaults(func=command_publication)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        root = repo_root(args.repo_root)
        return args.func(args, root)
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
