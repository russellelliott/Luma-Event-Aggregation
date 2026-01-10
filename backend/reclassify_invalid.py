import concurrent.futures
import sys
import os
import difflib
import requests
import json

# Add current directory to path to allow importing from classifyEvents
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classifyEvents import (
    load_events_from_lancedb, 
    save_events_to_lancedb, 
    # classify_event, # We will implement our own smarter version locally 
    VALID_EVENT_TYPES, 
    VALID_AUDIENCE_TYPES,
    LABELING_PROMPT
)

def is_valid(event_entry):
    # Handle nested event structure if present
    event = event_entry.get('event', event_entry) if isinstance(event_entry, dict) else event_entry
    
    current_type = event.get('event_type')
    current_audience = event.get('audience')
    
    return (current_type and current_type.lower() in VALID_EVENT_TYPES and 
            current_audience and current_audience.lower() in VALID_AUDIENCE_TYPES)

def find_closest_match(value, valid_options):
    if not value or not isinstance(value, str):
        return None
    # Normalize inputs
    value_lower = value.lower().strip()
    # Get exact match
    if value_lower in valid_options:
        return value_lower
    # Get closest match
    matches = difflib.get_close_matches(value_lower, valid_options, n=1, cutoff=0.4)
    return matches[0] if matches else None

def classify_and_fix_event(event, model="phi3:3.8b-mini-128k-instruct-q4_K_M", max_retries=3):
    """Classify event, and if invalid, attempt to fuzzy match results."""
    name = event.get('name', 'Unknown Event')
    description = event.get('description', '')
    if not description:
        description = event.get('summary', 'No description provided.')

    prompt = LABELING_PROMPT.format(name=name, description=description)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    for attempt in range(max_retries):
        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            response_text = result.get('response', '{}')
            
            try:
                classification = json.loads(response_text)
                event_type = classification.get('event_type')
                audience = classification.get('audience')
                
                # Check directly
                if (event_type and event_type.lower() in VALID_EVENT_TYPES and 
                    audience and audience.lower() in VALID_AUDIENCE_TYPES):
                    return classification
                
                # If invalid, try fuzzy match
                print(f"  Attempt {attempt+1}: Invalid raw output (Type: '{event_type}', Audience: '{audience}'). Checking similarity...")
                
                new_type = find_closest_match(event_type, list(VALID_EVENT_TYPES))
                new_audience = find_closest_match(audience, list(VALID_AUDIENCE_TYPES))
                
                if new_type and new_audience:
                    print(f"  -> Fixed via similarity: Type '{event_type}'->'{new_type}', Audience '{audience}'->'{new_audience}'")
                    return {"event_type": new_type, "audience": new_audience}
                else:
                    print(f"  -> Could not fix via similarity. Retrying...")

            except json.JSONDecodeError:
                print(f"  Attempt {attempt+1}: Failed to parse JSON. Retrying...")
                
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt+1}: Error calling Ollama: {e}")
            
    print(f"  Failed to classify event '{name}' after {max_retries} attempts.")
    return None

def process_invalid_event(args):
    event_entry, index, total = args
    
    # Handle nested event structure
    event = event_entry.get('event', event_entry) if isinstance(event_entry, dict) else event_entry
    
    print(f"Re-classifying {index+1}/{total}: {event.get('name', 'Unknown')}")
    print(f"  Current invalid state: Type={event.get('event_type')}, Audience={event.get('audience')}")
    
    # Use our local improved classify function
    classification = classify_and_fix_event(event)
    
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
