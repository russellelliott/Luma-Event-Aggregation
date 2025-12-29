#!/usr/bin/env python3
"""Fetch and aggregate Luma events from multiple slugs into LanceDB.

This script:
1. Automatically detects your location from IP address
2. Fetches events from multiple Luma slugs in parallel 
3. Saves all events into a LanceDB database
4. Generates city summaries with Google Maps distance/time data (REQUIRED)

REQUIREMENTS:
- GOOGLE_MAPS_API_KEY environment variable must be set
- Internet connection for IP-based location detection

Usage:
  export GOOGLE_MAPS_API_KEY="your_api_key_here"
  python3 fetchEvents.py

The script will save to LanceDB (~/.luma-event-aggregation/data/events.db):
- Table 'events' (all events sorted by start_at)
- Table 'city_summary' (city counts with detailed distance/time data from Google Maps)

Distance/time data includes:
- Text format (e.g., "15.2 miles", "23 minutes")
- Numeric values (meters, miles, seconds, minutes)
- Status information for each city lookup
"""

import asyncio
import aiohttp
import json
import os
import math
import uuid
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests
import googlemaps
from dotenv import load_dotenv
import lancedb

# Load environment variables from .env file
load_dotenv()


def detect_user_location():
    """Detect user's location from IP address using ipinfo.io"""
    try:
        print("Detecting your location from IP...")
        ipinfo = requests.get("https://ipinfo.io").json()
        loc = ipinfo.get("loc")
        city = ipinfo.get("city")
        region = ipinfo.get("region")
        country = ipinfo.get("country")
        
        if city and region:
            location_string = f"{city}, {region}, {country}"
        elif city:
            location_string = f"{city}, {country}"
        else:
            location_string = f"{country}"
            
        print(f"📍 Detected location: {location_string}")
        print(f"🗺️  Coordinates: {loc}")
        
        return location_string
        
    except Exception as e:
        print(f"❌ Error detecting location: {e}")
        print("Using fallback location: None")
        return None

