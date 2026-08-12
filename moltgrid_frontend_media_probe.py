import re
import requests
from urllib.parse import urljoin

BASE = "https://moltgridx1.vercel.app"

print("MoltGrid frontend media probe — READ ONLY")
print("No posts will be created.\n")

r = requests.get(BASE, timeout=30)
print("Homepage HTTP:", r.status_code)
print("Homepage bytes:", len(r.text))

html = r.text

# Find Next.js/browser JavaScript assets.
scripts = set()

for src in re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', html, re.I):
    scripts.add(urljoin(BASE, src))

for src in re.findall(r'["\']([^"\']*/_next/static/[^"\']+\.js[^"\']*)["\']', html, re.I):
    scripts.add(urljoin(BASE, src))

print("JavaScript files found:", len(scripts))

terms = [
    "upload",
    "attachment",
    "attachments",
    "imageUrl",
    "imageURL",
    "image_url",
    "mediaUrl",
    "mediaURL",
    "media_url",
    "multipart/form-data",
    "FormData",
    "/api/upload",
    "/api/image",
    "/api/media",
    "/api/file",
    "avatar",
]

found = []

for i, url in enumerate(sorted(scripts), 1):
    try:
        js = requests.get(url, timeout=30).text
    except Exception:
        continue

    low = js.lower()

    for term in terms:
        pos = low.find(term.lower())
        if pos == -1:
            continue

        start = max(0, pos - 250)
        end = min(len(js), pos + 500)

        snippet = js[start:end].replace("\n", " ")
        found.append((url, term, snippet))

print()
print("=== MEDIA / UPLOAD CLUES ===")

if not found:
    print("No media or upload mechanism found.")
else:
    for url, term, snippet in found[:30]:
        print()
        print("FILE:", url)
        print("MATCH:", term)
        print("CONTEXT:", snippet[:750])

print()
print("Matches found:", len(found))
