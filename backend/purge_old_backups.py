"""Remove old timestamped LanceDB backup tables.

By default this script prints the tables it would remove. Pass --execute to
drop them from the database.
"""

import argparse
import re
from pathlib import Path

import lancedb

from listTables import get_all_tables


KEEP_TABLES = {"events", "event_clusters", "city_summary"}
BACKUP_PATTERN = re.compile(r"_backup_(?:before_clustering_)?(\d+)$")
DEFAULT_KEEP_COUNT = 5


def get_default_db_path() -> Path:
    return Path.home() / ".luma-event-aggregation" / "data" / "events.db"


def find_backups(table_names: list[str]) -> list[tuple[int, str]]:
    backups = []
    for table_name in table_names:
        match = BACKUP_PATTERN.search(table_name)
        if match:
            backups.append((int(match.group(1)), table_name))
    return sorted(backups, reverse=True)


def purge_old_backups(
    db_path: Path,
    keep_count: int = DEFAULT_KEEP_COUNT,
    execute: bool = False,
) -> list[str]:
    if keep_count < 0:
        raise ValueError("keep_count must be zero or greater")
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at: {db_path}")

    db = lancedb.connect(str(db_path))
    backups = find_backups(get_all_tables(db))
    tables_to_keep = {name for _, name in backups[:keep_count]}
    tables_to_delete = [
        name for _, name in backups[keep_count:] if name not in KEEP_TABLES
    ]

    print(f"Database: {db_path}")
    print(f"Protected tables: {', '.join(sorted(KEEP_TABLES))}")
    print(f"Keeping {len(tables_to_keep)} most recent backup(s):")
    for _, table_name in backups[:keep_count]:
        print(f"  KEEP  {table_name}")

    if not tables_to_delete:
        print("No old backup tables found.")
        return []

    action = "Deleting" if execute else "Would delete"
    print(f"{action} {len(tables_to_delete)} old backup table(s):")
    for table_name in tables_to_delete:
        if execute:
            db.drop_table(table_name)
        print(f"  DELETE {table_name}")

    if not execute:
        print("Dry run only. Re-run with --execute to delete these tables.")
    return tables_to_delete


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge old timestamped LanceDB backup tables."
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP_COUNT,
        help=f"Number of newest backups to retain (default: {DEFAULT_KEEP_COUNT})",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=get_default_db_path(),
        help="Path to the LanceDB database",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually drop old backup tables; otherwise perform a dry run",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        purge_old_backups(args.db_path, args.keep, args.execute)
    except Exception as exc:
        print(f"Purge failed: {exc}")
        raise SystemExit(1)