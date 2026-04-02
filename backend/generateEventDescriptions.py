import json
import os
import lancedb
from eventDescription import get_luma_event_info


def load_events_from_lancedb(db_path=None):
    """Load events from LanceDB database.
    
    Args:
        db_path: Path to LanceDB database (defaults to ~/.luma-event-aggregation/data)
        
    Returns:
        List of events
    """
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"LanceDB database not found at {db_path}")
    
    db = lancedb.connect(db_path)
    if "events" not in db.table_names():
        raise FileNotFoundError(f"'events' table not found in LanceDB")
    
    table = db.open_table("events")
    events = table.to_pandas().to_dict('records')
    print(f"📊 Loaded {len(events)} events from LanceDB")
    return events


def persist_single_event_update(event_entry, db_path=None):
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")

    db = lancedb.connect(db_path)
    table = db.open_table("events")
    event_id = event_entry.get("id")
    if not event_id:
        return

    table.update(
        where=f"id = '{event_id}'",
        values={
            "description": event_entry.get("description"),
            "pricing": event_entry.get("pricing"),
        },
    )


def generate_descriptions_for_all_events(events, delay=1.0, db_path=None):
    """
    Generate descriptions and pricing for all events.
    Adds the data directly to the event objects.
    
    Args:
        events (list): List of events
        delay (float): Delay in seconds between requests (default: 1.0)
    
    Returns:
        list: List of events with added descriptions and pricing
    """
    print(f"Processing {len(events)} events sequentially with {delay}s delay between requests...\n")
    for i, event_entry in enumerate(events):
        event_url = event_entry.get('url')
        event_name = event_entry.get('name', 'Unknown Event')
        
        if event_url:
            # Check if we already have the description
            if event_entry.get('description'):
                print(f"[{i+1}/{len(events)}] Skipping: {event_name} (already has description)")
                continue

            print(f"[{i+1}/{len(events)}] Processing: {event_name}")
            print(f"  URL: {event_url}")
            
            # Get event information using the slug with specified delay
            event_info = get_luma_event_info(event_url, delay=delay)
            
            # Add description and pricing to the event object
            if 'error' not in event_info:
                # Add description to event
                if 'description' in event_info:
                    event_entry['description'] = event_info['description']
                
                # Add pricing information to event
                if 'pricing' in event_info:
                    event_entry['pricing'] = event_info['pricing']

                persist_single_event_update(event_entry, db_path=db_path)
                
                print(f"  ✓ Description and pricing added and persisted")
            else:
                print(f"  ⚠️  Error: {event_info['error']}")
                # Still add error info for reference
                event_entry['fetch_error'] = event_info['error']
        else:
            print(f"[{i+1}/{len(events)}] Skipping: {event_name} (no URL found)")
            event_entry['fetch_error'] = 'No URL found'

    return events


def save_descriptions_to_lancedb(events_with_descriptions, db_path=None):
    """
    Save events with descriptions back to LanceDB.
    
    Args:
        events_with_descriptions (list): List of events with descriptions
        db_path: Path to LanceDB database (defaults to ~/.luma-event-aggregation/data)
    """
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    db = lancedb.connect(db_path)
    
    # Drop and recreate the events table with updated data
    if "events" in db.table_names():
        db.drop_table("events")
    
    db.create_table("events", data=events_with_descriptions)
    print(f"\n✓ Descriptions saved to LanceDB: {db_path}")


if __name__ == '__main__':
    try:
        # Load events from LanceDB
        events = load_events_from_lancedb()
        
        # Generate descriptions for all events (1 second delay per request)
        events_with_descriptions = generate_descriptions_for_all_events(events, delay=1.0)
        
        print(f"\n🎉 Successfully processed {len(events_with_descriptions)} events!")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Run 'python fetchEvents.py' first to populate the database.")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
