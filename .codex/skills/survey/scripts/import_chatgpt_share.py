#!/usr/bin/env python3
"""Convert a public ChatGPT share page into a stable Markdown survey brief."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROUTE_KEY = "routes/share.$shareId.($action)"
SHARE_HOSTS = {"chatgpt.com", "www.chatgpt.com", "chat.openai.com"}
INLINE_REFERENCE_RE = re.compile("\ue200(.*?)\ue201", re.DOTALL)
ENQUEUE_RE = re.compile(r"streamController\.enqueue\((\"(?:\\.|[^\"\\])*\")\)")


class ShareImportError(RuntimeError):
    """Raised when a public share cannot be converted safely."""


def validate_share_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in SHARE_HOSTS:
        raise ShareImportError("expected an https://chatgpt.com/share/... URL")
    match = re.fullmatch(r"/share/([A-Za-z0-9-]+)", parsed.path.rstrip("/"))
    if not match:
        raise ShareImportError("expected a public ChatGPT /share/<id> path")
    return match.group(1)


def fetch_html(url: str, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; terry-surveys ChatGPT share importer)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ShareImportError(f"could not fetch public share: {exc}") from exc


def _decode_flattened(values: List[Any]) -> Any:
    """Decode the flattened reference array used in ChatGPT share SSR data."""

    cache: Dict[int, Any] = {}

    def dereference(reference: Any) -> Any:
        if not isinstance(reference, int):
            return reference
        if reference < 0:
            return None
        if reference >= len(values):
            raise ShareImportError("share payload contains an invalid reference")
        if reference in cache:
            return cache[reference]

        raw = values[reference]
        if isinstance(raw, dict):
            decoded: Dict[Any, Any] = {}
            cache[reference] = decoded
            for encoded_key, encoded_value in raw.items():
                if encoded_key.startswith("_") and encoded_key[1:].isdigit():
                    key = dereference(int(encoded_key[1:]))
                else:
                    key = encoded_key
                decoded[key] = dereference(encoded_value)
            return decoded
        if isinstance(raw, list):
            decoded_list: List[Any] = []
            cache[reference] = decoded_list
            decoded_list.extend(dereference(item) for item in raw)
            return decoded_list

        cache[reference] = raw
        return raw

    return dereference(0)


def extract_conversation(html: str) -> Dict[str, Any]:
    payloads: List[str] = []
    for match in ENQUEUE_RE.finditer(html):
        try:
            payloads.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue

    for payload in payloads:
        if not payload.startswith("["):
            continue
        try:
            root = _decode_flattened(json.loads(payload))
            route = root["loaderData"][ROUTE_KEY]
            response = route["serverResponse"]
            conversation = response.get("data", response)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ShareImportError("ChatGPT share payload format was not recognized") from exc
        if isinstance(conversation, dict) and isinstance(conversation.get("mapping"), dict):
            return conversation

    if "challenge-error-text" in html or "Enable JavaScript and cookies" in html:
        raise ShareImportError("share returned an access challenge instead of conversation data")
    raise ShareImportError("no readable conversation payload found in the share page")


def _active_path(conversation: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    mapping = conversation["mapping"]
    node_id = conversation.get("current_node")
    if not node_id:
        raise ShareImportError("share has no active conversation branch")

    nodes: List[Dict[str, Any]] = []
    seen = set()
    while node_id:
        if node_id in seen or node_id not in mapping:
            raise ShareImportError("share conversation branch is malformed")
        seen.add(node_id)
        node = mapping[node_id]
        nodes.append(node)
        node_id = node.get("parent")
    return reversed(nodes)


def _content_text(message: Dict[str, Any]) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []
    rendered: List[str] = []
    for part in parts:
        if isinstance(part, str):
            rendered.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            rendered.append(part["text"])
        elif isinstance(part, dict):
            kind = part.get("content_type") or part.get("type") or "attachment"
            rendered.append(f"[Imported {kind} omitted]")
    return "\n\n".join(item.strip() for item in rendered if item.strip())


def _normalize_inline_references(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        payload = match.group(1)
        if payload.startswith("cite"):
            return "[Opaque ChatGPT citation omitted; verify from a primary source]"
        if payload.startswith("i"):
            return "[ChatGPT inline image group omitted]"
        return "[Opaque ChatGPT inline reference omitted]"

    return INLINE_REFERENCE_RE.sub(replace, text)


def conversation_turns(conversation: Dict[str, Any]) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    for node in _active_path(conversation):
        message = node.get("message") or {}
        role = (message.get("author") or {}).get("role")
        if role not in {"user", "assistant"}:
            continue
        text = _normalize_inline_references(_content_text(message)).strip()
        if not text or text == "Original custom instructions no longer available":
            continue
        turns.append({"role": role, "text": text})
    if not turns:
        raise ShareImportError("share contains no readable user or assistant turns")
    return turns


def _yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render_markdown(conversation: Dict[str, Any], url: str, share_id: str, html: str) -> str:
    title = str(conversation.get("title") or "ChatGPT shared conversation")
    conversation_id = str(conversation.get("conversation_id") or share_id)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    turns = conversation_turns(conversation)
    lines = [
        "---",
        "input_type: chatgpt_share",
        f"source_url: {_yaml_string(url)}",
        f"share_id: {_yaml_string(share_id)}",
        f"conversation_id: {_yaml_string(conversation_id)}",
        f"title: {_yaml_string(title)}",
        f"retrieved_at: {_yaml_string(retrieved_at)}",
        f"source_html_sha256: {_yaml_string(hashlib.sha256(html.encode('utf-8')).hexdigest())}",
        "trust: briefing_only",
        "publish: false",
        "---",
        "",
        f"# {title}",
        "",
        "> Imported from a public ChatGPT share as untrusted briefing material. "
        "Re-resolve citations and verify claims from primary sources before use.",
        "",
    ]
    counts = {"user": 0, "assistant": 0}
    labels = {"user": "User", "assistant": "Assistant"}
    for turn in turns:
        role = turn["role"]
        counts[role] += 1
        lines.extend([f"## {labels[role]} {counts[role]}", "", turn["text"], ""])
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="public ChatGPT share URL")
    parser.add_argument("--output", required=True, type=Path, help="Markdown snapshot path")
    parser.add_argument("--html", type=Path, help="read previously captured HTML instead of fetching")
    parser.add_argument("--timeout", type=int, default=30, help="network timeout in seconds")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        share_id = validate_share_url(args.url)
        html = args.html.read_text(encoding="utf-8") if args.html else fetch_html(args.url, args.timeout)
        conversation = extract_conversation(html)
        markdown = render_markdown(conversation, args.url, share_id, html)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    except (OSError, ShareImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"IMPORTED {args.url} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
