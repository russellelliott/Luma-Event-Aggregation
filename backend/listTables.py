import lancedb
import os
from pathlib import Path
import re
import ast


VALID_TABLE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def extract_table_names(raw):
    """Extract table names from LanceDB responses across versions."""
    if raw is None:
        return [], None

    # SDK object shape: ListTablesResponse(tables=[...], page_token=...)
    if hasattr(raw, "tables"):
        tables_attr = getattr(raw, "tables", None)
        token_attr = getattr(raw, "page_token", None)
        if isinstance(tables_attr, list):
            return [str(x) for x in tables_attr], token_attr

    def parse_tables_string(text):
        if not isinstance(text, str):
            return None
        if not text.startswith("tables="):
            return None
        match = re.search(r"tables=(\[[\s\S]*\])\s+page_token=(.*)$", text)
        if not match:
            return None
        tables_str = match.group(1)
        token_str = match.group(2).strip()
        try:
            parsed_tables = ast.literal_eval(tables_str)
        except Exception:
            parsed_tables = []
        if not isinstance(parsed_tables, list):
            parsed_tables = []
        token = None if token_str in {"None", "null", ""} else token_str
        return [str(x) for x in parsed_tables], token

    # String shape from some builds: "tables=[...] page_token=None"
    parsed_from_string = parse_tables_string(raw)
    if parsed_from_string is not None:
        return parsed_from_string

    # Sometimes wrapped as a one-item string list: ["tables=[...] page_token=None"]
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], str):
        parsed_wrapped = parse_tables_string(raw[0])
        if parsed_wrapped is not None:
            return parsed_wrapped

    # Simple list shape: ["events", "city_summary"]
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return raw, None

    # Dict shape: {"tables": [...], "page_token": ...}
    if isinstance(raw, dict):
        tables = raw.get("tables") if isinstance(raw.get("tables"), list) else []
        token = raw.get("page_token")
        return [str(x) for x in tables], token

    # Tuple-list shape: [("tables", [...]), ("page_token", ...)]
    if isinstance(raw, list) and raw and all(isinstance(x, (tuple, list)) and len(x) == 2 for x in raw):
        as_dict = dict(raw)
        tables = as_dict.get("tables") if isinstance(as_dict.get("tables"), list) else []
        token = as_dict.get("page_token")
        return [str(x) for x in tables], token

    # Fallback: best effort stringification
    if isinstance(raw, list):
        return [str(x) for x in raw], None
    return [str(raw)], None


def get_all_tables(db):
    """Retrieve all table names, handling pagination if list_tables provides page tokens."""
    if hasattr(db, "list_tables"):
        tables = []
        seen = set()
        page_token = None

        while True:
            try:
                if page_token:
                    raw = db.list_tables(page_token=page_token)
                else:
                    raw = db.list_tables()
            except TypeError:
                # Some versions do not support page_token argument.
                raw = db.list_tables()
                names, _ = extract_table_names(raw)
                return names

            names, next_token = extract_table_names(raw)
            for name in names:
                if name not in seen:
                    seen.add(name)
                    tables.append(name)

            if not next_token:
                break
            page_token = next_token

        return tables

    if hasattr(db, "table_names"):
        return db.table_names() or []

    return []

def list_tables():
    # Correct path for this project's database
    home_dir = Path.home()
    db_path = home_dir / ".luma-event-aggregation" / "data" / "events.db"
    
    if not db_path.exists():
        print(f"Database directory not found at: {db_path}")
        return

    print(f"Connecting to database at: {db_path}")
    try:
        db = lancedb.connect(db_path)
        tables = get_all_tables(db)
        
        if not tables:
            print("No tables found in the database.")
            return

        valid_tables = [name for name in tables if VALID_TABLE_RE.match(name)]
        invalid_tables = [name for name in tables if not VALID_TABLE_RE.match(name)]

        print(f"\nFound {len(valid_tables)} tables:")
        if invalid_tables:
            print(f"Skipped {len(invalid_tables)} invalid table entries from listing response.")
        
        # Sort tables: 'events' first, 'city_summary' second, then backups sorted by recency
        def sort_key(name):
            if name == 'events':
                return (3, 0)
            if name == 'city_summary':
                return (2, 0)
            # Try to find timestamp in name for backups
            match = re.search(r'(\d{10,})', name)
            timestamp = int(match.group(1)) if match else 0
            return (0, timestamp)

        # Sort descending by priority then timestamp
        sorted_tables = sorted(valid_tables, key=sort_key, reverse=True)

        print(f"{'Table Name':<60} | {'Rows':<10}")
        print("-" * 75)

        for table_name in sorted_tables:
            try:
                tbl = db.open_table(table_name)
                # count_rows might depend on lancedb version, try/except
                try:
                    count = tbl.count_rows()
                except:
                    # Fallback for older versions or if count_rows missing
                    count = len(tbl.to_pandas())
                display_name = table_name if len(table_name) <= 60 else table_name[:57] + "..."
                print(f"{display_name:<60} | {count:<10}")
            except Exception as e:
                display_name = table_name if len(table_name) <= 60 else table_name[:57] + "..."
                print(f"{display_name:<60} | Error")
            
    except Exception as e:
        print(f"Error listing tables: {e}")

if __name__ == "__main__":
    list_tables()