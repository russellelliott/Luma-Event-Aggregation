
import lancedb
import os
import pandas as pd

def inspect_non_california():
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    print(f"Connected to LanceDB at {db_path}")
    print(f"Tables: {db.table_names()}")

    # Check city_summary table
    if "city_summary" in db.table_names():
        print("\n--- Checking 'city_summary' table ---")
        tbl = db.open_table("city_summary")
        df = tbl.to_pandas()
        
        # Filter for non-California cities
        # Assuming 'city' column exists
        
        # Whitelist of Bay Area cities that might appear without state
        whitelist = [
            "San Francisco", "Palo Alto", "Mountain View", "Sunnyvale", "San Jose", 
            "Santa Clara", "Cupertino", "Menlo Park", "Redwood City", "San Mateo", 
            "Berkeley", "Oakland", "Fremont", "Hayward", "San Ramon", "Pleasanton", 
            "Livermore", "Walnut Creek", "Los Gatos", "Saratoga", "Campbell", "Milpitas", 
            "Union City", "Newark", "Daly City", "South San Francisco", "Burlingame", 
            "Millbrae", "San Bruno", "Foster City", "Belmont", "San Carlos", "Atherton", 
            "Woodside", "Portola Valley", "Los Altos", "Los Altos Hills", "Stanford", 
            "East Palo Alto", "Emeryville", "Alameda", "Albany", "El Cerrito", "Richmond", 
            "San Leandro", "Castro Valley", "Dublin", "Pleasant Hill", "Concord", 
            "Lafayette", "Orinda", "Moraga", "Danville", "Alamo", "San Rafael", 
            "Sausalito", "Tiburon", "Mill Valley", "Corte Madera", "Larkspur", 
            "San Anselmo", "Fairfax", "Novato", "Half Moon Bay", "Pacifica", "Brisbane", 
            "Hillsborough", "Sunol"
        ]
        # Convert whitelist to lowercase for case-insensitive matching
        whitelist_lower = [c.lower() for c in whitelist]

        if 'city' in df.columns:
            # Logic: Keep if contains "California" OR ", CA" OR is in whitelist
            
            def is_california(city_name):
                if not isinstance(city_name, str):
                    return False
                if "California" in city_name or ", CA" in city_name:
                    return True
                # Check exact match against whitelist (ignoring case)
                if city_name.lower() in whitelist_lower:
                    return True
                return False

            non_cal_df = df[~df['city'].apply(is_california)]
            
            print(f"Found {len(non_cal_df)} non-California cities in summary:")
            if not non_cal_df.empty:
                print(non_cal_df[['city', 'event_count', 'status']].to_string())
        else:
            print("Column 'city' not found in city_summary table")

    # Check events table
    if "events" in db.table_names():
        print("\n--- Checking 'events' table ---")
        tbl = db.open_table("events")
        df = tbl.to_pandas()
        
        non_cal_events = []
        
        for index, row in df.iterrows():
            city = "Unknown"
            
            event_data = row.get('event')
            calendar_data = row.get('calendar')
            
            # Helper to get city string
            city_str = None
            
            if isinstance(event_data, dict):
                geo = event_data.get('geo_address_info', {})
                if isinstance(geo, dict):
                    city_str = geo.get('city_state') or geo.get('city')
            
            if not city_str and isinstance(calendar_data, dict):
                cal_city = calendar_data.get('geo_city')
                cal_region = calendar_data.get('geo_region')
                if cal_city:
                    if cal_region:
                        city_str = f"{cal_city}, {cal_region}"
                    else:
                        city_str = cal_city
            
            if city_str:
                # Use same is_california logic
                if not is_california(city_str):
                    non_cal_events.append({
                        "name": row.get('event', {}).get('name') if isinstance(row.get('event'), dict) else "Unknown",
                        "city": city_str,
                        "api_id": row.get('api_id')
                    })

        
        print(f"Found {len(non_cal_events)} events with non-California locations:")
        if non_cal_events:
            for e in non_cal_events[:20]: # Show first 20
                print(f"  - {e['city']}: {e['name']} ({e['api_id']})")
            if len(non_cal_events) > 20:
                print(f"  ... and {len(non_cal_events) - 20} more")

if __name__ == "__main__":
    inspect_non_california()
