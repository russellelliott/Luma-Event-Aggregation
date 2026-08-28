"""Remove old filesystem backups from the Luma data backup directory.

By default this script prints the backup directories it would remove. Pass
--execute to delete them.
"""

import argparse
import shutil
from pathlib import Path


def get_default_backup_path() -> Path:
    return Path.home() / ".luma-event-aggregation" / "data" / "backups"


def remove_entry(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


def purge_backup_files(backup_path: Path, execute: bool = False) -> list[Path]:
    if not backup_path.is_dir():
        raise FileNotFoundError(f"Backup directory not found at: {backup_path}")

    entries_to_delete = sorted(backup_path.iterdir())

    print(f"Backup directory: {backup_path}")
    if not entries_to_delete:
        print("Backup directory is already empty.")
        return []

    action = "Deleting" if execute else "Would delete"
    print(f"{action} all {len(entries_to_delete)} entr{'y' if len(entries_to_delete) == 1 else 'ies'}:")
    for path in entries_to_delete:
        if execute:
            remove_entry(path)
        print(f"  DELETE {path.name}")

    if not execute:
        print("Dry run only. Re-run with --execute to empty this directory.")
    return entries_to_delete


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Empty the Luma filesystem backup directory."
    )
    mode_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "--backup-path",
        type=Path,
        default=get_default_backup_path(),
        help="Path to the filesystem backup directory",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete old backups; otherwise perform a dry run",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show backups that would be deleted without deleting them (default)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        purge_backup_files(args.backup_path, args.execute)
    except Exception as exc:
        print(f"Purge failed: {exc}")
        raise SystemExit(1)