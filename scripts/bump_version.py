#!/usr/bin/env python3
"""Simple semver patch-bumper for pyproject.toml

Usage:
  python scripts/bump_version.py        # prints new version
  python scripts/bump_version.py --git  # commits, tags, and pushes

This script finds the first `version = "X.Y.Z"` in pyproject.toml,
increments the patch (Z) by one, writes the file, and optionally creates
a git commit + tag and pushes.
"""
import re
import subprocess
import argparse
from pathlib import Path


PYPROJECT = Path("pyproject.toml")


def read_version(text: str) -> tuple[int,int,int]|None:
    m = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text, flags=re.M)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_patch(text: str) -> tuple[str,str]:
    v = read_version(text)
    if not v:
        raise SystemExit("Could not find version = \"X.Y.Z\" in pyproject.toml")
    major, minor, patch = v
    patch += 1
    new = f'{major}.{minor}.{patch}'
    new_text = re.sub(r'(^version\s*=\s*\")\d+\.\d+\.\d+(\"$)', fr"\1{new}\2", text, flags=re.M)
    return new_text, new


def git_commit_and_tag(new_version: str):
    msg = f"Bump version to {new_version}"
    subprocess.check_call(["git", "add", "pyproject.toml"])
    subprocess.check_call(["git", "commit", "-m", msg])
    tag = f"v{new_version}"
    subprocess.check_call(["git", "tag", tag])
    subprocess.check_call(["git", "push"])
    subprocess.check_call(["git", "push", "origin", tag])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--git", action="store_true", help="Commit, tag and push the bumped version")
    args = parser.parse_args()

    if not PYPROJECT.exists():
        raise SystemExit("pyproject.toml not found in current directory")

    text = PYPROJECT.read_text(encoding="utf-8")
    new_text, new_version = bump_patch(text)
    PYPROJECT.write_text(new_text, encoding="utf-8")
    print(new_version)

    if args.git:
        git_commit_and_tag(new_version)


if __name__ == "__main__":
    main()
