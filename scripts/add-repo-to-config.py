#!/usr/bin/env python3
"""
Safely add the repo's shared/skills/ path to an existing opencode.json.

Usage:
  python3 scripts/add-repo-to-config.py <repo_dir>

If the target opencode.json already references the repo path, it is skipped.
The original file is preserved (no backup needed — the old config stays in place).
"""
import json
import os
import sys


def main():
    if len(sys.argv) < 2:
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    else:
        repo_dir = sys.argv[1]

    config_path = os.path.expanduser("~/.config/opencode/opencode.json")
    repo_skills = os.path.join(repo_dir, "shared", "skills")

    if not os.path.isfile(config_path):
        print("  ~/.config/opencode/opencode.json not found. Nothing to modify.")
        return 0

    # Make repo path absolute for portability
    repo_skills_abs = os.path.abspath(repo_skills)

    with open(config_path, "r") as f:
        config = json.load(f)

    paths = config.setdefault("skills", {}).setdefault("paths", [])

    if repo_skills_abs in paths:
        print(f"  ✅ Repo skills path already in config: {repo_skills_abs}")
        return 0

    # Check if any path under this repo is already listed
    for p in paths:
        try:
            if os.path.samefile(p, repo_skills_abs):
                print(f"  ✅ Repo skills path already in config (via {p})")
                return 0
        except (OSError, ValueError):
            pass

    paths.append(repo_skills_abs)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"  ✅ Added to ~/.config/opencode/opencode.json:")
    print(f"     skills.paths → {repo_skills_abs}")
    print(f"     (original config preserved, no files moved or deleted)")

    return 1


if __name__ == "__main__":
    sys.exit(main())
