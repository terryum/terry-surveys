"""CLI controller for the action-first tutorial harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from shared.scaffold import create_tutorial
from .input import normalize_input
from .quality import content_digest, evaluate, write_scorecard
from .state import (
    block_task,
    build_tasks,
    complete_task,
    load_state,
    new_state,
    ready_chapter_digests,
    ready_tasks,
    repo_root,
    resume_state,
    save_state,
    start_task,
    state_path,
    summarize,
    tutorial_dir,
)


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _next_tutorial_number(root: Path) -> int:
    registry = root.parent / "terryum-ai/projects/surveys/surveys.json"
    if registry.is_file():
        try:
            value = json.loads(registry.read_text(encoding="utf-8")).get("next_tutorial_number")
            if isinstance(value, int) and value > 0:
                return value
        except (OSError, json.JSONDecodeError):
            pass
    numbers = []
    for path in (root / "surveys").glob("*/survey.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data.get("tutorial_number"), int):
            numbers.append(data["tutorial_number"])
    return max(numbers, default=0) + 1


def command_scaffold(args, root: Path) -> int:
    number = args.tutorial_number or _next_tutorial_number(root)
    path = Path(create_tutorial(args.slug, root / "surveys", number))
    normalize_input(root, path, prompt=args.prompt, file_path=args.file, chatgpt_url=args.chatgpt_url, chatgpt_html=args.chatgpt_html)
    emit({"slug": args.slug, "tutorial_number": number, "path": str(path), "visibility": "private", "status": "wip"})
    return 0


def command_input(args, root: Path) -> int:
    manifest = normalize_input(root, tutorial_dir(root, args.slug), prompt=args.prompt, file_path=args.file, chatgpt_url=args.chatgpt_url, chatgpt_html=args.chatgpt_html)
    emit({"manifest": str(manifest)})
    return 0


def command_init(args, root: Path) -> int:
    path = state_path(root, args.slug)
    if path.exists() and not args.force:
        raise FileExistsError(f"state already exists: {path}; use --force or reopen")
    selected = [args.chapter] if args.chapter is not None else None
    state = new_state(root, args.slug, selected)
    save_state(root, state, replace=args.force)
    emit(summarize(state))
    return 0


def command_status(args, root: Path) -> int:
    emit(summarize(load_state(root, args.slug)))
    return 0


def command_next(args, root: Path) -> int:
    state = load_state(root, args.slug)
    emit({"tasks": ready_tasks(state, args.limit)})
    return 0


def command_start(args, root: Path) -> int:
    state = load_state(root, args.slug)
    start_task(state, args.task, args.agent_id)
    save_state(root, state)
    emit({"task": args.task, "status": "running"})
    return 0


def command_complete(args, root: Path) -> int:
    state = load_state(root, args.slug)
    complete_task(root, state, args.task)
    save_state(root, state)
    emit({"task": args.task, "status": "completed", "run_status": state["status"]})
    return 0


def command_block(args, root: Path) -> int:
    state = load_state(root, args.slug)
    block_task(state, args.task, args.reason)
    save_state(root, state)
    emit({"task": args.task, "status": "blocked", "reason": args.reason})
    return 0


def command_resume(args, root: Path) -> int:
    state = load_state(root, args.slug)
    reopened = resume_state(root, state)
    save_state(root, state)
    result = summarize(state)
    result["reopened_tasks"] = reopened
    emit(result)
    return 0


def command_sync_roadmap(args, root: Path) -> int:
    state = load_state(root, args.slug)
    base = tutorial_dir(root, args.slug)
    if state.get("selection_mode") == "selected":
        chapters = state["selected_chapters"]
    else:
        data = json.loads((base / "survey.json").read_text(encoding="utf-8"))
        chapters = sorted({int(ch["num"]) for part in data.get("parts", []) for ch in part.get("chapters", [])})
    old = {task["id"]: task for task in state["tasks"]}
    tasks = build_tasks(chapters)
    for task in tasks:
        if task["id"] in {"normalize-input", "roadmap"} and old.get(task["id"], {}).get("status") == "completed":
            task.update(old[task["id"]])
    state["tasks"] = tasks
    state["selected_chapters"] = chapters
    state["protected_ready_chapters"] = ready_chapter_digests(base, set(chapters))
    save_state(root, state)
    emit(summarize(state))
    return 0


def command_reopen(args, root: Path) -> int:
    old = load_state(root, args.slug)
    state = new_state(root, args.slug, [args.chapter])
    state["revision"] = old["revision"]
    save_state(root, state, replace=True)
    emit(summarize(state))
    return 0


def command_feedback(args, root: Path) -> int:
    base = tutorial_dir(root, args.slug)
    record = {
        "chapter": args.chapter,
        "result": args.result,
        "environment": json.loads(args.environment_json),
        "notes": args.notes,
    }
    ledger = base / "_tutorial/user_validation.jsonl"
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    old = load_state(root, args.slug)
    state = new_state(root, args.slug, [args.chapter])
    state["revision"] = old["revision"]
    save_state(root, state, replace=True)
    emit({"recorded": record, "reopened": args.chapter})
    return 0


def command_score(args, root: Path) -> int:
    state = load_state(root, args.slug)
    incomplete = [task["id"] for task in state["tasks"] if task["phase"] != "release" and task["status"] not in {"completed", "skipped"}]
    if incomplete:
        raise ValueError("cannot score before production tasks complete: " + ", ".join(incomplete))
    scorecard = evaluate(tutorial_dir(root, args.slug))
    if args.write:
        write_scorecard(tutorial_dir(root, args.slug), scorecard)
    state["quality"]["last_scorecard"] = scorecard
    state["status"] = "ready_for_preview" if scorecard["passed"] else "blocked"
    save_state(root, state)
    emit(scorecard)
    return 0 if scorecard["passed"] else 2


def _artifact_map(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"release artifact must be KEY=VALUE: {item}")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def command_release(args, root: Path) -> int:
    state = load_state(root, args.slug)
    base = tutorial_dir(root, args.slug)
    channel = args.channel
    if args.status == "blocked":
        state["status"] = "deploy_blocked"
        state["release"][channel] = "blocked"
        state["release"]["blocked_reason"] = args.reason
        save_state(root, state)
        emit({"channel": channel, "status": "blocked", "reason": args.reason})
        return 0
    scorecard = state.get("quality", {}).get("last_scorecard") or {}
    if not scorecard.get("passed") or scorecard.get("content_digest") != content_digest(base):
        raise ValueError("release requires a passing score for the current content digest")
    if args.status == "running":
        state["release"][channel] = "running"
        save_state(root, state)
        emit({"channel": channel, "status": "running", "content_digest": scorecard["content_digest"]})
        return 0
    artifacts = _artifact_map(args.artifact)
    receipt = {"channel": channel, "content_digest": scorecard["content_digest"], **artifacts}
    if channel == "preview":
        required = {"content_commit", "framework_commit", "gallery_commit", "pages_url", "workflow_id", "anonymous", "member", "admin_ko", "admin_en"}
        missing = sorted(required - set(artifacts))
        if missing:
            raise ValueError("preview release artifacts missing: " + ", ".join(missing))
        receipt["access"] = {key: artifacts.pop(key) for key in ("anonymous", "member", "admin_ko", "admin_en")}
        receipt.pop("anonymous", None); receipt.pop("member", None); receipt.pop("admin_ko", None); receipt.pop("admin_en", None)
        path = base / "_quality/releases/preview.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        task = next(task for task in state["tasks"] if task["id"] == "deploy-preview")
        if task["status"] == "pending":
            start_task(state, "deploy-preview", f"release-orchestrator-{state['run_id']}")
        complete_task(root, state, "deploy-preview")
    else:
        preview = base / "_quality/releases/preview.json"
        if not preview.is_file() or json.loads(preview.read_text(encoding="utf-8")).get("content_digest") != scorecard["content_digest"]:
            raise ValueError("production must promote the exact approved preview snapshot")
        required = {"content_commit", "framework_commit", "gallery_commit", "pages_url", "workflow_id", "live_ko", "live_en"}
        missing = sorted(required - set(artifacts))
        if missing:
            raise ValueError("production release artifacts missing: " + ", ".join(missing))
        path = base / "_quality/releases/production.json"
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        survey_path = base / "survey.json"
        survey = json.loads(survey_path.read_text(encoding="utf-8"))
        survey["visibility"] = "public"
        survey_path.write_text(json.dumps(survey, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state["status"] = "released"
        state["release"]["production"] = "released"
    save_state(root, state)
    emit({"channel": channel, "status": "released", "receipt": str(path)})
    return 0


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--repo-root")
    sub = command.add_subparsers(dest="command", required=True)

    def input_arguments(item):
        item.add_argument("--prompt")
        item.add_argument("--file")
        item.add_argument("--chatgpt-url")
        item.add_argument("--chatgpt-html")

    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("slug")
    scaffold.add_argument("--tutorial-number", type=int)
    input_arguments(scaffold)
    scaffold.set_defaults(func=command_scaffold)
    inputs = sub.add_parser("input")
    inputs.add_argument("slug")
    input_arguments(inputs)
    inputs.set_defaults(func=command_input)
    init = sub.add_parser("init")
    init.add_argument("slug")
    init.add_argument("--chapter", type=int)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)
    for name, function in (("status", command_status), ("resume", command_resume), ("sync-roadmap", command_sync_roadmap)):
        item = sub.add_parser(name); item.add_argument("slug"); item.set_defaults(func=function)
    nxt = sub.add_parser("next"); nxt.add_argument("slug"); nxt.add_argument("--limit", type=int); nxt.set_defaults(func=command_next)
    start = sub.add_parser("start"); start.add_argument("slug"); start.add_argument("task"); start.add_argument("--agent-id", required=True); start.set_defaults(func=command_start)
    complete = sub.add_parser("complete"); complete.add_argument("slug"); complete.add_argument("task"); complete.set_defaults(func=command_complete)
    block = sub.add_parser("block"); block.add_argument("slug"); block.add_argument("task"); block.add_argument("--reason", required=True); block.set_defaults(func=command_block)
    reopen = sub.add_parser("reopen"); reopen.add_argument("slug"); reopen.add_argument("--chapter", type=int, required=True); reopen.set_defaults(func=command_reopen)
    feedback = sub.add_parser("feedback"); feedback.add_argument("slug"); feedback.add_argument("--chapter", type=int, required=True); feedback.add_argument("--result", choices=["success", "failure"], required=True); feedback.add_argument("--environment-json", default="{}"); feedback.add_argument("--notes", required=True); feedback.set_defaults(func=command_feedback)
    score = sub.add_parser("score"); score.add_argument("slug"); score.add_argument("--write", action="store_true"); score.set_defaults(func=command_score)
    release = sub.add_parser("release"); release.add_argument("slug"); release.add_argument("channel", choices=["preview", "production"]); release.add_argument("status", choices=["running", "released", "blocked"]); release.add_argument("--artifact", action="append", default=[]); release.add_argument("--reason"); release.set_defaults(func=command_release)
    return command


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        root = repo_root(args.repo_root)
        return args.func(args, root)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
