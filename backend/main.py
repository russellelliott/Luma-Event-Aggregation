from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import json
import os
import math
import lancedb
from listCities import load_city_summary
from filterEvents import load_events, apply_filters, convert_to_serializable, get_city_from_event
from pydantic import BaseModel
from eventDescription import get_luma_event_info
from classifyEvents import classify_event
from datetime import datetime
import uuid
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load data at startup
print("Loading data...")
try:
    CITY_SUMMARY_DF = load_city_summary()
    print(f"📊 Loaded {len(CITY_SUMMARY_DF)} cities from LanceDB")
    # Sort by duration_seconds (ascending)
    if 'duration_seconds' in CITY_SUMMARY_DF.columns:
        CITY_SUMMARY_DF = CITY_SUMMARY_DF.sort_values(by='duration_seconds', ascending=True)
    
    ALL_EVENTS = load_events()
    print("Data loaded successfully.")
except Exception as e:
    print(f"Error loading data: {e}")
    CITY_SUMMARY_DF = None
    ALL_EVENTS = []

def clean_nans(data):
    """Recursively replace NaN values with None in a dictionary or list."""
    if isinstance(data, list):
        return [clean_nans(item) for item in data]
    elif isinstance(data, dict):
        return {k: clean_nans(v) for k, v in data.items()}
    elif isinstance(data, float) and math.isnan(data):
        return None  # Convert NaN to JSON-compliant null
    return data

@app.get("/cities")
def get_cities():
    try:
        if CITY_SUMMARY_DF is None:
            return {"error": "City summary data not loaded"}
        
        # Convert to list of dictionaries
        result = CITY_SUMMARY_DF.to_dict(orient='records')
        return clean_nans(convert_to_serializable(result))
    except Exception as e:
        return {"error": str(e)}

@app.get("/events")
def get_events(
    location: Optional[List[str]] = Query(None),
    dates: Optional[List[str]] = Query(None),
    weekdays: Optional[List[str]] = Query(None),
    event_type: Optional[List[str]] = Query(None, alias="event-type"),
    audience: Optional[List[str]] = Query(None)
):
    try:
        filtered_events = apply_filters(
            ALL_EVENTS, 
            location=location, 
            dates=dates, 
            weekdays=weekdays, 
            event_types=event_type, 
            audiences=audience
        )
        
        # Normalize URLs in the response
        response_events = []
        for e in filtered_events:
            # Create a copy to avoid modifying the in-memory cache if we want to keep it raw
            # But actually, modifying it is fine or we can just return a modified dict
            event_copy = e.copy()
            
            # Handle nested event structure
            event_data = event_copy.get('event', event_copy) if isinstance(event_copy, dict) else event_copy
            
            # Normalize URL
            url = event_data.get('url')
            if url and not url.startswith('http'):
                # It's a slug, make it a full Luma URL
                full_url = f"https://lu.ma/{url}"
                
                # Update the URL in the appropriate place
                if isinstance(event_copy.get('event'), dict):
                    event_copy['event']['url'] = full_url
                else:
                    event_copy['url'] = full_url
            
            response_events.append(event_copy)
            
        return clean_nans(convert_to_serializable(response_events))
    except Exception as e:
        return {"error": str(e)}

class EventUrl(BaseModel):
    url: str

