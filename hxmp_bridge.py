from pathlib import Path
import json

from journal import HXMP_QUEUE_PATH

def pending_events(limit=20):
    if not HXMP_QUEUE_PATH.exists():
        return []
    rows = []
    for line in HXMP_QUEUE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows[-limit:]

def print_review(limit=20):
    rows = pending_events(limit)
    if not rows:
        print("No HXMP-ready events queued.")
        return
    print("\nHXMP READY FOR REVIEW")
    print("-" * 72)
    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['time']} | {row['event_type']}")
        print(json.dumps(row["payload"], indent=2))
        print()
    print("Nothing above has been written on-chain.")
    print("HXMP requires preview + explicit approval before state-changing writes.")