async def fetch_all_luma_events_bounding_box(session, east, north, south, west, slug,
                                               base_url="https://api2.luma.com/discover/get-paginated-events",
                                               pagination_limit=100):
    """
    Fetch all events for a given slug and bounding box using async requests.
    """
    all_events = []
    has_more = True
    current_cursor = None

    print(f"[{slug}] Starting to fetch events within bounding box:")
    print(f"[{slug}]   North: {north}, South: {south}, East: {east}, West: {west}")

    while has_more:
        params = {
            "east": east,
            "north": north,
            "south": south,
            "west": west,
            "pagination_limit": pagination_limit,
            "slug": slug
        }
        if current_cursor:
            params["pagination_cursor"] = current_cursor

        try:
            async with session.get(base_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # Add events from the current page to our list
                current_page_entries = data.get("entries", [])
                all_events.extend(current_page_entries)

                # Update pagination info
                has_more = data.get("has_more", False)
                current_cursor = data.get("next_cursor")

                print(f"[{slug}] Fetched {len(current_page_entries)} events. Total: {len(all_events)}. Has more: {has_more}")
                if current_cursor:
                    print(f"[{slug}]   Next cursor: {current_cursor}")

                if has_more:
                    # Small delay to be polite to the API
                    await asyncio.sleep(0.2)

        except aiohttp.ClientError as e:
            print(f"[{slug}] HTTP error occurred: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"[{slug}] Error decoding JSON response: {e}")
            break
        except Exception as e:
            print(f"[{slug}] An unexpected error occurred: {e}")
            break

    print(f"[{slug}] Finished fetching. Total events collected: {len(all_events)}")
    return slug, all_events


async def fetch_all_luma_events_calendar_api(session, east, north, south, west, calendar_api_id, calendar_name,
                                               base_url="https://api2.luma.com/calendar/get-items",
                                               pagination_limit=100):
    """
    Fetch all events for a given calendar_api_id and bounding box using async requests.
    """
    all_events = []
    has_more = True
    current_cursor = None

    print(f"[{calendar_name}] Starting to fetch events within bounding box:")
    print(f"[{calendar_name}]   North: {north}, South: {south}, East: {east}, West: {west}")

    while has_more:
        params = {
            "calendar_api_id": calendar_api_id,
            "east": east,
            "north": north,
            "south": south,
            "west": west,
            "location_required": "true",
            "period": "future",
            "pagination_limit": pagination_limit,
        }
        if current_cursor:
            params["pagination_cursor"] = current_cursor

        try:
            async with session.get(base_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # Add events from the current page to our list
                current_page_entries = data.get("entries", [])
                all_events.extend(current_page_entries)

                # Update pagination info
                has_more = data.get("has_more", False)
                current_cursor = data.get("next_cursor")

                print(f"[{calendar_name}] Fetched {len(current_page_entries)} events. Total: {len(all_events)}. Has more: {has_more}")
                if current_cursor:
                    print(f"[{calendar_name}]   Next cursor: {current_cursor}")

                if has_more:
                    # Small delay to be polite to the API
                    await asyncio.sleep(0.2)

        except aiohttp.ClientError as e:
            print(f"[{calendar_name}] HTTP error occurred: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"[{calendar_name}] Error decoding JSON response: {e}")
            break
        except Exception as e:
            print(f"[{calendar_name}] An unexpected error occurred: {e}")
            break

    print(f"[{calendar_name}] Finished fetching. Total events collected: {len(all_events)}")
    return calendar_name, all_events


def get_start_at(item):
    """Extract start_at datetime from event item."""
    s = item.get("start_at") or item.get("event", {}).get("start_at")
    if not s:
        return None
    try:
        # handle ISO with 'Z'
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            return None


def get_event_api_id(event):
    """Extract api_id from an event, prioritizing the nested event.api_id.
    
    Args:
        event: Event item
        
    Returns:
        The api_id string, or None if not found
    """
    # Try nested event.api_id first (this is the unique event identifier)
    api_id = event.get("event", {}).get("api_id")
    if api_id:
        return api_id
    
    # Fallback to top-level api_id
    api_id = event.get("api_id")
    if api_id:
        return api_id
    
    return None


def get_event_url(event):
    """Extract url from an event, prioritizing the nested event.url.
    
    Args:
        event: Event item
        
    Returns:
        The url string, or None if not found
    """
    # Try nested event.url first
    url = event.get("event", {}).get("url")
    if url:
        return url
    
    # Fallback to top-level url
    url = event.get("url")
    if url:
        return url
    
    return None


def deduplicate_events(events):
    """Remove duplicate events based on event.api_id (the unique event identifier).
    
    Args:
        events: List of event items
        
    Returns:
        List of deduplicated events, keeping the first occurrence of each event.api_id
    """
    seen_api_ids = set()
    deduplicated = []
    duplicates_count = 0
    duplicates_list = []
    
    for event in events:
        # Use the nested event.api_id as the unique identifier
        api_id = get_event_api_id(event)
        
        if api_id:
            if api_id not in seen_api_ids:
                seen_api_ids.add(api_id)
                deduplicated.append(event)
            else:
                duplicates_count += 1
                event_name = event.get("event", {}).get("name") or event.get("name", "Unknown")
                duplicates_list.append(f"  - {api_id}: {event_name}")
        else:
            # Events without api_id are kept (shouldn't happen, but safety measure)
            deduplicated.append(event)
    
    if duplicates_count > 0:
        print(f"🔍 Removed {duplicates_count} duplicate events based on event.api_id:")
        for dup in duplicates_list[:10]:  # Show first 10 duplicates
            print(dup)
        if duplicates_count > 10:
            print(f"  ... and {duplicates_count - 10} more")
    else:
        print(f"✓ No duplicate events found")
    
    return deduplicated


def get_event_coordinates(event_data):
    """
    Tries to find coordinates in 3 different places.
    Returns (lat, lon) or (None, None).
    """
    lat, lon = None, None

    # Check 1: The 'coordinate' object directly on the event (First JSON example)
    # This is usually the most accurate for Luma events
    if event_data.get('event') and event_data['event'].get('coordinate'):
        coord = event_data['event']['coordinate']
        lat = coord.get('latitude')
        lon = coord.get('longitude')

    # Check 2: The 'location' object (Second JSON example / Schema.org style)
    if lat is None and event_data.get('location'):
        loc = event_data['location']
        
        # Sometimes it's directly in location
        lat = loc.get('latitude')
        lon = loc.get('longitude')
        
        # Sometimes it's nested in 'geo'
        if lat is None and loc.get('geo'):
            lat = loc['geo'].get('latitude')
            lon = loc['geo'].get('longitude')

    # Check 3: Fallback to Geo Address Info (if available in API response)
    if lat is None and event_data.get('event', {}).get('geo_address_info'):
        geo = event_data['event']['geo_address_info']
        lat = geo.get('latitude')
        lon = geo.get('longitude')

    return lat, lon


def extract_city(item, gmaps_client=None):
    """Extract city name, preferring city_state format for better Google Maps accuracy.
    
    Args:
        item: Event item to extract city from
        gmaps_client: Optional Google Maps client for reverse geocoding
        
    Returns:
        City string in "City, State" format, or "Unknown" if not found
    """
    ev = item.get("event", {})
    geo = ev.get("geo_address_info", {}) if isinstance(ev.get("geo_address_info", {}), dict) else {}
    
    vague_cities = ["California", "United States", "USA", "Register to See Address"]

    # PREFER city_state like "San Francisco, California" for better Google Maps accuracy
    city_state = geo.get("city_state")
    if city_state and city_state not in vague_cities:
        return city_state

    # Fallback to calendar geo_city with state if available
    cal_city = item.get("calendar", {}).get("geo_city")
    cal_region = item.get("calendar", {}).get("geo_region_abbrev") or item.get("calendar", {}).get("geo_region")
    if cal_city and cal_city not in vague_cities:
        if cal_region:
            return f"{cal_city}, {cal_region}"
        return cal_city

    # Fallback to explicit city field (but this lacks state info)
    city = geo.get("city")
    if city and city not in vague_cities:
        # Try to add state if available
        state = geo.get("region") or geo.get("region_abbrev")
        if state:
            return f"{city}, {state}"
        return city

    # Last resort: Use reverse geocoding if coordinates are available
    if gmaps_client:
        lat, lng = get_event_coordinates(item)
        
        if lat is not None and lng is not None:
            try:
                result = gmaps_client.reverse_geocode((lat, lng))
                if result:
                    # Extract city and state from address components
                    city_name = None
                    state_name = None
                    
                    for component in result[0].get("address_components", []):
                        types = component.get("types", [])
                        if "locality" in types:
                            city_name = component.get("long_name")
                        elif "administrative_area_level_1" in types:
                            state_name = component.get("long_name")
                    
                    if city_name and state_name:
                        return f"{city_name}, {state_name}"
                    elif city_name:
                        return city_name
            except Exception as e:
                print(f"    ⚠️  Reverse geocoding failed for coordinates ({lat}, {lng}): {e}")
    
    # If we still have a vague city name, return it as a last resort
    if city:
        return city
    if city_state:
        return city_state
    if cal_city:
        return cal_city

    return "Unknown"


def get_distance_and_time_from_user_location(origin, destination, gmaps_client):
    """Get distance and estimated driving time between two locations with detailed metrics."""
    try:
        # Use Google Maps Distance Matrix API with current time for more accurate estimates
        result = gmaps_client.distance_matrix(
            origins=[origin],
            destinations=[destination],
            mode="driving",
            departure_time=datetime.now()
        )
        
        if result["status"] == "OK":
            element = result["rows"][0]["elements"][0]
            status = element.get("status")
            
            if status == "OK":
                distance_text = element["distance"]["text"]
                duration_text = element["duration"]["text"]
                distance_value = element["distance"]["value"]  # meters
                duration_value = element["duration"]["value"]  # seconds
                
                # Convert meters to miles
                distance_miles = None
                try:
                    distance_miles = round(distance_value / 1609.344, 2) if distance_value is not None else None
                except Exception:
                    distance_miles = None
                
                # Convert seconds to minutes
                duration_minutes = None
                try:
                    duration_minutes = round(duration_value / 60, 1) if duration_value is not None else None
                except Exception:
                    duration_minutes = None
                
                return {
                    "status": status,
                    "distance_text": distance_text,
                    "distance_meters": distance_value,
                    "distance_miles": distance_miles,
                    "duration_text": duration_text,
                    "duration_seconds": duration_value,
                    "duration_minutes": duration_minutes,
                }
            else:
                return {
                    "status": status,
                    "distance_text": None,
                    "distance_meters": None,
                    "distance_miles": None,
                    "duration_text": None,
                    "duration_seconds": None,
                    "duration_minutes": None,
                }
                
    except Exception as e:
        print(f"Error getting distance/time for {destination}: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "distance_text": None,
            "distance_meters": None,
            "distance_miles": None,
            "duration_text": None,
            "duration_seconds": None,
            "duration_minutes": None,
        }
    
    return None


def normalize_city_data(event):
    """Normalize city data by extracting city and state from city_state if needed.
    
    Args:
        event: Event item to normalize
        
    Returns:
        The event with normalized geo_address_info (city and state fields populated)
    """
    ev = event.get("event", {})
    geo = ev.get("geo_address_info", {}) if isinstance(ev.get("geo_address_info", {}), dict) else {}
    
    # If city field is missing but city_state is present, extract it
    if not geo.get("city") and geo.get("city_state"):
        city_state = geo.get("city_state", "")
        if "," in city_state:
            parts = city_state.split(",", 1)
            geo["city"] = parts[0].strip()
            # Only set state if not already present
            if not geo.get("region") and len(parts) > 1:
                geo["region"] = parts[1].strip()
            
            # Update the event with normalized data
            if isinstance(ev.get("geo_address_info"), dict):
                ev["geo_address_info"] = geo
    
    return event


def enrich_event_with_city(event, gmaps_client):
    """Enrich an event with city data using reverse geocoding if needed.
    
    Args:
        event: Event item to enrich
        gmaps_client: Google Maps client for reverse geocoding
        
    Returns:
        The event with potentially enriched geo_address_info
    """
    # First normalize existing city_state data
    event = normalize_city_data(event)
    
    ev = event.get("event", {})
    geo = ev.get("geo_address_info", {}) if isinstance(ev.get("geo_address_info", {}), dict) else {}
    
    # Check if city data is already present
    # We consider "California", "United States", "USA" as vague/invalid and try to improve it
    current_city = geo.get("city")
    current_city_state = geo.get("city_state")
    cal_city = event.get("calendar", {}).get("geo_city")
    vague_cities = ["California", "United States", "USA", "Register to See Address"]
    
    has_valid_city_data = (
        (current_city_state and not any(v in current_city_state for v in vague_cities if v == current_city_state)) or 
        (current_city and current_city not in vague_cities) or 
        (cal_city and cal_city not in vague_cities)
    )
    
    # If no city data OR it's vague, try to add it via reverse geocoding
    if not has_valid_city_data and gmaps_client:
        lat, lng = get_event_coordinates(event)
        
        if lat is not None and lng is not None:
            try:
                result = gmaps_client.reverse_geocode((lat, lng))
                if result:
                    # Extract city and state from address components
                    city_name = None
                    state_name = None
                    country_name = None
                    
                    for component in result[0].get("address_components", []):
                        types = component.get("types", [])
                        if "locality" in types:
                            city_name = component.get("long_name")
                        elif "administrative_area_level_1" in types:
                            state_name = component.get("long_name")
                        elif "country" in types:
                            country_name = component.get("long_name")
                    
                    # Enrich the geo_address_info with the geocoded data
                    if city_name:
                        geo["city"] = city_name
                        if state_name:
                            geo["region"] = state_name
                            geo["city_state"] = f"{city_name}, {state_name}"
                        if country_name:
                            geo["country"] = country_name
                        
                        # Update the event with enriched data
                        if isinstance(ev.get("geo_address_info"), dict):
                            ev["geo_address_info"] = geo
                        
                        return event, True  # Return event and enrichment flag
                        
            except Exception as e:
                # Silent fail - just return original event
                pass
    
    return event, False  # Return event and no enrichment flag


def generate_city_summary(events, user_location):
    """Generate summary of events by city with distance/time info from Google Maps API.
    
    Args:
        events: List of events to summarize
        user_location: User's location string (required for distance calculations)
        
    Raises:
        ValueError: If Google Maps API key is not configured or user_location is not provided
    """
    print("Generating city summary...")
    
    # Validate that user_location is provided
    if not user_location:
        raise ValueError("user_location is required for city summary generation")
    
    # Set up Google Maps client - this is now REQUIRED
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not google_maps_api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY environment variable is required for city summary generation")
    
    try:
        gmaps_client = googlemaps.Client(key=google_maps_api_key)
        print("Google Maps API key found - will use for distance/time calculations and reverse geocoding")
    except Exception as e:
        raise ValueError(f"Error setting up Google Maps client: {e}")
    
    # Count events by city, using reverse geocoding for missing locations
    print("📍 Extracting cities from events (using reverse geocoding when needed)...")
    city_counter = Counter()
    for event in events:
        city = extract_city(event, gmaps_client)
        city_counter[city] += 1
    
    summary = {}
    cities = list(city_counter.keys())
    
    print(f"📊 Processing {len(cities)} cities for distance/time calculations...")
    
    for i, city in enumerate(cities, 1):
        city_info = {"event_count": city_counter[city]}
        
        print(f"  [{i}/{len(cities)}] Querying: {city}", end="")
        
        # Always add distance/time info for valid cities
        if city != "Unknown":
            distance_data = get_distance_and_time_from_user_location(
                user_location, city, gmaps_client
            )
            
            if distance_data and distance_data.get("status") == "OK":
                city_info.update(distance_data)
                miles = distance_data.get("distance_miles", "N/A")
                minutes = distance_data.get("duration_minutes", "N/A")
                print(f" ✓ {miles} mi, {minutes} min")
            else:
                city_info.update({
                    "status": distance_data.get("status", "ERROR") if distance_data else "ERROR",
                    "distance_text": "Unable to calculate",
                    "distance_meters": None,
                    "distance_miles": None,
                    "duration_text": "Unable to calculate", 
                    "duration_seconds": None,
                    "duration_minutes": None,
                })
                if distance_data and distance_data.get("error"):
                    city_info["error"] = distance_data["error"]
                    print(f" ✗ Error: {distance_data['error']}")
                else:
                    status = distance_data.get("status", "UNKNOWN") if distance_data else "UNKNOWN"
                    print(f" ✗ Status: {status}")
        else:
            city_info.update({
                "status": "INVALID_LOCATION",
                "distance_text": "N/A - Unknown location",
                "distance_meters": None,
                "distance_miles": None,
                "duration_text": "N/A - Unknown location",
                "duration_seconds": None,
                "duration_minutes": None,
            })
            print(" ⚠️  Unknown location - skipping")
        
        summary[city] = city_info
    
    print(f"✅ Completed distance/time calculations for all cities")
    return summary


async def fetch_and_aggregate_events(slugs, calendar_configs, east, north, south, west, 
                                   user_location):
    """
    Fetch events for multiple slugs and calendar APIs concurrently and save to LanceDB.
    
    Args:
        slugs: List of Luma calendar slugs to fetch from
        calendar_configs: List of dicts with 'calendar_api_id' and 'name' keys for calendar API endpoints
        east, north, south, west: Bounding box coordinates  
        user_location: User's location string (required for Google Maps distance calculations)
        
    Raises:
        ValueError: If user_location is not provided or Google Maps API is not configured
    """
    if not user_location:
        raise ValueError("user_location is required for generating city summary with distance/time data")
    
    # Initialize LanceDB in home directory
    home_dir = os.path.expanduser("~")
    db_dir = os.path.join(home_dir, ".luma-event-aggregation", "data")
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    db_path = os.path.join(db_dir, "events.db")
    db = lancedb.connect(db_path)
    print(f"🗄️  Connected to LanceDB at {db_path}")

    # Create a single aiohttp session for all requests
    async with aiohttp.ClientSession() as session:
        # Create tasks for all slugs
        tasks = [
            fetch_all_luma_events_bounding_box(session, east, north, south, west, slug)
            for slug in slugs
        ]
        
        # Create tasks for all calendar API endpoints
        tasks.extend([
            fetch_all_luma_events_calendar_api(
                session, east, north, south, west, 
                config['calendar_api_id'], 
                config['name']
            )
            for config in calendar_configs
        ])

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # Combine all events from all sources
        all_events = []
        for source_name, events in results:
            print(f"\n[{source_name}] Collected {len(events)} events")
            all_events.extend(events)

        print(f"\n✓ Total events collected from all sources: {len(all_events)}")
        
        # Remove duplicate events based on api_id
        print("🔄 Removing duplicate events...")
        deduplicated_events = deduplicate_events(all_events)
        removed_count = len(all_events) - len(deduplicated_events)
        all_events = deduplicated_events
        print(f"✓ Total unique events after deduplication: {len(all_events)} (removed {removed_count})")

        # Enrich events with city data using reverse geocoding where needed
        print("🔍 Enriching events with city data via reverse geocoding...")
        google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if google_maps_api_key:
            try:
                gmaps_client = googlemaps.Client(key=google_maps_api_key)
                enriched_count = 0
                
                for i, event in enumerate(all_events):
                    enriched_event, was_enriched = enrich_event_with_city(event, gmaps_client)
                    all_events[i] = enriched_event
                    if was_enriched:
                        enriched_count += 1
                
                if enriched_count > 0:
                    print(f"✓ Enriched {enriched_count} events with reverse-geocoded city data")
                else:
                    print(f"✓ All events already have city data")
            except Exception as e:
                print(f"⚠️  Could not enrich events: {e}")
        else:
            print("⚠️  Skipping event enrichment (no Google Maps API key)")

        # Load existing events to preserve them and avoid duplicates
        existing_events = []
        existing_urls = set()
        
        if "events" in db.table_names():
            try:
                tbl = db.open_table("events")
                # Load all existing events
                existing_events = tbl.to_pandas().to_dict(orient='records')
                
                # Clean NaNs from existing events (Pandas introduces NaNs)
                def clean_nans(obj):
                    if isinstance(obj, float) and math.isnan(obj):
                        return None
                    elif isinstance(obj, dict):
                        return {k: clean_nans(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [clean_nans(v) for v in obj]
                    return obj
                
                existing_events = [clean_nans(e) for e in existing_events]
                
                # Build set of existing URLs
                for event in existing_events:
                    url = get_event_url(event)
                    if url:
                        existing_urls.add(url)
                        
                print(f"✓ Loaded {len(existing_events)} existing events from DB")
            except Exception as e:
                print(f"⚠️ Could not read existing data: {e}")

        # Filter fetched events to only include those not in DB
        new_events = []
        skipped_count = 0
        
        for event in all_events:
            url = get_event_url(event)
            if url and url in existing_urls:
                skipped_count += 1
                continue
            new_events.append(event)
            
        print(f"✓ Found {len(new_events)} new events (skipped {skipped_count} existing)")

        # Initialize fields for NEW events only
        print("📝 Initializing fields for new events...")
        for event in new_events:
            # Initialize classification fields if not present
            if 'event_type' not in event:
                event['event_type'] = None
            if 'audience' not in event:
                event['audience'] = None
            
            # Initialize bookmark
            event['bookmarked'] = False
            
            # Generate new UUID
            event['id'] = str(uuid.uuid4())

        # Combine existing and new events
        final_events = existing_events + new_events
        
        # Sort events by start_at
        def sort_key(item):
            dt = get_start_at(item)
            return dt if dt else datetime.min.replace(tzinfo=dt.tzinfo if dt else None)
            
        sorted_events = sorted(final_events, key=sort_key)
        print(f"✓ Total events to save: {len(sorted_events)} (sorted by start time)")

        # Save to LanceDB
        print("💾 Saving events to LanceDB...")
        try:
            if "events" in db.table_names():
                print("  Overwriting existing 'events' table with updated list...")
                db.drop_table("events")
            
            db.create_table("events", data=sorted_events)
            print(f"✓ Saved {len(sorted_events)} events to LanceDB table 'events'")
        except Exception as e:
            print(f"❌ Error saving to LanceDB: {e}")
            raise

        # Generate and save city summary to LanceDB as well
        city_summary = generate_city_summary(sorted_events, user_location)
        
        # Convert city summary to table format for LanceDB
        city_summary_data = [
            {"city": city, **details}
            for city, details in city_summary.items()
        ]
        
        if "city_summary" in db.table_names():
            db.drop_table("city_summary")
        
        db.create_table("city_summary", data=city_summary_data)
        print(f"✓ Saved city summary to LanceDB table 'city_summary'")

    print(f"\n✓ All processing completed successfully!")
    return len(sorted_events)


async def main():
    """Main function to fetch and aggregate events."""
    # Bounding box coordinates (San Francisco Bay Area)
    east_coord = -121.57055455494474
    north_coord = 37.96737772066783
    south_coord = 36.71845574708184
    west_coord = -122.7412517581312

    # Slugs to fetch (using discover API)
    slugs = [
        "tech",
        "ai",
        "sf"
    ]
    
    # Calendar API configs (using calendar/get-items API)
    calendar_configs = [
        {
            "calendar_api_id": "cal-KtLaZ6kCBmxDuxH",
            "name": "foundersocialclub"
        },
        {
            "calendar_api_id": "cal-JTdFQadEz0AOxyV",
            "name": "genai-sf"
        },
        {
            "calendar_api_id": "cal-S7gDcd9Akzu62RD",
            "name": "sf-developer-events"
        },
        {
            "calendar_api_id": "cal-woPJeSUOpqqFp6f",
            "name": "svgenai"
        },
        {
            "calendar_api_id": "cal-E74MDlDKBaeAwXK",
            "name": "genai-collective"
        },
        {
            "calendar_api_id": "cal-Sl7q1nHTRXQzjP2",
            "name": "Frontier Tower"
        },
        {
            "calendar_api_id": "cal-MvY3wcADGCzQG99",
            "name": "Beta-events"
        },
        {
            "calendar_api_id": "cal-sjbD5arlvEXNV14",
            "name": "Founders Creative"
        },
        {
            "calendar_api_id": "cal-sQ96963Pp5vVxZl",
            "name": "pnpsv"
        }
    ]

    # Validate required environment variable
    if not os.getenv("GOOGLE_MAPS_API_KEY"):
        print("❌ ERROR: GOOGLE_MAPS_API_KEY environment variable is required!")
        print("Please set it with: export GOOGLE_MAPS_API_KEY='your_api_key_here'")
        return

    # Automatically detect user location from IP
    user_location = detect_user_location()
    
    if not user_location:
        print("❌ ERROR: Could not detect user location!")
        print("Unable to generate city summary without location data.")
        return
    
    print("\n=== Starting concurrent fetch and aggregation for multiple sources ===")
    print(f"📍 Using detected location: {user_location}")
    print(f"📊 Fetching from {len(slugs)} slug-based calendars and {len(calendar_configs)} calendar APIs")
    print("🗺️  Google Maps API will be used for all distance/time calculations\n")
    
    try:
        total_events = await fetch_and_aggregate_events(
            slugs, calendar_configs, east_coord, north_coord, south_coord, west_coord,
            user_location
        )
        
        print(f"\n🎉 Successfully processed {total_events} total events!")
        print("📁 Data saved to LanceDB (~/.luma-event-aggregation/data/events.db):")
        print("   - Table 'events'")
        print("   - Table 'city_summary'")
        print("\n💡 Use filterEvents.py to filter the combined events by location, date, or weekday")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Please ensure:")
        print("1. GOOGLE_MAPS_API_KEY environment variable is set")
        print("2. user_location is properly configured in the script")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())