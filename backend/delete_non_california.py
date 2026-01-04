
import lancedb
import os
import pandas as pd

def delete_non_california():
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    print(f"Connected to LanceDB at {db_path}")

    # Whitelist of Bay Area cities
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
    whitelist_lower = [c.lower() for c in whitelist]

    def is_california(city_name):
        if not isinstance(city_name, str):
            return False
        if "California" in city_name or ", CA" in city_name:
            return True
        if city_name.lower() in whitelist_lower:
            return True
        return False

    # 1. Clean up city_summary table
    if "city_summary" in db.table_names():
        print("\n--- Cleaning 'city_summary' table ---")
        tbl = db.open_table("city_summary")
        df = tbl.to_pandas()
        
        if 'city' in df.columns:
            cities_to_delete = df[~df['city'].apply(is_california)]['city'].tolist()
            
            if cities_to_delete:
                print(f"Found {len(cities_to_delete)} non-California cities to delete.")
                # Construct delete query
                # Escape single quotes in city names if necessary
                quoted_cities = [c.replace("'", "''") for c in cities_to_delete]
                
                # Delete in batches if too many
                batch_size = 50
                for i in range(0, len(quoted_cities), batch_size):
                    batch = quoted_cities[i:i+batch_size]
                    where_clause = f"city IN ({', '.join([f"'{c}'" for c in batch])})"
                    try:
                        tbl.delete(where_clause)
                        print(f"✓ Deleted batch {i//batch_size + 1} ({len(batch)} cities).")
                    except Exception as e:
                        print(f"❌ Error deleting batch {i//batch_size + 1}: {e}")
            else:
                print("No non-California cities found in summary.")

    # 2. Clean up events table
    if "events" in db.table_names():
        print("\n--- Cleaning 'events' table ---")
        tbl = db.open_table("events")
        df = tbl.to_pandas()
        
        ids_to_delete = []
        
        for index, row in df.iterrows():
            city_str = None
            event_data = row.get('event')
            calendar_data = row.get('calendar')
            
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
                if not is_california(city_str):
                    ids_to_delete.append(row.get('api_id'))
        
        if ids_to_delete:
            print(f"Found {len(ids_to_delete)} non-California events to delete.")
            
            # Delete in batches to avoid huge query strings
            batch_size = 100
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i:i+batch_size]
                quoted_ids = [f"'{id}'" for id in batch]
                where_clause = f"api_id IN ({', '.join(quoted_ids)})"
                
                try:
                    tbl.delete(where_clause)
                    print(f"✓ Deleted batch {i//batch_size + 1} ({len(batch)} events).")
                except Exception as e:
                    print(f"❌ Error deleting batch {i//batch_size + 1}: {e}")
            
            print("✓ Finished deleting events.")
        else:
            print("No non-California events found.")

if __name__ == "__main__":
    delete_non_california()
