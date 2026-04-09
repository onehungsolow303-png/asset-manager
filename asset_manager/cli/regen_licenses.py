"""CLI: regenerate .shared/LICENSES.md from packs.yaml.

The LICENSES.md file is the human-readable license reference table for
every asset pack and AI service we use. Most of it is hand-written
prose (license definitions, distribution rules, AI service ToS notes)
that should NOT be auto-overwritten. The only auto-generated section
is the "Currently registered packs" table, which is derived from
packs.yaml.

This CLI:

  1. Reads .shared/packs.yaml
  2. Builds the new "Currently registered packs" table from the packs
     section, sorted by pack_id
  3. Reads .shared/LICENSES.md and locates the BEGIN/END markers around
     the auto-generated section
  4. Replaces the section between the markers with the rebuilt table
  5. Leaves all hand-written prose untouched

If the LICENSES.md doesn't exist or is missing the markers, the CLI
prints clear instructions on how to add them and exits with a non-zero
status (no destructive overwrites).

Usage:
    python -m asset_manager.cli.regen_licenses
    python -m asset_manager.cli.regen_licenses --check  # exit 1 if outdated
    python -m asset_manager.cli.regen_licenses --packs-yaml path --licenses-md path

The --check mode is intended for CI / pre-commit hooks: it regenerates
the table in memory, compares to the on-disk LICENSES.md, and exits
with status 1 if they differ. This catches stale LICENSES.md before
it lands in a commit.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

DEFAULT_PACKS_YAML = Path("C:/Dev/.shared/packs.yaml")
DEFAULT_LICENSES_MD = Path("C:/Dev/.shared/LICENSES.md")

# Markers that delimit the auto-generated section. They MUST be present
# in LICENSES.md as HTML comments so the CLI knows what to replace.
BEGIN_MARKER = "<!-- BEGIN AUTO-GENERATED PACKS TABLE -->"
END_MARKER = "<!-- END AUTO-GENERATED PACKS TABLE -->"

_TABLE_HEADER = (
    "| Pack | Author | License | Redistribution | Status |\n"
    "|---|---|---|---|---|\n"
)


def build_packs_table(packs_yaml_path: Path) -> str:
    """Read packs.yaml and return the markdown table for the auto section."""
    if not packs_yaml_path.exists():
        raise FileNotFoundError(f"packs.yaml not found: {packs_yaml_path}")

    data = yaml.safe_load(packs_yaml_path.read_text(encoding="utf-8")) or {}
    packs = data.get("packs") or []

    if not packs:
        return _TABLE_HEADER + "| (no packs registered) | | | | |\n"

    rows = []
    for p in sorted(packs, key=lambda x: x.get("pack_id", "")):
        name = _md_escape(p.get("pack_name", "?"))
        author = _md_escape(p.get("author", "?"))
        license_code = _md_escape(p.get("license_code", "?"))
        redistribution = "**NO**" if not p.get("redistribution", True) else "YES"
        status = _md_escape(p.get("status", "unknown"))
        rows.append(f"| {name} | {author} | {license_code} | {redistribution} | {status} |")

    return _TABLE_HEADER + "\n".join(rows) + "\n"


def regenerate_licenses_md(
    packs_yaml_path: Path,
    licenses_md_path: Path,
    check_only: bool = False,
) -> tuple[bool, str]:
    """Rebuild LICENSES.md's auto-generated section from packs.yaml.

    Returns (changed, message). When check_only=True, the file is not
    written; the function only reports whether the on-disk version
    differs from what the regenerator would produce.
    """
    new_table = build_packs_table(packs_yaml_path)

    if not licenses_md_path.exists():
        return False, (
            f"LICENSES.md not found: {licenses_md_path}\n"
            "Create it manually first, including the markers:\n"
            f"  {BEGIN_MARKER}\n"
            "  | Pack | Author | License | ... |\n"
            f"  {END_MARKER}"
        )

    existing = licenses_md_path.read_text(encoding="utf-8")

    if BEGIN_MARKER not in existing or END_MARKER not in existing:
        return False, (
            f"LICENSES.md missing required markers. Add these around the "
            f"packs table:\n  {BEGIN_MARKER}\n  ...table...\n  {END_MARKER}\n"
            "Then re-run this CLI."
        )

    begin_idx = existing.index(BEGIN_MARKER)
    end_idx = existing.index(END_MARKER)
    if end_idx < begin_idx:
        return False, "LICENSES.md markers are in wrong order"

    # Splice: keep everything up to and including BEGIN, replace middle,
    # keep everything from END onward
    before = existing[: begin_idx + len(BEGIN_MARKER)]
    after = existing[end_idx:]
    rebuilt = f"{before}\n{new_table}\n{after}"

    if rebuilt == existing:
        return False, "LICENSES.md is already up to date"

    if check_only:
        return True, (
            "LICENSES.md is OUT OF DATE — run "
            "`python -m asset_manager.cli.regen_licenses` to fix"
        )

    licenses_md_path.write_text(rebuilt, encoding="utf-8")
    return True, f"updated {licenses_md_path}"


def _md_escape(text: str) -> str:
    """Escape pipe characters that would break markdown table rows."""
    return str(text).replace("|", "\\|")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the auto-generated section of LICENSES.md"
    )
    parser.add_argument(
        "--packs-yaml",
        default=str(DEFAULT_PACKS_YAML),
        help="Path to packs.yaml",
    )
    parser.add_argument(
        "--licenses-md",
        default=str(DEFAULT_LICENSES_MD),
        help="Path to LICENSES.md",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Don't write — exit 1 if LICENSES.md is out of date",
    )
    args = parser.parse_args(argv)

    try:
        changed, message = regenerate_licenses_md(
            Path(args.packs_yaml),
            Path(args.licenses_md),
            check_only=args.check,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(message)
    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
