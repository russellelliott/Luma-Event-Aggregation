import argparse
import os

import lancedb


DEFAULT_TABLE_NAME = "events"


def get_db_path() -> str:
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def delete_table(table_name: str = DEFAULT_TABLE_NAME) -> None:
    db_path = get_db_path()

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at: {db_path}")

    db = lancedb.connect(db_path)
    table_names = db.table_names()

    if table_name not in table_names:
        print(f"Table '{table_name}' does not exist. Nothing to delete.")
        return

    db.drop_table(table_name)
    print(f"Deleted table '{table_name}' from {db_path}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete a table from the local LanceDB database."
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE_NAME,
        help=f"Table name to delete (default: {DEFAULT_TABLE_NAME})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        delete_table(table_name=args.table)
        print("Delete operation complete.")
    except Exception as exc:
        print(f"Delete failed: {exc}")
        raise SystemExit(1)
