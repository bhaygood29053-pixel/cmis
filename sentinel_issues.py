#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ISSUE_FILE = Path("development/issues.json")
ARCHIVE_FILE = Path("development/issues_archive.json")

VALID_STATUSES = (
    "OPEN",
    "FIXING",
    "TESTED",
    "VERIFIED",
)

VALID_SEVERITIES = (
    "low",
    "normal",
    "high",
    "urgent",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def load_data():
    if not ISSUE_FILE.exists():
        return {"version": 1, "issues": []}

    with ISSUE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    ISSUE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with ISSUE_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def next_issue_id(issues):
    numbers = []

    for issue in issues:
        issue_id = str(issue.get("id", ""))

        if issue_id.startswith("SENT-"):
            try:
                numbers.append(int(issue_id.split("-", 1)[1]))
            except ValueError:
                pass

    number = max(numbers, default=0) + 1
    return f"SENT-{number:04d}"


def command_add(args):
    data = load_data()

    issue = {
        "id": next_issue_id(data["issues"]),
        "area": args.area,
        "issue": args.issue,
        "severity": args.severity,
        "status": "OPEN",
        "created_at": now(),
        "updated_at": now(),
    }

    data["issues"].append(issue)
    save_data(data)

    print(f"Added {issue['id']}: {issue['issue']}")



def issue_age(created_at):
    """
    Return a human-readable age for an issue.
    Example: 2h 17m, 3d 6h, 45m.
    """
    try:
        created = datetime.fromisoformat(created_at)
        current = datetime.now(timezone.utc)

        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        seconds = max(0, int((current - created).total_seconds()))
    except (TypeError, ValueError):
        return "Unknown"

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)

    if days:
        return f"{days}d {hours}h"

    if hours:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"


def priority_display(priority):
    """
    Color-code priorities for terminal display.
    URGENT also uses ANSI blink where supported.
    """
    reset = "\033[0m"
    green = "\033[92m"
    cyan = "\033[96m"
    yellow = "\033[93m"
    red_blink = "\033[5;91m"

    styles = {
        "low": green,
        "normal": cyan,
        "high": yellow,
        "urgent": red_blink,
    }

    style = styles.get(priority, "")
    label = str(priority).upper()

    return f"{style}{label}{reset}" if style else label


def command_list(args):
    data = load_data()
    issues = data["issues"]

    if args.status:
        issues = [
            issue
            for issue in issues
            if issue.get("status") == args.status
        ]

    all_issues = data["issues"]

    counts = {
        status: sum(
            1 for issue in all_issues
            if issue.get("status") == status
        )
        for status in VALID_STATUSES
    }

    urgent_open = sum(
        1 for issue in all_issues
        if issue.get("severity") == "urgent"
        and issue.get("status") != "VERIFIED"
    )

    print("=" * 48)
    print("          X1 SENTINEL ISSUE TRACKER")
    print("=" * 48)
    print()
    print(f"Open:      {counts['OPEN']}")
    print(f"Fixing:    {counts['FIXING']}")
    print(f"Tested:    {counts['TESTED']}")
    print(f"Verified:  {counts['VERIFIED']}")
    print(f"Urgent:    {urgent_open}")
    print()

    if not issues:
        print("No matching development issues.")
        return

    for status in VALID_STATUSES:
        grouped = [
            issue
            for issue in issues
            if issue.get("status") == status
        ]

        if not grouped:
            continue

        print("-" * 48)
        print(status)
        print("-" * 48)

        for issue in grouped:
            print()
            print(f"{issue['id']}  |  {issue['area'].title()}")
            print(f"Priority:  {priority_display(issue['severity'])}")
            print(f"Issue age: {issue_age(issue.get('created_at'))}")
            print()
            print("Problem:")
            print(f"  {issue['issue']}")
            print()



