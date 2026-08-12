"""
Liquidity Scout graphics organizer.

Run this from the project root:
    python organize_graphics.py

It creates:

graphics/
├── branding/      # avatar, logo, Liquidity Scout identity art
├── alerts/        # burn, liquidity, safety, buy/sell, warning graphics
├── tokens/        # token-specific permanent graphics
├── generated/     # dynamic cards created by Liquidity Scout
└── unsorted/      # anything that cannot be classified safely

The script never deletes files and never overwrites an existing file.
"""

from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parent
GRAPHICS = PROJECT_ROOT / "graphics"

FOLDERS = {
    "branding": GRAPHICS / "branding",
    "alerts": GRAPHICS / "alerts",
    "tokens": GRAPHICS / "tokens",
    "generated": GRAPHICS / "generated",
    "unsorted": GRAPHICS / "unsorted",
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"
}

BRANDING_WORDS = (
    "avatar", "logo", "liquidity_scout", "liquidity-scout",
    "scout_avatar", "profile", "branding",
)

ALERT_WORDS = (
    "burn", "burned", "alert", "warning", "danger", "safety",
    "liquidity", "volume", "buy", "sell", "pump", "dump",
    "whale", "risk",
)

GENERATED_WORDS = (
    "snapshot", "generated", "report", "asset_card", "asset-card",
    "_card", "-card",
)


def unique_destination(folder: Path, filename: str) -> Path:
    """Return a non-overwriting destination path."""
    target = folder / filename

    if not target.exists():
        return target

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2

    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def classify(path: Path) -> str:
    name = path.stem.lower()

    if any(word in name for word in GENERATED_WORDS):
        return "generated"

    if any(word in name for word in BRANDING_WORDS):
        return "branding"

    if any(word in name for word in ALERT_WORDS):
        return "alerts"

    # Token-specific images often use short ticker names or token names.
    # We avoid guessing and put unrecognized files into unsorted instead.
    return "unsorted"


def main():
    GRAPHICS.mkdir(parents=True, exist_ok=True)

    for folder in FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)

    moved = []
    skipped = []

    # Only organize image files sitting directly in graphics/.
    # Existing subfolders are left untouched.
    for path in sorted(GRAPHICS.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            skipped.append(path.name)
            continue

        category = classify(path)
        destination = unique_destination(FOLDERS[category], path.name)

        shutil.move(str(path), str(destination))
        moved.append((path.name, category, destination.name))

    # Create a simple guide inside graphics/.
    readme = GRAPHICS / "README.txt"
    readme.write_text(
        """LIQUIDITY SCOUT GRAPHICS

branding/
  Permanent Liquidity Scout avatar, logo, and identity artwork.

alerts/
  Burn, liquidity, safety, warning, buy/sell, volume, and risk graphics.

tokens/
  Permanent token-specific artwork you intentionally place here.

generated/
  Dynamic asset cards automatically created by Liquidity Scout.

unsorted/
  Images the organizer could not safely classify.
  Review these and move them into branding/, alerts/, or tokens/ when desired.

Nothing in this organizer is deleted automatically.
""",
        encoding="utf-8",
    )

    print()
    print("Liquidity Scout graphics organization complete.")
    print(f"Graphics folder: {GRAPHICS}")
    print()

    if moved:
        print("Moved:")
        for original, category, final_name in moved:
            print(f"  {original} -> graphics/{category}/{final_name}")
    else:
        print("No loose image files needed to be moved.")

    if skipped:
        print()
        print("Non-image files left untouched:")
        for name in skipped:
            print(f"  {name}")

    print()
    print("Folder structure:")
    for key in ("branding", "alerts", "tokens", "generated", "unsorted"):
        print(f"  graphics/{key}/")


if __name__ == "__main__":
    main()
