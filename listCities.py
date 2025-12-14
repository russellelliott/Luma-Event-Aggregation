#!/usr/bin/env python3
"""
List cities from LanceDB sorted by travel time (duration_seconds).
"""

import os
import lancedb
import argparse
import json

def load_city_summary(db_path=None):
    """Load city summary from LanceDB database."""
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"LanceDB database not found at {db_path}")
    
    db = lancedb.connect(db_path)
    
    if "city_summary" not in db.table_names():
        raise FileNotFoundError(f"'city_summary' table not found in LanceDB at {db_path}")
    
    table = db.open_table("city_summary")
    return table.to_pandas()

def main():
    parser = argparse.ArgumentParser(description='List cities sorted by travel time')
    parser.add_argument('--db', type=str, default=None, help='Path to LanceDB database')
    args = parser.parse_args()

    try:
        df = load_city_summary(args.db)
        
        # Sort by duration_seconds (ascending)
        # Handle NaN values if any (though they should be populated)
        df = df.sort_values(by='duration_seconds', ascending=True)
        
        # Select relevant columns for display
        display_cols = ['city', 'event_count', 'duration_text', 'distance_text']
        
        # Check if columns exist (in case of schema changes)
        available_cols = [c for c in display_cols if c in df.columns]
        
        # Convert to list of dictionaries
        result = df[available_cols].to_dict(orient='records')
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
