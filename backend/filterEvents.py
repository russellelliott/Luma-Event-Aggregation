import json
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import lancedb
import os
import numpy as np
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo


def convert_to_serializable(obj):
    """Convert numpy types and other non-serializable objects to JSON-serializable types."""
    if isinstance(obj, np.ndarray):
        return convert_to_serializable(obj.tolist())
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    return obj

def load_events(db_path=None):
    """Load events from LanceDB database.
    
    Args:
        db_path: Path to LanceDB database directory (defaults to ~/.luma-event-aggregation/data)
        
    Returns:
        List of events
        
    Raises:
        FileNotFoundError: If database or events table not found
    """
    # Set default database path if not provided
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    # Load from LanceDB
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"LanceDB database not found at {db_path}\n"
            f"Run 'python fetchEvents.py' first to populate the database."
        )
    
    try:
        db = lancedb.connect(db_path)
        if "events" not in db.table_names():
            raise FileNotFoundError(
                f"'events' table not found in LanceDB at {db_path}\n"
                f"Run 'python fetchEvents.py' first to populate the database."
            )
        
        table = db.open_table("events")
        events = table.to_pandas().to_dict('records')
        
        # Calculate cosine similarity if embeddings exist
        try:
            # Check for numpy 2.x which might not be compatible with existing code if it uses removed features.
            # But standard numpy operations are fine.
            
            # Find bookmarked events with embeddings
            bookmarked_vectors = []
            for e in events:
                # Handle nested dict if necessary, bookmarked is top level usually
                is_bookmarked = e.get('bookmarked', False)
                vector = e.get('vector')
                
                if is_bookmarked and vector is not None and isinstance(vector, (list, np.ndarray)):
                     bookmarked_vectors.append(vector)
            
            if bookmarked_vectors:
                # Calculate mean vector
                # Convert to numpy array for efficiency
                bookmark_matrix = np.array(bookmarked_vectors)
                mean_vector = np.mean(bookmark_matrix, axis=0)
                
                # Normalize mean vector for cosine similarity
                norm_mean = np.linalg.norm(mean_vector)
                if norm_mean > 0:
                    mean_vector = mean_vector / norm_mean
                    
                    # Calculate distance for all events
                    for e in events:
                        vec = e.get('vector')
                        if vec is not None and isinstance(vec, (list, np.ndarray)):
                            vec_np = np.array(vec)
                            norm_vec = np.linalg.norm(vec_np)
                            if norm_vec > 0:
                                # Cosine Similarity = dot product of normalized vectors
                                # We already normalized mean_vector.
                                cosine_sim = np.dot(vec_np / norm_vec, mean_vector)
                                # Distance = 1 - Similarity
                                # Ensure range [0, 2]
                                e['cosine_distance'] = float(1 - cosine_sim)
                            else:
                                e['cosine_distance'] = None
                        else:
                            e['cosine_distance'] = None
            else:
                # No bookmarks with vectors, so no distance
                for e in events:
                    e['cosine_distance'] = None

        except Exception as e:
            print(f"⚠️ Warning: Failed to calculate embeddings distance: {e}")
            # Ensure field exists even if calculation fails
            for e in events:
                if 'cosine_distance' not in e:
                   e['cosine_distance'] = None

        print(f"📊 Loaded {len(events)} events from LanceDB")
        return events
    except Exception as e:
        raise FileNotFoundError(
            f"Error loading events from LanceDB at {db_path}: {e}\n"
            f"Run 'python fetchEvents.py' first to populate the database."
        )

def get_local_date_and_weekday(utc_iso_str, pacific_tz):
    dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
    dt_local = dt_utc.astimezone(pacific_tz)
    return dt_local.date(), dt_local.strftime("%A")

def get_city_from_event(event):
    """Extract city from event's geo_address_info."""
    # Handle case where event might be the raw event dict (from API)
    # or might have nested 'event' key (from JSON structure)
    if isinstance(event, dict) and 'event' in event:
        event = event['event']
    
    geo_info = event.get('geo_address_info', {})
    if isinstance(geo_info, dict):
        city = geo_info.get('city') or geo_info.get('city_state', 'Unknown city')
    else:
        city = 'Unknown city'
    
    return city if city else 'Unknown city'

