"""Small, runtime-neutral fingerprint and ownership primitives for both harnesses.

The domain controllers choose inputs, dependencies, and authorized writers.  This
module deliberately does not infer a DAG or silently accept a changed artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

_CACHE_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _chapter_number(value: Any) -> int | None:
    text = str(value).lower().strip()
    for prefix in ("chapter", "ch"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip(" -_")
            break
    return int(text) if text.isdigit() else None


def _chapter_view(value: Any, chapter: int, chapter_map: bool = False) -> Any:
    """Keep this chapter's records and unscoped metadata in JSON/JSONL inputs."""
    if isinstance(value, list):
        result = []
        for item in value:
            selected = _chapter_view(item, chapter)
            if selected is not _OMIT:
                result.append(selected)
        return result
    if not isinstance(value, dict):
        return value
    for field in ("chapter", "chapter_num", "chapter_hint", "chapter_hints", "chapters", "ch", "num"):
        marker = value.get(field)
        if marker is None or isinstance(marker, dict):
            continue
        markers = marker if isinstance(marker, list) else [marker]
        numbers = {_chapter_number(item) for item in markers} - {None}
        if numbers and chapter not in numbers:
            return _OMIT
    result = {}
    for key, child in value.items():
        number = _chapter_number(key) if chapter_map or str(key).lower().startswith("ch") else None
        if number is not None and number != chapter:
            continue
        selected = _chapter_view(child, chapter, chapter_map=key == "chapters" and isinstance(child, dict))
        if selected is not _OMIT:
            result[key] = selected
    return result


_OMIT = object()


def _without_keys(value: Any, ignored: set[str]) -> Any:
    if isinstance(value, dict):
        return {key: _without_keys(child, ignored) for key, child in value.items() if key not in ignored}
    if isinstance(value, list):
        return [_without_keys(child, ignored) for child in value]
    return value


def _relative(value: str) -> str:
    path = PurePosixPath(value.rstrip("/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"scope must stay within its root: {value}")
    return path.as_posix()


def _overlap(left: str, right: str) -> bool:
    left, right = _relative(left), _relative(right)
    return left == "." or right == "." or left == right or left.startswith(right + "/") or right.startswith(left + "/")


def ownership_conflicts(scopes: Iterable[str], other_scopes: Iterable[str]) -> list[str]:
    """Return conflicting filesystem scopes; shared files have one active writer."""
    other = list(other_scopes)
    return sorted({f"{left} <> {right}" for left in scopes for right in other if _overlap(left, right)})


def _fingerprint(roots: Mapping[str, Path], selector: dict[str, Any]) -> str:
    root = Path(roots[selector["root"]]).resolve()
    relative = _relative(selector["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"input escapes its root: {relative}")
    if not path.exists():
        return "missing"
    if path.is_dir():
        values = []
        for child in sorted(path.rglob("*")):
            rel = child.relative_to(path)
            if any(part in _CACHE_NAMES for part in rel.parts) or child.suffix in {".pyc", ".pyo"}:
                continue
            if any(_overlap(rel.as_posix(), ignored) for ignored in selector.get("exclude_paths", [])):
                continue
            if child.is_file():
                if not child.resolve().is_relative_to(root):
                    raise ValueError(f"input escapes its root: {child}")
                values.append((rel.as_posix(), hashlib.sha256(child.read_bytes()).hexdigest()))
        return hashlib.sha256(_canonical(values)).hexdigest()
    data = path.read_bytes()
    if "chapter" in selector or selector.get("ignore_keys"):
        if path.suffix == ".jsonl":
            value = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        else:
            value = json.loads(data)
        if "chapter" in selector:
            value = _chapter_view(value, int(selector["chapter"]))
            if value is _OMIT:
                value = None
        value = _without_keys(value, set(selector.get("ignore_keys", [])))
        data = _canonical(value)
    return hashlib.sha256(data).hexdigest()


def snapshot_inputs(roots: Mapping[str, Path], selectors: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"version": 1, "entries": [{"selector": dict(selector), "digest": _fingerprint(roots, selector)} for selector in selectors]}


def revalidate_inputs(roots: Mapping[str, Path], snapshot: dict[str, Any] | None, ignored_scopes: Iterable[str] = ()) -> list[str]:
    """Describe changed inputs.  A legacy completion without evidence is unverified."""
    if not snapshot or snapshot.get("version") != 1 or not isinstance(snapshot.get("entries"), list):
        return ["unverified input snapshot"]
    ignored = list(ignored_scopes)
    changed = []
    for entry in snapshot["entries"]:
        selector = entry["selector"]
        if selector["root"] == "content" and any(_covered(selector["path"], scope) for scope in ignored):
            continue
        if _fingerprint(roots, selector) != entry["digest"]:
            suffix = f"#ch{int(selector['chapter']):02d}" if "chapter" in selector else ""
            changed.append(f"{selector['root']}:{selector['path']}{suffix}")
    return changed


def refresh_owned_inputs(roots: Mapping[str, Path], snapshot: dict[str, Any], scopes: Iterable[str], root: str = "content") -> dict[str, Any]:
    """Accept only caller-authorized writes, after the controller checks lineage."""
    result = json.loads(json.dumps(snapshot))
    scopes = list(scopes)
    for entry in result["entries"]:
        selector = entry["selector"]
        if selector["root"] == root and any(_covered(selector["path"], scope) for scope in scopes):
            entry["digest"] = _fingerprint(roots, selector)
    return result


def _covered(path: str, scope: str) -> bool:
    path, scope = _relative(path), _relative(scope)
    return scope == "." or path == scope or path.startswith(scope + "/")
