"""Legacy AGI burn-scan command routed through the generic X1 provider stack.

AGI identity is resolved from the current XDEX catalog at runtime instead of
hard-coding a remembered mint address. X1 RPC transport, signature traversal,
transaction parsing, and activity persistence are owned by the X1 providers.
"""

from x1_burn_scan import run_token_scan


WORKERS = 6
DB_FILE = "agi_burn_scan.db"


def main():
    return run_token_scan(
        "AGI",
        workers=WORKERS,
        max_signatures=None,
        db_file=DB_FILE,
    )


if __name__ == "__main__":
    main()
