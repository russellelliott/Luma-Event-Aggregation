import json
from eventDescription import get_luma_event_info


def generate_descriptions_for_all_events(json_file_path):
    """
    Generate descriptions and pricing for all events in combined_events.json.
    Adds the data directly to the event objects.
    
    Args:
        json_file_path (str): Path to the combined_events.json file
    
    Returns:
        list: List of events with added descriptions and pricing
    """
    # Load the combined events
    with open(json_file_path, 'r') as f:
        events = json.load(f)
    
    print(f"Processing {len(events)} events sequentially...\n")
    events_with_descriptions = []
    
    for i, event_entry in enumerate(events):
        # Extract the event URL slug
        event_url = event_entry.get('event', {}).get('url')
        event_name = event_entry.get('event', {}).get('name', 'Unknown Event')
        
        if event_url:
            print(f"[{i+1}/{len(events)}] Processing: {event_name}")
            
            # Get event information using the slug
            event_info = get_luma_event_info(event_url)
            
            # Add description and pricing to the event object
            if 'error' not in event_info:
                # Add description to event
                if 'description' in event_info:
                    event_entry['event']['description'] = event_info['description']
                
                # Add pricing information to event
                if 'pricing' in event_info:
                    event_entry['event']['pricing'] = event_info['pricing']
                
                print(f"  ✓ Description and pricing added")
            else:
                print(f"  ⚠️  Error: {event_info['error']}")
                # Still add error info for reference
                event_entry['event']['fetch_error'] = event_info['error']
        else:
            print(f"[{i+1}/{len(events)}] Skipping: {event_name} (no URL found)")
            event_entry['event']['fetch_error'] = 'No URL found'
        
        events_with_descriptions.append(event_entry)
    
    return events_with_descriptions


def save_descriptions(events_with_descriptions, output_path):
    """
    Save events with descriptions to a new JSON file.
    
    Args:
        events_with_descriptions (list): List of events with descriptions
        output_path (str): Path where to save the output file
    """
    with open(output_path, 'w') as f:
        json.dump(events_with_descriptions, f, indent=2)
    print(f"\n✓ Descriptions saved to: {output_path}")


if __name__ == '__main__':
    # Path to combined events
    combined_events_path = 'aggregatedEvents/combined_events.json'
    output_path = 'aggregatedEvents/combined_events_with_descriptions.json'
    
    # Generate descriptions for all events
    events_with_descriptions = generate_descriptions_for_all_events(combined_events_path)
    
    # Save the results
    save_descriptions(events_with_descriptions, output_path)
