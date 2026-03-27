#!/usr/bin/env python3
"""
Validate rule files in .claude/rules/.
Checks: frontmatter present, required fields exist.
"""
import sys
import pathlib


REQUIRED_FIELDS = ["description"]


def validate_rule(filepath: str) -> list[str]:
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
    return errors


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0
    all_errors = []
    for f in files:
        all_errors.extend(validate_rule(f))
    if all_errors:
        for err in all_errors:
            print(f"❌ {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
