import argparse
import os

import lancedb


DEFAULT_BACKUP_TABLE = "events_backup_1775677802"


def get_db_path() -> str:
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def restore_events_table(backup_table_name: str) -> None:
    db_path = get_db_path()

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at: {db_path}")

    db = lancedb.connect(db_path)

    # Use Arrow directly to preserve nested struct/list types.
    backup_table = db.open_table(backup_table_name)
    backup_data = backup_table.to_arrow()
    row_count = backup_table.count_rows()

    try:
        db.drop_table("events")
    except Exception:
        pass

    db.create_table("events", data=backup_data)

    print(f"Restored 'events' from '{backup_table_name}' with {row_count} rows.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore the events table from a backup table."
    )
    parser.add_argument(
        "--backup-table",
        default=DEFAULT_BACKUP_TABLE,
        help=f"Backup table name to restore from (default: {DEFAULT_BACKUP_TABLE})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        restore_events_table(backup_table_name=args.backup_table)
        print("Restore complete.")
    except Exception as exc:
        print(f"Restore failed: {exc}")
        raise SystemExit(1)
