import json
import os
import lancedb
import requests
import pandas as pd
import concurrent.futures

LABELING_PROMPT = """Analyze this event and assign labels:

<event>
<title>{name}</title>
<description>{description}</description>
</event>

Task 1: Select ONE event type:
[career_fair, hackathon, workshop, networking, conference, demo_day, panel_discussion]

Task 2: Select ONE audience category:
- "job_seekers": For students, recent grads, engineers, anyone looking for jobs/internships, career development
- "founder_investor": For founders, VCs, investors, people raising/deploying capital
- "general": Explicitly open to everyone with no specific target

Return ONLY JSON:
{{"event_type": "...", "audience": "..."}}
"""

VALID_EVENT_TYPES = {
    'career_fair', 'hackathon', 'workshop', 'networking', 
    'conference', 'demo_day', 'panel_discussion'
}
VALID_AUDIENCE_TYPES = {'job_seekers', 'founder_investor', 'general'}

def load_events_from_lancedb(db_path=None):
    """Load events from LanceDB database."""
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

def classify_event(event, model="phi3:3.8b-mini-128k-instruct-q4_K_M", max_retries=3):
    """Classify a single event using Ollama with retries."""
    name = event.get('name', 'Unknown Event')
    description = event.get('description', '')
    
    # If description is missing or empty, try to use summary or just name
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
                
                if (event_type and event_type.lower() in VALID_EVENT_TYPES and 
                    audience and audience.lower() in VALID_AUDIENCE_TYPES):
                    return classification
                else:
                    print(f"⚠️ Invalid classification (Type: {event_type}, Audience: {audience}) for event '{name}'. Retrying ({attempt + 1}/{max_retries})...")
                    
            except json.JSONDecodeError:
                print(f"⚠️ Failed to parse JSON for event: {name}. Retrying ({attempt + 1}/{max_retries})...")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling Ollama: {e}")
            return None
            
    print(f"❌ Failed to classify event '{name}' after {max_retries} attempts.")
    return None

def save_events_to_lancedb(events, db_path=None):
    """Save events back to LanceDB, overwriting the existing table."""
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    db = lancedb.connect(db_path)
    
    # Use overwrite mode to update the existing table with the classified data
    db.create_table("events", data=events, mode="overwrite")
    print(f"💾 Updated 'events' table in LanceDB with {len(events)} records")

def process_event_wrapper(args):
    """Wrapper for parallel processing."""
    event_entry, index, total = args
    
    # Handle both nested and flat event structures
    event = event_entry.get('event', event_entry) if isinstance(event_entry, dict) else event_entry
    
    # Skip if already classified AND valid
    current_type = event.get('event_type')
    current_audience = event.get('audience')
    
    if (current_type and current_type.lower() in VALID_EVENT_TYPES and 
        current_audience and current_audience.lower() in VALID_AUDIENCE_TYPES):
        print(f"Skipping {index+1}/{total}: {event.get('name', 'Unknown')} (Already classified & valid)")
        return False

    print(f"Processing {index+1}/{total}: {event.get('name', 'Unknown')}\n  URL: {event.get('url', 'No URL')}")
    classification = classify_event(event)
    
    if classification:
        event_type = classification.get('event_type')
        audience = classification.get('audience')
        
        print(f"  -> {event.get('name', 'Unknown')}: Type: {event_type}, Audience: {audience}")
        
        # Update the event object directly
        event['event_type'] = event_type
        event['audience'] = audience
        return True
    else:
        print(f"  -> {event.get('name', 'Unknown')}: Classification failed.")
        return False

def main():
    try:
        events = load_events_from_lancedb()
        total_events = len(events)
        print(f"🚀 Starting classification for {total_events} events...")
        
        # Prepare arguments for parallel processing
        event_args = [(event, i, total_events) for i, event in enumerate(events)]
        
        # Use ThreadPoolExecutor for parallel processing
        # Adjust max_workers based on your Ollama server capabilities
        # Using 4 workers as a reasonable default for local LLM inference
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_event_wrapper, event_args))
            
        updated_count = sum(results)
        
        if updated_count > 0:
            print(f"\nUpdating LanceDB with {updated_count} new classifications...")
            save_events_to_lancedb(events)
        else:
            print("\nNo new classifications to save.")
            
        print(f"\n✅ Classification complete.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
