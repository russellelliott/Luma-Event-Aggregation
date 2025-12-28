import lancedb
import os
import pyarrow as pa

def add_bookmark_column():
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
        
        if 'bookmarked' not in df.columns:
            print("Adding 'bookmarked' column...")
            df['bookmarked'] = False
            
            # Overwrite the table with the new schema
            # LanceDB allows overwriting.
            db.create_table("events", data=df, mode="overwrite")
            print("Successfully added 'bookmarked' column initialized to False.")
        else:
            print("'bookmarked' column already exists.")
            
    except Exception as e:
        print(f"Error updating database: {e}")

if __name__ == "__main__":
    add_bookmark_column()
