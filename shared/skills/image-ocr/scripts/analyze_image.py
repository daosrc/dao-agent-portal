#!/usr/bin/env python3
"""
Analyze an image using Gemini 3.1 Flash Lite Image via Qiniu AI API (OpenAI-compatible).

Usage:
    python3 analyze_image.py <image_path> [prompt]
    python3 analyze_image.py <prompt>                     # auto-discovers image in CWD
    python3 analyze_image.py                              # auto-discovers image, default prompt

Auto-discovers the newest .png/.jpg/.jpeg/.gif/.webp in the current directory when
no path is given. Reads the image file, base64-encodes it, and sends it to the
Qiniu AI API (api.qnaigc.com) using the google/gemini-3.1-flash-lite-image model.

Requires:
    - QINIU_AI_API_KEY environment variable set
"""

import base64
import json
import mimetypes
import os
import glob
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.qnaigc.com/v1"
MODEL = "google/gemini-3.1-flash-lite-image"
IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.bmp")


def get_api_key() -> str:
    key = os.environ.get("QINIU_AI_API_KEY")
    if not key:
        # fallback: read from opencode config
        config_path = os.path.expanduser("~/.config/opencode/opencode.json")
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            key = cfg.get("provider", {}).get("qiniu", {}).get("options", {}).get("apiKey", "")
        except Exception:
            pass
    if not key:
        print("QINIU_AI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


def clipboard_image() -> str | None:
    """Extract image from macOS clipboard if available. Returns temp path."""
    import subprocess
    import tempfile
    script = '''use framework "AppKit"
set pb to current application's NSPasteboard's generalPasteboard()
set imgData to pb's dataForType:(current application's NSPasteboardTypePNG)
if imgData is not missing value then
    imgData's writeToFile:"{path}" atomically:false
    return "png"
end if
set tiffData to pb's dataForType:(current application's NSPasteboardTypeTIFF)
if tiffData is not missing value then
    tiffData's writeToFile:"{path}" atomically:false
    return "tiff"
end if
return "none"'''
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        r = subprocess.run(
            ["osascript", "-e", script.format(path=tmp.name)],
            capture_output=True, text=True, timeout=5,
        )
        kind = r.stdout.strip()
        if kind == "none":
            os.unlink(tmp.name)
            return None
        return tmp.name
    except Exception:
        return None


CLIPBOARD_TMP: str | None = None


def find_image(cwd: str | None = None) -> str | None:
    global CLIPBOARD_TMP
    if cwd is None:
        cwd = os.getcwd()
    search_dirs = [cwd]
    home = os.path.expanduser("~")
    for d in [os.path.join(home, "Downloads"),
              os.path.join(home, "Desktop"),
              os.path.join(home, "Pictures")]:
        if os.path.isdir(d) and d != cwd:
            search_dirs.append(d)
    seen = set()
    best = None
    for d in search_dirs:
        for ext in IMAGE_EXTS:
            for f in glob.glob(os.path.join(d, ext)):
                p = os.path.realpath(f)
                if p not in seen and os.path.isfile(p):
                    seen.add(p)
                    mtime = os.path.getmtime(p)
                    if best is None or mtime > best[1]:
                        best = (p, mtime)
    # clipboard takes priority over disk (user just screenshotted)
    clip = clipboard_image()
    if clip:
        CLIPBOARD_TMP = clip
        return clip
    if best:
        return best[0]
    return None


def encode_image(path: str) -> tuple[str, str]:
    if not os.path.isfile(path):
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return mime_type, b64


def analyze_image(path: str, prompt: str, api_key: str) -> str:
    mime_type, b64 = encode_image(path)
    data_url = f"data:{mime_type};base64,{b64}"

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"Unexpected API response: {json.dumps(result, ensure_ascii=False, indent=2)}", file=sys.stderr)
        sys.exit(1)


def main():
    path = None
    prompt = None

    if len(sys.argv) >= 3:
        path, prompt = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        arg = sys.argv[1]
        if os.path.isfile(arg):
            path = arg
        else:
            path = find_image()
            if not path:
                print(f"no image found and argument is not a file: {arg}", file=sys.stderr)
                sys.exit(1)
            prompt = arg
    else:
        path = find_image()
        if not path:
            print("no image file found in current directory", file=sys.stderr)
            print(f"Usage: {os.path.basename(__file__)} <image_path> [prompt]", file=sys.stderr)
            sys.exit(1)

    if not prompt:
        prompt = "分析这张图片，详细描述你看到的所有内容，包括文字、布局、颜色、样式等"

    api_key = get_api_key()
    result = analyze_image(path, prompt, api_key)
    print(result)


if __name__ == "__main__":
    try:
        main()
    finally:
        if CLIPBOARD_TMP:
            try:
                os.unlink(CLIPBOARD_TMP)
            except Exception:
                pass
