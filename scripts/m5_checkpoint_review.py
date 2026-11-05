"""Read-only Git/source inventory. Never stages files, commits, or reads private documents."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode().strip()


def inventory():
    entries = []
    for raw in (
        subprocess.check_output(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=ROOT
        )
        .decode()
        .split("\0")
    ):
        if not raw:
            continue
        state, name = raw[:2], raw[3:]
        path = ROOT / name
        private = (
            (
                name.startswith(("docs/academic/", "docs/production/", "var/"))
                and name != "docs/production/CLOUD_RUN_STAGING.md"
            )
            or (
                path.suffix.lower()
                in {".pdf", ".xlsx", ".jpg", ".png", ".sqlite3", ".db", ".pem", ".key"}
            )
            or (path.name.startswith(".env") and not path.name.endswith(".example"))
        )
        kind = (
            "excluded-private-or-raw-evidence"
            if private
            else (
                "source-test"
                if name.startswith(("apps/", "services/", "packages/", "scripts/"))
                else "reviewed-documentation"
                if name.startswith("docs/")
                else "configuration"
            )
        )
        if not private and name.endswith(".json") and name.startswith(("docs/api/", "packages/")):
            kind = "generated-versioned-contract-or-collection"
        entry = {
            "path": name,
            "git_state": state,
            "category": kind,
            "checkpoint_candidate": not private,
        }
        # Private artifacts are identified by metadata only, never opened by this review.
        if path.is_file() and not private:
            data = path.read_bytes()
            entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            patterns = [
                r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"\bAKIA[A-Z0-9]{16}\b",
                r'"private_key"\s*:\s*"[^"\s]{30,}',
            ]
            entry["secret_indicator"] = any(
                re.search(p, data.decode("utf-8", errors="replace")) for p in patterns
            )
        entries.append(entry)
    return {
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "index_changed": bool(git("diff", "--cached", "--name-only")),
        "entries": entries,
        "note": "Candidate inventory is neither staging approval nor full secret certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("New evidence file in existing directory required")
    value = inventory()
    args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "paths": len(value["entries"]),
                "head": value["head"],
                "secret_indicators": sum(
                    e.get("secret_indicator", False) for e in value["entries"]
                ),
            }
        )
    )
