#!/usr/bin/env python3
"""Gemini Image Generation Script for Book Illustrations.

Usage:
    python3 generate_image.py --prompt "description" --style "technical" --output "path.png"
    python3 generate_image.py --prompt "description" --style "technical" --output "path.png" --size "1536x1024"
"""

import argparse
import os
import sys
from pathlib import Path

# Load API key from .env.local
def load_api_key():
    env_paths = [
        Path(__file__).resolve().parents[3] / ".env.local",  # project root
        Path.home() / ".env.local",
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip("'\"")

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    print("ERROR: GEMINI_API_KEY not found.")
    print("Set it in .env.local: GEMINI_API_KEY=your_key_here")
    print("Or get one at: https://aistudio.google.com/")
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


def generate_image(prompt: str, style: str, output_path: str, size: str = "1024x1024"):
    api_key = load_api_key()

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("Installing google-genai...")
        os.system(f"{sys.executable} -m pip install -q google-genai Pillow")
        from google import genai
        from google.genai import types

    client = genai.Client(api_key=api_key)

    # Combine style prompt with user prompt
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["technical"])
    full_prompt = f"{style_prompt}\n\nSubject: {prompt}"

    print(f"Generating image...")
    print(f"  Style: {style}")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  Output: {output_path}")

    # Use Gemini's image generation
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            # Extract and save the image
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            image_saved = False
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    from PIL import Image
                    import io

                    image = Image.open(io.BytesIO(part.inline_data.data))

                    # Resize if needed
                    if size != "1024x1024":
                        w, h = map(int, size.split("x"))
                        image = image.resize((w, h), Image.LANCZOS)

                    image.save(str(output))
                    image_saved = True
                    print(f"  Saved: {output_path} ({image.size[0]}x{image.size[1]})")
                    break

            if image_saved:
                return str(output)
            else:
                print(f"  Attempt {attempt + 1}: No image in response, retrying...")

        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(5)
            else:
                print(f"  ERROR: Failed after {max_retries} attempts")
                # Create a placeholder
                create_placeholder(output_path, prompt)
                return str(output_path)

    create_placeholder(output_path, prompt)
    return str(output_path)


def create_placeholder(output_path: str, prompt: str):
    """Create a placeholder image when generation fails."""
    try:
        from PIL import Image, ImageDraw, ImageFont

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
    parser = argparse.ArgumentParser(description="Generate images using Gemini API")
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
