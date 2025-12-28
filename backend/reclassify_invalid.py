import concurrent.futures
import sys
import os

# Add current directory to path to allow importing from classifyEvents
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classifyEvents import (
    load_events_from_lancedb, 
    save_events_to_lancedb, 
    classify_event, 
    VALID_EVENT_TYPES, 
    VALID_AUDIENCE_TYPES
)

def is_valid(event_entry):
    # Handle nested event structure if present
    event = event_entry.get('event', event_entry) if isinstance(event_entry, dict) else event_entry
    
    current_type = event.get('event_type')
    current_audience = event.get('audience')
    
    return (current_type and current_type.lower() in VALID_EVENT_TYPES and 
            current_audience and current_audience.lower() in VALID_AUDIENCE_TYPES)

def process_invalid_event(args):
    event_entry, index, total = args
    
    # Handle nested event structure
    event = event_entry.get('event', event_entry) if isinstance(event_entry, dict) else event_entry
    
    print(f"Re-classifying {index+1}/{total}: {event.get('name', 'Unknown')}")
    print(f"  Current invalid state: Type={event.get('event_type')}, Audience={event.get('audience')}")
    
    classification = classify_event(event)
    
    if classification:
        event_type = classification.get('event_type')
        audience = classification.get('audience')
        
        print(f"  -> New: Type: {event_type}, Audience: {audience}")
        
        event['event_type'] = event_type
        event['audience'] = audience
        return True
    else:
        print(f"  -> Failed to re-classify.")
        return False

def main():
    try:
        events = load_events_from_lancedb()
        total_events = len(events)
        
        # Identify invalid events
        invalid_indices = [i for i, e in enumerate(events) if not is_valid(e)]
        
        if not invalid_indices:
            print("No invalid events found. All events have valid classifications.")
            return

        print(f"Found {len(invalid_indices)} invalid events out of {total_events} total events.")
        
        # Prepare args only for invalid events
        # We pass the actual event object from the list so it gets modified in place
        event_args = [(events[i], i, len(invalid_indices)) for i in invalid_indices]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_invalid_event, event_args))
            
        updated_count = sum(results)
        
        if updated_count > 0:
            print(f"\nUpdating LanceDB with {updated_count} re-classified events...")
            save_events_to_lancedb(events)
        else:
            print("\nNo updates made.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
