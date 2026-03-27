#!/usr/bin/env python3
"""
Validate skill files (SKILL.md) in .claude/skills/.
Checks: frontmatter present, required fields exist, SSOT link present.
"""
import sys
import pathlib


REQUIRED_FIELDS = ["name", "description"]


def validate_skill(filepath: str) -> list[str]:
    errors = []
    path = pathlib.Path(filepath)
    if not path.exists():
        return [f"File not found: {filepath}"]
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        errors.append(f"{filepath}: missing frontmatter (no leading ---)")
        return errors
    try:
        end = text.index("---", 3)
    except ValueError:
        errors.append(f"{filepath}: frontmatter not closed")
        return errors
    frontmatter = text[3:end]
    for field in REQUIRED_FIELDS:
        if f"{field}:" not in frontmatter:
            errors.append(f"{filepath}: missing required frontmatter field '{field}'")
    if "**SSOT:**" not in text:
        errors.append(f"{filepath}: missing SSOT link (expected '**SSOT:**')")
    return errors


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0
    all_errors = []
    for f in files:
        all_errors.extend(validate_skill(f))
    if all_errors:
        for err in all_errors:
            print(f"❌ {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
