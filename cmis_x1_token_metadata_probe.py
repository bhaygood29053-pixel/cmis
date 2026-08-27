"""Sanitized read-only X1 Token Metadata live evidence probe.

The probe performs only X1 JSON-RPC reads. It verifies the configured Metaplex
Token Metadata program account and, when a mint is supplied, requests the exact
mint-filtered metadata account through the bounded provider contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from liquidity_scout.providers.x1.token_metadata import (
    TOKEN_METADATA_PROGRAM_ID,
    get_token_metadata_for_mint,
    get_token_metadata_program_status,
)


DEFAULT_PROBE_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only X1 Metaplex Token Metadata evidence probe"
    )
    parser.add_argument(
        "--mint",
        default=DEFAULT_PROBE_MINT,
        help="Exact X1 mint to probe after program verification",
    )
    parser.add_argument(
        "--output",
        default="x1-token-metadata-evidence.json",
        help="Sanitized JSON evidence output path",
    )
    args = parser.parse_args()

    program = get_token_metadata_program_status()
    evidence = {
        "probe": "x1_token_metadata_evidence",
        "program_id": TOKEN_METADATA_PROGRAM_ID,
        "read_only": True,
        "execution_authorized": False,
        "program": program,
        "mint": args.mint,
        "metadata": None,
    }

    if program.get("program_executable_verified") is not True:
        evidence["result"] = "program_unverified"
        Path(args.output).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 1

    metadata_evidence = get_token_metadata_for_mint(args.mint)
    evidence["metadata"] = metadata_evidence.get("metadata")
    evidence["result"] = (
        "verified"
        if metadata_evidence.get("identity_verified") is True
        else "metadata_unverified"
    )

    Path(args.output).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["result"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