def command_status(args):
    data = load_data()

    for issue in data["issues"]:
        if issue.get("id") == args.id:
            old_status = issue["status"]
            issue["status"] = args.status
            issue["updated_at"] = now()

            save_data(data)

            print(
                f"{args.id}: "
                f"{old_status} -> {args.status}"
            )
            return

    raise SystemExit(f"Issue not found: {args.id}")



def command_archive(args):
    data = load_data()
    issues = data["issues"]

    if ARCHIVE_FILE.exists():
        with ARCHIVE_FILE.open("r", encoding="utf-8") as f:
            archive_data = json.load(f)
    else:
        archive_data = {
            "version": 1,
            "issues": [],
        }

    if args.verified:
        to_archive = [
            issue
            for issue in issues
            if issue.get("status") == "VERIFIED"
        ]
    else:
        to_archive = [
            issue
            for issue in issues
            if issue.get("id") == args.id
        ]

        if not to_archive:
            raise SystemExit(f"Issue not found: {args.id}")

        if to_archive[0].get("status") != "VERIFIED":
            raise SystemExit(
                f"{args.id} must be VERIFIED before it can be archived."
            )

    if not to_archive:
        print("No VERIFIED issues are ready to archive.")
        return

    archive_ids = {
        issue["id"]
        for issue in to_archive
    }

    archived_at = now()

    for issue in to_archive:
        archived_issue = dict(issue)
        archived_issue["archived_at"] = archived_at
        archive_data["issues"].append(archived_issue)

    data["issues"] = [
        issue
        for issue in issues
        if issue.get("id") not in archive_ids
    ]

    save_data(data)

    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with ARCHIVE_FILE.open("w", encoding="utf-8") as f:
        json.dump(archive_data, f, indent=2)
        f.write("\n")

    print(f"Archived {len(to_archive)} verified issue(s).")


def command_summary(args):
    data = load_data()
    issues = data["issues"]

    counts = {
        status: 0
        for status in VALID_STATUSES
    }

    urgent_open = 0

    for issue in issues:
        status = issue.get("status", "OPEN")

        if status in counts:
            counts[status] += 1

        if (
            issue.get("severity") == "urgent"
            and status != "VERIFIED"
        ):
            urgent_open += 1

    print("X1 SENTINEL ISSUE SUMMARY")
    print("=" * 40)
    print(f"Open:      {counts['OPEN']}")
    print(f"Fixing:    {counts['FIXING']}")
    print(f"Tested:    {counts['TESTED']}")
    print(f"Verified:  {counts['VERIFIED']}")
    print(f"Urgent:    {urgent_open}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage X1 Sentinel development issues."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Add a new issue.",
    )
    add_parser.add_argument(
        "--area",
        required=True,
        help="Area such as analysis, performance, branding, network.",
    )
    add_parser.add_argument(
        "--issue",
        required=True,
        help="Short description of the problem.",
    )
    add_parser.add_argument(
        "--severity",
        choices=VALID_SEVERITIES,
        default="normal",
    )
    add_parser.set_defaults(func=command_add)

    list_parser = subparsers.add_parser(
        "list",
        help="List development issues.",
    )
    list_parser.add_argument(
        "--status",
        choices=VALID_STATUSES,
    )
    list_parser.set_defaults(func=command_list)

    status_parser = subparsers.add_parser(
        "status",
        help="Change an issue status.",
    )
    status_parser.add_argument("id")
    status_parser.add_argument(
        "status",
        choices=VALID_STATUSES,
    )
    status_parser.set_defaults(func=command_status)

    archive_parser = subparsers.add_parser(
        "archive",
        help="Archive verified issues.",
    )

    archive_group = archive_parser.add_mutually_exclusive_group(
        required=True,
    )

    archive_group.add_argument(
        "id",
        nargs="?",
        help="Verified issue ID to archive.",
    )

    archive_group.add_argument(
        "--verified",
        action="store_true",
        help="Archive all VERIFIED issues.",
    )

    archive_parser.set_defaults(func=command_archive)

    summary_parser = subparsers.add_parser(
        "summary",
        help="Show issue counts.",
    )
    summary_parser.set_defaults(func=command_summary)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
