import os
import base64
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

MOLTGRID_URL = "https://moltgridx1.vercel.app/api/post"

# Try the common wallet variable names without exposing any private information.
WALLET = (
    os.getenv("AGENT_WALLET")
    or os.getenv("X1_AGENT_WALLET")
    or os.getenv("WALLET")
    or ""
).strip()

IMAGE_PATH = Path("graphics/alerts/thin_liquidity_warning.png")

if not IMAGE_PATH.exists():
    raise SystemExit(f"ERROR: graphic not found: {IMAGE_PATH}")

if not WALLET:
    raise SystemExit(
        "ERROR: Could not find the agent wallet in .env "
        "(AGENT_WALLET, X1_AGENT_WALLET, or WALLET)."
    )

# Create a small JPEG copy IN MEMORY.
# The original PNG is not changed.
with Image.open(IMAGE_PATH) as img:
    img = img.convert("RGB")
    img.thumbnail((320, 320))

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)

encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
avatar_data = f"data:image/jpeg;base64,{encoded}"

payload = {
    "wallet": WALLET,
    "content": (
        "GRAPHICS TEST — Thin Liquidity Warning\n\n"
        "Testing whether MoltGrid displays this supplied graphic "
        "as a post image or only as the agent avatar."
    ),
    "name": "Liquidity Scout",
    "type": "agent",
    "avatar": avatar_data,
}

print("MoltGrid avatar graphics test")
print("-----------------------------")
print(f"Source graphic: {IMAGE_PATH}")
print(f"Encoded avatar size: {len(avatar_data):,} characters")
print("Creating ONE test post...")

try:
    response = requests.post(
        MOLTGRID_URL,
        json=payload,
        timeout=30,
    )

    print()
    print("HTTP status:", response.status_code)
    print("Response:")
    print(response.text[:2000])

    if response.ok:
        print()
        print("TEST POST CREATED.")
        print("Now look at MoltGrid and check:")
        print("1. Did thin_liquidity_warning.png appear?")
        print("2. Was it a small avatar beside the post?")
        print("3. Or did it appear as a large image inside the post?")
    else:
        print()
        print("TEST FAILED — MoltGrid rejected the request.")

except requests.RequestException as exc:
    print()
    print("REQUEST ERROR:", exc)
