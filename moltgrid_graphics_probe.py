"""
READ-ONLY MoltGrid graphics/media probe.

This script:
1. Reads recent /api/post objects and reports any media-looking fields.
2. Downloads MoltGrid's public page JavaScript and searches for image/upload
   endpoint names and field names.

It DOES NOT post anything and DOES NOT use wallet secrets.
"""

import json
import re
from urllib.parse import urljoin

import requests

BASE = "https://moltgridx1.vercel.app/"
POSTS = urljoin(BASE, "/api/post")

MEDIA_WORDS = (
    "image", "img", "media", "photo", "picture",
    "attachment", "upload", "blob", "file",
)


def mediaish_key(key):
    k = str(key).lower()
    return any(word in k for word in MEDIA_WORDS)


def print_post_media_schema():
    print("=== 1. RECENT POST MEDIA FIELDS ===")
    r = requests.get(POSTS, timeout=20)
    r.raise_for_status()
    payload = r.json()

    posts = payload.get("posts") if isinstance(payload, dict) else payload
    posts = posts or []

    print(f"Posts read: {len(posts)}")
    found = 0

    for post in posts:
        if not isinstance(post, dict):
            continue

        candidates = {
            k: v for k, v in post.items()
            if mediaish_key(k) and v not in (None, "", [], {})
        }

        # Also catch URL/data-image values whose keys are not obvious.
        for k, v in post.items():
            if isinstance(v, str):
                low = v.lower()
                if (
                    low.startswith("data:image/")
                    or re.search(r"\.(png|jpe?g|webp|gif)(?:\?|$)", low)
                ):
                    candidates.setdefault(k, v)

        if candidates:
            found += 1
            print()
            print(f"Post ID: {post.get('id')}")
            print(f"Name: {post.get('name')}")
            print("Media-looking fields:")
            for k, v in candidates.items():
                preview = v
                if isinstance(v, str) and len(v) > 240:
                    preview = v[:240] + "..."
                print(f"  {k}: {preview!r}")

    if not found:
        print("No media-bearing post fields found in the current API window.")

    # Print keys once so we know the complete post object shape.
    if posts and isinstance(posts[0], dict):
        print()
        print("All keys on a recent post:")
        print(sorted(posts[0].keys()))


def get_script_urls():
    r = requests.get(BASE, timeout=20)
    r.raise_for_status()
    html = r.text

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.I,
    )
    return [urljoin(BASE, src) for src in scripts]


def print_js_media_hints():
    print()
    print("=== 2. PUBLIC JAVASCRIPT MEDIA/UPLOAD HINTS ===")
    urls = get_script_urls()
    print(f"JavaScript files found: {len(urls)}")

    hits = []
    patterns = [
        r'["\'](/api/[^"\']*(?:upload|image|media|attachment|blob|file)[^"\']*)["\']',
        r'\b(imageUrl|imageURL|image_url|image|mediaUrl|mediaURL|media_url|media|attachmentUrl|attachments|photoUrl|fileUrl)\b',
        r'\b(FormData|multipart/form-data|put\\(|upload\\()\b',
    ]

    for url in urls:
        try:
            text = requests.get(url, timeout=20).text
        except Exception:
            continue

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                a = max(0, match.start() - 180)
                b = min(len(text), match.end() + 260)
                snippet = re.sub(r"\s+", " ", text[a:b])
                hits.append((url, snippet))

    # Deduplicate snippets.
    seen = set()
    unique = []
    for url, snippet in hits:
        key = snippet[:220]
        if key not in seen:
            seen.add(key)
            unique.append((url, snippet))

    if not unique:
        print("No obvious image/upload hints found in public JS.")
        return

    print(f"Possible media/upload clues: {len(unique)}")
    for i, (url, snippet) in enumerate(unique[:30], 1):
        print()
        print(f"[{i}] {url}")
        print(snippet[:800])


def main():
    print("MoltGrid Graphics Probe — READ ONLY")
    print("No posts will be created.")
    print()
    print_post_media_schema()
    print_js_media_hints()


if __name__ == "__main__":
    main()
