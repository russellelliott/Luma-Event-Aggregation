import os
import lancedb
from datetime import datetime

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")

def backup_lancedb_table(db, table_name, verbose=True):
    """Creates a timestamped backup of a specific LanceDB table."""
    try:
        table = db.open_table(table_name)
        timestamp = int(datetime.now().timestamp())
        backup_name = f"{table_name}_backup_{timestamp}"
        
        df = table.to_pandas()
        db.create_table(backup_name, df)
        
        if verbose:
            print(f"   📦 Created backup table: {backup_name}")
        return backup_name
    except Exception as e:
        print(f"   ❌ Failed to create backup: {e}")
        return None

if __name__ == "__main__":
    try:
        db = lancedb.connect(db_path)
        backup_lancedb_table(db, "events", verbose=True)
        print("✅ Backup completed successfully!")
    except Exception as e:
        print(f"❌ Error during backup: {e}")
        exit(1)
