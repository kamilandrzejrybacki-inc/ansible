#!/usr/bin/env python3
"""Validate an AXI SKILL.md: discoverable frontmatter + all 13 required principles.

Usage:  validate_axi_skill.py <path/to/SKILL.md>
Exit:   0 = conformant, 1 = missing sections / invalid frontmatter, 2 = usage error.

The AXI standard (kunchenguid/axi) plus the homelab "reject unknown flags" addendum
define 13 required principles. This fixture proves a committed skill is discoverable
(valid frontmatter with name + trigger description) and covers every principle, so the
skill cannot silently rot in either the Claude Code (ansible) or Hermes (helm) tree.
"""
import re
import sys

# Each principle -> list of anchor substrings; ALL must be present (case-insensitive).
REQUIRED = {
    "1 token-efficient output": ["## 1. Token-efficient output", "TOON"],
    "2 minimal default schemas": ["## 2. Minimal default schemas"],
    "3 truncation + total-size + full escape": ["## 3. Content truncation", "truncated", "--full"],
    "4 pre-computed aggregates/counts": ["## 4. Pre-computed aggregates", "total count"],
    "5 definitive empty states": ["## 5. Definitive empty states"],
    "6 structured errors + exit codes": ["## 6. Structured errors", "exit code"],
    "7 idempotent mutations": ["### Idempotent mutations"],
    "8 no interactive prompts": ["### No interactive prompts"],
    "9 content-first default": ["## 8. Content first"],
    "10 contextual next-step hints": ["## 9. Contextual disclosure"],
    "11 concise per-subcommand help": ["## 10. Consistent way to get help", "--help"],
    "12 stdout/stderr separation": ["### Output channels", "stderr"],
    "13 reject unknown flags": ["## 11. Reject unknown flags"],
}


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    desc = re.search(r"^description:\s*", fm, re.MULTILINE)
    if not name or not desc:
        return None
    return name.group(1)


def main(argv):
    if len(argv) != 2:
        sys.stdout.write("error: exactly one argument (path to SKILL.md) required\n")
        sys.stdout.write("help: validate_axi_skill.py <path/to/SKILL.md>\n")
        return 2
    path = argv[1]
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as exc:
        sys.stdout.write("error: cannot read %s (%s)\n" % (path, exc.__class__.__name__))
        return 1

    problems = []
    name = parse_frontmatter(text)
    if name is None:
        problems.append("invalid or missing frontmatter (need name + description)")
    elif name != "axi":
        problems.append("frontmatter name is %r, expected 'axi'" % name)

    low = text.lower()
    missing = []
    for principle, anchors in REQUIRED.items():
        for anchor in anchors:
            if anchor.lower() not in low:
                missing.append("%s (anchor: %r)" % (principle, anchor))
                break

    if missing:
        problems.append("missing %d/13 principle anchors:\n    - %s"
                        % (len(missing), "\n    - ".join(missing)))

    if problems:
        sys.stdout.write("axi-skill: FAIL (%s)\n" % path)
        for p in problems:
            sys.stdout.write("  - %s\n" % p)
        return 1

    sys.stdout.write("axi-skill: OK — %s discoverable, all 13/13 principles present\n" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