def convert_to_local_time(utc_iso_str, timezone_str="America/Los_Angeles"):
    """Convert UTC timestamp to local timezone."""
    if not utc_iso_str:
        return None
    dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
    local_tz = ZoneInfo(timezone_str)
    dt_local = dt_utc.astimezone(local_tz)
    return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")

def filter_by_location(events, locations=None):
    if not locations:
        return events
    
    # Handle single string input (backward compatibility)
    if isinstance(locations, str):
        locations = [locations]
        
    locations_lower = set(loc.lower() for loc in locations)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        city = get_city_from_event(event_data)
        if city and city.lower() in locations_lower:
            filtered.append(e)
    return filtered

def filter_by_dates(events, dates, pacific_tz):
    if not dates:
        return events
    date_set = set(dates)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
        event_date, _ = get_local_date_and_weekday(start_at, pacific_tz)
        if event_date.isoformat() in date_set:
            filtered.append(e)
    return filtered

def filter_by_weekdays(events, weekdays, pacific_tz):
    if not weekdays:
        return events
    weekdays_set = set(day.capitalize() for day in weekdays)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
        _, event_weekday = get_local_date_and_weekday(start_at, pacific_tz)
        if event_weekday in weekdays_set:
            filtered.append(e)
    return filtered

def filter_by_event_type(events, event_types):
    if not event_types:
        return events
    event_types_set = set(t.lower() for t in event_types)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        event_type = event_data.get('event_type')
        audience = event_data.get('audience')
        
        # Check event_type
        if event_type and event_type.lower() in event_types_set:
            filtered.append(e)
        # Fallback: Check audience for misclassified events (e.g. social might end up in audience)
        elif audience and audience.lower() in event_types_set:
            filtered.append(e)
            
    return filtered

def filter_by_audience(events, audiences):
    if not audiences:
        return events
    audiences_set = set(a.lower() for a in audiences)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        audience = event_data.get('audience')
        if audience and audience.lower() in audiences_set:
            filtered.append(e)
    return filtered

def filter_by_dates_or_weekdays(events, dates, weekdays, pacific_tz):
    if not dates and not weekdays:
        return events

    date_set = set(dates) if dates else set()
    weekdays_set = set(day.capitalize() for day in weekdays) if weekdays else set()
    
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
            
        event_date, event_weekday = get_local_date_and_weekday(start_at, pacific_tz)
        
        match_date = event_date.isoformat() in date_set if dates else False
        match_weekday = event_weekday in weekdays_set if weekdays else False
        
        if match_date or match_weekday:
            filtered.append(e)
            
    return filtered

def filter_by_bookmarked(events, bookmarked):
    if not bookmarked:
        return events
    return [e for e in events if e.get('bookmarked', False)]

def filter_by_future(events, include_past, pacific_tz):
    if include_past:
        return events
    
    # Get current date in Pacific time
    current_date = datetime.now(pacific_tz).date()
    
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
        
        event_date, _ = get_local_date_and_weekday(start_at, pacific_tz)
        
        # Keep events from today onwards
        if event_date >= current_date:
            filtered.append(e)
            
    return filtered

