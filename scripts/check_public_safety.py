"""Fail if anything that should stay private is tracked by git.

Checks
------
1. No CSV/Excel/database files are tracked (data must stay local).
2. No ``*.local.*`` configuration files are tracked.
3. If ``config/banned_terms.local.txt`` exists (git-ignored; one term per
   line), none of those terms may appear in any tracked text file. Keep your
   own list of provider/company names there - never in the repository.

    python scripts/check_public_safety.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED_FILE = ROOT / "config" / "banned_terms.local.txt"
PRIVATE_SUFFIXES = {".csv", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3"}
TEXT_SUFFIXES = {".py", ".md", ".sql", ".json", ".yml", ".yaml", ".txt", ".ipynb",
                 ".ini", ".toml", ""}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("This check must run inside the git repository.")
        sys.exit(2)
    return [ROOT / line for line in result.stdout.splitlines()]


def main() -> int:
    problems: list[str] = []
    files = [f for f in tracked_files() if f.exists()]

    for file in files:
        relative = file.relative_to(ROOT)
        if file.suffix.lower() in PRIVATE_SUFFIXES:
            problems.append(f"Tracked data file: {relative}")
        if ".local." in file.name:
            problems.append(f"Tracked local config: {relative}")

    if BANNED_FILE.exists():
        terms = [
            line.strip().lower()
            for line in BANNED_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        for file in files:
            if file.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = file.read_text(encoding="utf-8", errors="ignore").lower()
            for term in terms:
                if term in text:
                    # Never print the term itself.
                    problems.append(
                        f"Banned term #{terms.index(term) + 1} found in "
                        f"{file.relative_to(ROOT)}"
                    )
    else:
        print("note: config/banned_terms.local.txt not found; "
              "term check skipped.")

    if problems:
        print("PUBLIC-SAFETY CHECK FAILED")
        for problem in sorted(set(problems)):
            print(f"  - {problem}")
        return 1

    print(f"Public-safety check passed ({len(files)} tracked files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
