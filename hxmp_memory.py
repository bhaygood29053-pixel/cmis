import json
import subprocess
from pathlib import Path

ROBERTA_WALLET = "3g8TZbnj6mnTrzS6qm1nkHUNQntrVnPD2f9bjfNpMjeU"

PROJECT_ROOT = Path(__file__).resolve().parent

HXMP_TOOL = (
    PROJECT_ROOT
    / "integrations"
    / "hxmp"
    / "scripts"
    / "hxmp_tools.mjs"
)

HXMP_KEY = (
    Path.home()
    / ".hermes"
    / "x1"
    / "roberta"
    / "hxmp-encryption.key"
)


def load_roberta_memory():
    cmd = [
        "node",
        str(HXMP_TOOL),
        "read-soul",
        "--wallet",
        ROBERTA_WALLET,
        "--encryption-key",
        str(HXMP_KEY),
        "--show-content",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"HXMP read failed: {result.stderr.strip()}"
        )

    data = json.loads(result.stdout)

    if not data.get("verified"):
        raise RuntimeError(
            "HXMP memory was retrieved but verification failed."
        )

    return {
        "verified": True,
        "wallet": data.get("wallet"),
        "sequence": data.get("sequence"),
        "sha256": data.get("plaintext_sha256"),
        "content": data.get("content", ""),
        "summary": data.get("summary", ""),
    }


if __name__ == "__main__":
    memory = load_roberta_memory()

    print("HXMP MEMORY LOADED")
    print("------------------")
    print("Verified:", memory["verified"])
    print("Sequence:", memory["sequence"])
    print("SHA-256:", memory["sha256"])
    print()
    print("Summary:")
    print(memory["summary"])