def apply_filters(events, location=None, dates=None, weekdays=None, event_types=None, audiences=None, bookmarked=False, include_past=False):
    # Recalculate cosine distances based on current bookmarks
    # This ensures dynamic updates when bookmarks change
    try:
        # Find all currently bookmarked events with embeddings
        # Use simple iteration for safety
        bookmarked_vectors = []
        
        # Helper to safely navigate
        def get_field(item, key):
            val = item.get(key)
            if val is not None: return val
            if isinstance(item.get('event'), dict):
                return item['event'].get(key)
            return None

        for e in events:
            is_mark = get_field(e, 'bookmarked')
            vector = e.get('vector') # Vector is top-level only based on schema
            
            if is_mark is True and vector is not None and isinstance(vector, (list, np.ndarray)):
                bookmarked_vectors.append(vector)

        if bookmarked_vectors:
            # Calculate mean vector
            bookmark_matrix = np.array(bookmarked_vectors)
            mean_vector = np.mean(bookmark_matrix, axis=0)
            norm_mean = np.linalg.norm(mean_vector)

            if norm_mean > 0:
                mean_vector_normalized = mean_vector / norm_mean
                
                for e in events:
                    vec = e.get('vector')
                    if vec is not None and isinstance(vec, (list, np.ndarray)):
                        vec_np = np.array(vec)
                        norm_vec = np.linalg.norm(vec_np)
                        if norm_vec > 0:
                            # Cosine Sim
                            cosine_sim = np.dot(vec_np / norm_vec, mean_vector_normalized)
                            # Distance
                            e['cosine_distance'] = float(1 - cosine_sim)
                        else:
                            e['cosine_distance'] = None
                    else:
                        e['cosine_distance'] = None
            else:
                 for e in events: e['cosine_distance'] = None
        else:
             for e in events: e['cosine_distance'] = None

    except Exception as e:
        print(f"⚠️ Error updating cosine distances in apply_filters: {e}")

    pacific_tz = ZoneInfo("America/Los_Angeles")
    
    # Filter by past/future first
    events = filter_by_future(events, include_past, pacific_tz)
    
    events = filter_by_location(events, location)
    
    # Apply dates and weekdays with OR logic if either is present
    if dates or weekdays:
        events = filter_by_dates_or_weekdays(events, dates, weekdays, pacific_tz)
        
    events = filter_by_event_type(events, event_types)
    events = filter_by_audience(events, audiences)
    events = filter_by_bookmarked(events, bookmarked)
    return events

def parse_args():
    parser = argparse.ArgumentParser(description='Filter events from LanceDB database')
    parser.add_argument('--db', type=str, default=None, help='Path to LanceDB database (defaults to ~/.luma-event-aggregation/data/events.db)')
    parser.add_argument('--location', type=str, nargs='*', help='City name(s) to filter by (case-insensitive)')
    parser.add_argument('--dates', type=str, nargs='*', help='Specific date(s) to filter by (YYYY-MM-DD)')
    parser.add_argument('--weekdays', type=str, nargs='*', help='Weekday(s) to filter by (e.g., Monday Tuesday)')
    parser.add_argument('--event-type', type=str, nargs='*', help='Event type(s) to filter by (e.g., hackathon workshop)')
    parser.add_argument('--audience', type=str, nargs='*', help='Audience(s) to filter by (e.g., job_seekers founder_investor)')
    parser.add_argument('--today', action='store_true', help='Filter events happening today')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    try:
        events = load_events(db_path=args.db)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)
    
    # Handle --today flag
    if args.today:
        from datetime import date
        today = date.today().isoformat()
        args.dates = [today] if not args.dates else args.dates + [today]
    
    filtered_events = apply_filters(
        events,
        location=args.location,
        dates=args.dates,
        weekdays=args.weekdays,
        event_types=args.event_type,
        audiences=args.audience
    )
    
    # Convert to JSON output format with local times
    output = []
    for e in filtered_events:
        # Handle both nested and flat event structures from LanceDB
        event_data = e.get('event', e) if isinstance(e, dict) else e
        timezone = event_data.get('timezone', 'America/Los_Angeles')
        
        # Get the URL - it may be a full URL or just a slug
        event_url = event_data.get('url', '')
        if event_url and not event_url.startswith('http'):
            full_url = f"https://luma.com/{event_url}"
        else:
            full_url = event_url
        
        output.append({
            'name': event_data.get('name', 'Unnamed Event'),
            'city': get_city_from_event(event_data),
            'start': convert_to_local_time(event_data.get('start_at'), timezone),
            'end': convert_to_local_time(event_data.get('end_at'), timezone),
            'description': event_data.get('description'),
            'pricing': event_data.get('pricing'),
            'event_type': event_data.get('event_type'),
            'audience': event_data.get('audience'),
            'url': full_url
        })
    
    # Print summary and JSON output
    print(f"Filtered {len(output)} events matching criteria.\n")
    # Convert numpy types to JSON-serializable types
    output = convert_to_serializable(output)
    print(json.dumps(output, indent=2))

