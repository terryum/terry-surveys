#!/usr/bin/env python3
"""Image generation for survey book illustrations.

Calls BizRouter's `google/gemini-3-pro-image-preview` model via the OpenAI-
compatible chat completions endpoint. BizRouter proxies to Google's
Nano Banana Pro backend, so output quality matches Gemini direct.

Usage:
    python3 generate_image.py --prompt "description" --style "technical" --output "path.png"
    python3 generate_image.py --prompt "description" --style "technical" --output "path.png" --size "1536x1024"
"""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path

BIZROUTER_ENDPOINT = "https://api.bizrouter.ai/v1/chat/completions"
MODEL = "google/gemini-3-pro-image-preview"


def load_api_key():
    env_paths = [
        Path(__file__).resolve().parents[3] / ".env.local",
        Path.home() / ".env.local",
        Path.home() / ".config/claude-profiles/terry.env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    for prefix in ("BIZROUTER_API_KEY=", "export BIZROUTER_API_KEY="):
                        if line.startswith(prefix):
                            return line.split("=", 1)[1].strip().strip("'\"")

    key = os.environ.get("BIZROUTER_API_KEY")
    if key:
        return key

    print("ERROR: BIZROUTER_API_KEY not found.")
    print("Set it in ~/.config/claude-profiles/terry.env or project .env.local")
    sys.exit(1)


STYLE_PROMPTS = {
    "technical": (
        "Clean technical diagram with precise lines, white background, "
        "labeled components, engineering drawing style. "
        "No text in non-English languages. High detail, publication quality."
    ),
    "infographic": (
        "Educational infographic with icons, arrows, and visual hierarchy. "
        "Pastel color palette, clear layout, minimal text. "
        "Modern flat design style."
    ),
    "conceptual": (
        "Conceptual diagram showing relationships and flow. "
        "Abstract visualization with nodes and connections. "
        "Clean modern design with subtle gradients."
    ),
    "darkmode": (
        "Technical illustration on dark background (#0a0a0f). "
        "Bright colored lines (#00D4AA, #3498DB, #9B59B6, #FF6B35). "
        "Glowing edges, minimal style, suitable for dark-themed website."
    ),
    "academic": (
        "Academic paper figure style. Simple, clear, black and white "
        "with minimal color accents. Publication-ready quality. "
        "Suitable for IEEE journal 2-column format."
    ),
}


def _bizrouter_call(prompt: str, image_size: str = "2K", aspect_ratio: str = "16:9") -> bytes | None:
    api_key = load_api_key()
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
    })

    # Shell out to curl so corporate MITM CA handling works transparently.
    result = subprocess.run(
        [
            "curl", "-sS", "--fail-with-body", "-X", "POST", BIZROUTER_ENDPOINT,
            "-H", f"Authorization: Bearer {api_key}",
            "-H", "Content-Type: application/json",
            "--data-binary", "@-",
        ],
        input=body,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  curl failed ({result.returncode}): {result.stderr[:200]}")
        return None

    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  Bad JSON response: {result.stdout[:200]}")
        return None

    if "error" in resp:
        print(f"  API error: {resp['error']}")
        return None

    content = resp["choices"][0]["message"]["content"]
    if isinstance(content, str):
        print(f"  Text-only response (no image): {content[:150]}")
        return None
    for part in content:
        if part.get("type") == "image_url":
            data_url = part["image_url"]["url"]
            return base64.b64decode(data_url.split(",", 1)[1])
    return None


def _pick_aspect_ratio(size: str) -> str:
    try:
        w, h = map(int, size.split("x"))
        ratio = w / h
        if abs(ratio - 16 / 9) < 0.1:
            return "16:9"
        if abs(ratio - 9 / 16) < 0.1:
            return "9:16"
        if abs(ratio - 4 / 3) < 0.1:
            return "4:3"
        if abs(ratio - 3 / 4) < 0.1:
            return "3:4"
        return "1:1"
    except (ValueError, ZeroDivisionError):
        return "1:1"


def generate_image(prompt: str, style: str, output_path: str, size: str = "1024x1024"):
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["technical"])
    full_prompt = f"{style_prompt}\n\nSubject: {prompt}"
    aspect_ratio = _pick_aspect_ratio(size)

    print(f"Generating image (BizRouter → {MODEL}, ratio={aspect_ratio})...")
    print(f"  Style: {style}")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  Output: {output_path}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    max_retries = 3
    for attempt in range(max_retries):
        raw = _bizrouter_call(full_prompt, aspect_ratio=aspect_ratio)
        if raw is not None:
            try:
                from PIL import Image
                image = Image.open(io.BytesIO(raw))
                if size != "1024x1024":
                    w, h = map(int, size.split("x"))
                    image = image.resize((w, h), Image.LANCZOS)
                image.save(str(output))
                print(f"  Saved: {output_path} ({image.size[0]}x{image.size[1]})")
                return str(output)
            except ImportError:
                output.write_bytes(raw)
                print(f"  Saved (raw, install Pillow for resize): {output_path}")
                return str(output)
            except Exception as e:
                print(f"  Attempt {attempt + 1} post-process failed: {e}")
        else:
            print(f"  Attempt {attempt + 1}: empty image, retrying...")

        if attempt < max_retries - 1:
            import time
            time.sleep(5)

    print(f"  ERROR: Failed after {max_retries} attempts — writing placeholder")
    create_placeholder(output_path, prompt)
    return str(output_path)


def create_placeholder(output_path: str, prompt: str):
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1024, 1024), color=(30, 30, 40))
        draw = ImageDraw.Draw(img)
        draw.text(
            (50, 480),
            f"[Placeholder]\n{prompt[:80]}",
            fill=(150, 150, 150),
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        print(f"  Placeholder saved: {output_path}")
    except Exception:
        print(f"  Could not create placeholder at {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate images via BizRouter (Gemini 3 Pro Image)")
    parser.add_argument("--prompt", required=True, help="Image description")
    parser.add_argument(
        "--style",
        default="technical",
        choices=list(STYLE_PROMPTS.keys()),
        help="Style preset",
    )
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--size", default="1024x1024", help="Image size WxH")
    args = parser.parse_args()

    generate_image(args.prompt, args.style, args.output, args.size)


if __name__ == "__main__":
    main()