@app.post("/add-event")
def add_event(event_url: EventUrl):
    global ALL_EVENTS
    try:
        print(f"Adding event from URL: {event_url.url}")
        # 1. Fetch info
        info = get_luma_event_info(event_url.url)
        if 'error' in info:
            return {"error": info['error']}
        
        # 2. Classify
        classification = classify_event(info)
        event_type = 'networking'
        audience = 'general'
        if classification:
            event_type = classification.get('event_type', 'networking')
            audience = classification.get('audience', 'general')
            
        # 3. Prepare data structure matching schema
        api_id = info.get('url', '').split('/')[-1]
        record_id = str(uuid.uuid4())
        start_at = info.get('start_date')
        
        # Construct 'event' struct
        event_struct = {
            'api_id': api_id,
            'name': info.get('name'),
            'description': info.get('description'),
            'start_at': start_at,
            'url': info.get('url'),
            'event_type': event_type,
            'audience': audience
        }

        # Handle coordinates
        lat = info.get('latitude')
        lng = info.get('longitude')
        if lat is not None and lng is not None:
            try:
                event_struct['coordinate'] = {
                    'latitude': float(lat),
                    'longitude': float(lng)
                }
            except (ValueError, TypeError):
                pass
            
        # Handle address/location
        geo_address_info = {}
        address_data = info.get('address')
        if isinstance(address_data, dict):
            geo_address_info['city'] = address_data.get('addressLocality')
            geo_address_info['region'] = address_data.get('addressRegion')
            geo_address_info['country'] = address_data.get('addressCountry')
            geo_address_info['address'] = address_data.get('streetAddress')
            
            # Construct city_state
            city = geo_address_info.get('city')
            region = geo_address_info.get('region')
            if city and region:
                geo_address_info['city_state'] = f"{city}, {region}"
            elif city:
                geo_address_info['city_state'] = city
        
        if geo_address_info:
            event_struct['geo_address_info'] = geo_address_info

        # Construct top-level record
        new_record = {
            'api_id': api_id,
            'event': event_struct,
            'start_at': start_at,
            'event_type': event_type,
            'audience': audience,
            'bookmarked': False,
            'id': record_id
        }

        # 5. Save to DB
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
        db = lancedb.connect(db_path)
        
        try:
            table = db.open_table("events")
            table.add([new_record])
        except Exception as e:
            print(f"⚠️ Add failed: {e}")
            print("🔄 Attempting to update schema via overwrite...")
            try:
                # Read existing data
                table = db.open_table("events")
                existing_data = table.to_pandas().to_dict('records')
                
                # Append new record
                existing_data.append(new_record)
                
                # Overwrite table
                db.create_table("events", data=existing_data, mode="overwrite")
                print("✅ Schema updated and event added.")
            except Exception as e2:
                print(f"❌ Overwrite failed: {e2}")
                return {"error": f"Failed to add event: {str(e)} -> {str(e2)}"}
        
        # Reload ALL_EVENTS
        ALL_EVENTS = load_events()
        
        return {"message": "Event added successfully", "event": new_record}
        
    except Exception as e:
        print(f"Error adding event: {e}")
        return {"error": str(e)}

@app.post("/events/{event_id}/bookmark")
def bookmark_event(event_id: str, bookmarked: bool):
    try:
        # Update LanceDB
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
        db = lancedb.connect(db_path)
        table = db.open_table("events")
        
        # Update the row
        # LanceDB update syntax: table.update(where=..., values=...)
        table.update(where=f"id = '{event_id}'", values={"bookmarked": bookmarked})
        
        # Update in-memory data
        global ALL_EVENTS
        for event in ALL_EVENTS:
            if event.get('id') == event_id:
                event['bookmarked'] = bookmarked
                break
        
        return {"status": "success", "id": event_id, "bookmarked": bookmarked}
    except Exception as e:
        return {"error": str(e)}

@app.get("/bookmarks")
def get_bookmarks():
    try:
        # Filter for bookmarked events
        bookmarked_events = [e for e in ALL_EVENTS if e.get('bookmarked', False)]
        
        # Sort by start_at
        def get_start_time(e):
            # Try to get start_at from top level or nested event
            start_at = e.get('start_at')
            if not start_at and isinstance(e.get('event'), dict):
                start_at = e['event'].get('start_at')
            return start_at or ""

        bookmarked_events.sort(key=get_start_time)

        # Enrich with distance info
        city_lookup = {}
        if CITY_SUMMARY_DF is not None:
            for _, row in CITY_SUMMARY_DF.iterrows():
                city_lookup[row['city']] = {
                    'distance_miles': row.get('distance_miles'),
                    'duration_minutes': row.get('duration_minutes'),
                    'distance_text': row.get('distance_text'),
                    'duration_text': row.get('duration_text')
                }
        
        results = []
        for event in bookmarked_events:
            event_copy = event.copy()
            
            # Logic to extract city matching fetchEvents.py's extract_city as closely as possible
            # to ensure we hit the cache keys in city_lookup
            ev_data = event.get('event', {}) if isinstance(event.get('event'), dict) else event
            geo = ev_data.get('geo_address_info', {}) if isinstance(ev_data.get('geo_address_info'), dict) else {}
            
            city_key = "Unknown"
            
            # Try city_state first (e.g. "San Francisco, California")
            if geo.get('city_state'):
                city_key = geo.get('city_state')
            # Then try city (e.g. "San Francisco")
            elif geo.get('city'):
                city_key = geo.get('city')
            # Then try calendar city
            elif event.get('calendar', {}).get('geo_city'):
                cal_city = event.get('calendar', {}).get('geo_city')
                cal_region = event.get('calendar', {}).get('geo_region')
                if cal_city and cal_region:
                    city_key = f"{cal_city}, {cal_region}"
                elif cal_city:
                    city_key = cal_city
            
            # Try to find distance info
            dist_info = city_lookup.get(city_key)
            
            # If not found, try simple city name if we had a state
            if not dist_info and "," in city_key:
                simple_city = city_key.split(",")[0].strip()
                dist_info = city_lookup.get(simple_city)
                
            if dist_info:
                event_copy['distance_info'] = dist_info
            
            results.append(event_copy)
            
        return clean_nans(convert_to_serializable(results))
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
