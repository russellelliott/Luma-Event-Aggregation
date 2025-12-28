import lancedb
import os
import uuid
import pandas as pd

def migrate_db():
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    try:
        db = lancedb.connect(db_path)
        if "events" not in db.table_names():
            print("Table 'events' not found")
            return

        table = db.open_table("events")
        df = table.to_pandas()
        
        # Add 'id' column if missing
        if 'id' not in df.columns:
            print("Adding 'id' column with UUIDs...")
            df['id'] = [str(uuid.uuid4()) for _ in range(len(df))]
        else:
            print("'id' column already exists.")
            
        # Add 'bookmarked' column if missing
        if 'bookmarked' not in df.columns:
            print("Adding 'bookmarked' column...")
            df['bookmarked'] = False
        else:
            print("'bookmarked' column already exists.")
            
        # Overwrite the table with the new schema
        db.create_table("events", data=df, mode="overwrite")
        print("Successfully migrated database.")
            
    except Exception as e:
        print(f"Error updating database: {e}")

if __name__ == "__main__":
    migrate_db()
