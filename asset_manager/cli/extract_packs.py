"""CLI: extract every zip archive in a directory.

Walks a directory for *.zip files and extracts each to a sibling
subfolder named after the zip stem. Used for unpacking large
asset collections like Forgotten Adventures packs that ship as
multi-gigabyte zip archives.

Why this exists separately from bulk_import:
    Extraction is a slow, disk-heavy operation that benefits from
    being a discrete step the user can re-run, inspect, and clean
    up independently. Splitting "extract zips" from "register the
    extracted content in the catalog" lets the user:

      1. Extract once, import many times (e.g., re-import after
         editing the kind_overrides config)
      2. Browse the extracted content in File Explorer before
         deciding which sub-packs to register
      3. Delete the source zips after extraction if disk is tight,
         keeping only the extracted content as the source of truth

Idempotency:
    If a target subfolder already exists AND contains files, the
    extraction is SKIPPED for that zip. This avoids re-extracting
    multi-gigabyte archives on every run. Use --force to override
    and always extract.

Error handling:
    Bad zips (truncated, password-protected, encoding errors) are
    logged and skipped — the CLI continues with the next zip rather
    than aborting the whole batch. Final summary lists how many
    zips succeeded vs failed.

Usage:
    python -m asset_manager.cli.extract_packs <directory>
    python -m asset_manager.cli.extract_packs <directory> --force
    python -m asset_manager.cli.extract_packs <directory> --quiet
"""
from __future__ import annotations

import argparse
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractResult:
    zip_path: Path
    target_dir: Path
    success: bool
    skipped: bool = False
    file_count: int = 0
    bytes_extracted: int = 0
    error: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class BatchResult:
    successes: int = 0
    skipped: int = 0
    failures: int = 0
    total_bytes: int = 0
    per_zip: list[ExtractResult] = field(default_factory=list)


def extract_zip(
    zip_path: Path,
    target_dir: Path,
    force: bool = False,
) -> ExtractResult:
    """Extract a single zip file to target_dir.

    target_dir is created if missing. If it already contains files
    and force=False, the extraction is skipped (idempotent).
    """
    result = ExtractResult(zip_path=zip_path, target_dir=target_dir, success=False)
    started = time.monotonic()

    if not zip_path.exists():
        result.error = f"zip not found: {zip_path}"
        return result

    if not zipfile.is_zipfile(zip_path):
        result.error = f"not a valid zip: {zip_path}"
        return result

    # Idempotency check
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        result.success = True
        result.skipped = True
        result.elapsed_seconds = time.monotonic() - started
        return result

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.infolist()
            for info in members:
                if info.is_dir():
                    continue
                # Defense against zip-slip path traversal: refuse to
                # extract any member whose normalized path escapes
                # target_dir.
                resolved = (target_dir / info.filename).resolve()
                try:
                    resolved.relative_to(target_dir.resolve())
                except ValueError:
                    continue  # outside target — skip
                zf.extract(info, target_dir)
                result.file_count += 1
                result.bytes_extracted += info.file_size
        result.success = True
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        result.error = f"extraction failed: {e}"

    result.elapsed_seconds = time.monotonic() - started
    return result


def extract_all_in_dir(
    directory: Path,
    force: bool = False,
    verbose: bool = True,
) -> BatchResult:
    """Find every *.zip in directory (non-recursive) and extract each.

    Each zip extracts to a sibling subfolder named after the zip stem
    (e.g., `FA_Objects_A_v3.52.zip` → `FA_Objects_A_v3.52/`).
    """
    batch = BatchResult()

    if not directory.exists() or not directory.is_dir():
        if verbose:
            print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return batch

    zips = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".zip")

    if verbose:
        total_size_gb = sum(z.stat().st_size for z in zips) / (1024 ** 3)
        print(f"Found {len(zips)} zip files, {total_size_gb:.1f} GB total")
        print()

    for i, zip_path in enumerate(zips, start=1):
        target = directory / zip_path.stem
        if verbose:
            print(f"[{i}/{len(zips)}] {zip_path.name} -> {target.name}/", end=" ", flush=True)

        result = extract_zip(zip_path, target, force=force)
        batch.per_zip.append(result)

        if result.success and not result.skipped:
            batch.successes += 1
            batch.total_bytes += result.bytes_extracted
            if verbose:
                size_mb = result.bytes_extracted / (1024 ** 2)
                print(
                    f"OK ({result.file_count} files, {size_mb:.1f} MB, "
                    f"{result.elapsed_seconds:.1f}s)"
                )
        elif result.skipped:
            batch.skipped += 1
            if verbose:
                print("SKIP (target dir already populated)")
        else:
            batch.failures += 1
            if verbose:
                print(f"FAIL: {result.error}")

    if verbose:
        print()
        gb = batch.total_bytes / (1024 ** 3)
        print(
            f"DONE: {batch.successes} extracted, {batch.skipped} skipped, "
            f"{batch.failures} failed. {gb:.2f} GB total."
        )

    return batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract every .zip archive in a directory to sibling subfolders"
    )
    parser.add_argument("directory", help="Directory containing zip files")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if the target subfolder already has content",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-zip progress lines",
    )
    args = parser.parse_args(argv)

    batch = extract_all_in_dir(
        Path(args.directory),
        force=args.force,
        verbose=not args.quiet,
    )

    return 0 if batch.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
