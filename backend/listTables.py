import lancedb
import os
from pathlib import Path
import re

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
        tables = db.table_names()
        
        if not tables:
            print("No tables found in the database.")
            return

        print(f"\nFound {len(tables)} tables:")
        
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
        sorted_tables = sorted(tables, key=sort_key, reverse=True)

        print(f"{'Table Name':<45} | {'Size Estimate':<15}")
        print("-" * 65)

        for table_name in sorted_tables:
            try:
                tbl = db.open_table(table_name)
                # count_rows might depend on lancedb version, try/except
                try:
                    count = tbl.count_rows()
                except:
                    # Fallback for older versions or if count_rows missing
                    count = len(tbl.to_pandas())
                print(f"{table_name:<45} | {count:<15}")
            except Exception as e:
                print(f"{table_name:<45} | Error: {e}")
            
    except Exception as e:
        print(f"Error listing tables: {e}")

if __name__ == "__main__":
    list_tables()