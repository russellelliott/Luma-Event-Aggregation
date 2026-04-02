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
import pyarrow as pa
from urllib.parse import urlparse
from normalize_event import normalize_luma_event

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
    s = item.get("start_at")
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
    canonical_url = canonicalize_event_url(get_event_url(event))
    return canonical_url or event.get("id")


def get_event_url(event):
    """Extract url from an event, prioritizing the nested event.url.
    
    Args:
        event: Event item
        
    Returns:
        The url string, or None if not found
    """
    if not isinstance(event, dict):
        return None

    nested_event = event.get("event") if isinstance(event.get("event"), dict) else {}
    return event.get("url") or nested_event.get("url")


def canonicalize_event_url(url):
    """Return a canonical URL string for stable deduping and DB matching."""
    if not url:
        return None

    text = str(url).strip()
    if not text:
        return None

    # Luma API often returns slug-only values (for example: "abc123").
    if not text.startswith("http"):
        text = f"https://luma.com/{text.lstrip('/')}"

    try:
        parsed = urlparse(text)
    except Exception:
        return text

    host = (parsed.netloc or "").lower()
    if host in {"lu.ma", "www.lu.ma", "luma.com", "www.luma.com"}:
        host = "luma.com"

    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")

    scheme = parsed.scheme or "https"
    canonical = f"{scheme}://{host}{path}"

    # Keep query/fragment only for non-Luma URLs.
    if host and host != "luma.com":
        if parsed.query:
            canonical += f"?{parsed.query}"
        if parsed.fragment:
            canonical += f"#{parsed.fragment}"

    return canonical


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
                event_name = event.get("name", "Unknown")
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
    coords = event_data.get("coordinates") if isinstance(event_data.get("coordinates"), dict) else {}
    coordinate = event_data.get("coordinate") if isinstance(event_data.get("coordinate"), dict) else {}
    location = event_data.get("location") if isinstance(event_data.get("location"), dict) else {}
    location_geo = location.get("geo") if isinstance(location.get("geo"), dict) else {}
    geo_address_info = event_data.get("geo_address_info") if isinstance(event_data.get("geo_address_info"), dict) else {}
    nested_event = event_data.get("event") if isinstance(event_data.get("event"), dict) else {}

    latitude = (
        coords.get("latitude")
        or coordinate.get("latitude")
        or location.get("latitude")
        or location_geo.get("latitude")
        or geo_address_info.get("latitude")
        or nested_event.get("latitude")
    )
    longitude = (
        coords.get("longitude")
        or coordinate.get("longitude")
        or location.get("longitude")
        or location_geo.get("longitude")
        or geo_address_info.get("longitude")
        or nested_event.get("longitude")
    )
    return latitude, longitude


def _extract_city_from_address(address):
    if not isinstance(address, dict):
        return None

    city = address.get("addressLocality") or address.get("locality") or address.get("city")
    region = address.get("addressRegion") or address.get("region") or address.get("state")

    if city and region:
        return f"{city}, {region}"
    if city:
        return city
    return None


def extract_city(item, gmaps_client=None):
    """Extract city name, preferring city_state format for better Google Maps accuracy.
    
    Args:
        item: Event item to extract city from
        gmaps_client: Optional Google Maps client for reverse geocoding
        
    Returns:
        City string in "City, State" format, or "Unknown" if not found
    """
    nested_event = item.get("event") if isinstance(item.get("event"), dict) else {}
    geo_address_info = item.get("geo_address_info") if isinstance(item.get("geo_address_info"), dict) else {}
    calendar = item.get("calendar") if isinstance(item.get("calendar"), dict) else {}
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    location_geo = location.get("geo") if isinstance(location.get("geo"), dict) else {}
    location_name = item.get("location_name") or nested_event.get("location_name")

    city = (
        item.get("city")
        or geo_address_info.get("city_state")
        or geo_address_info.get("city")
        or nested_event.get("city")
        or nested_event.get("city_state")
        or _extract_city_from_address(address)
        or _extract_city_from_address(location)
        or _extract_city_from_address(location_geo)
        or _extract_city_from_address(nested_event.get("address") if isinstance(nested_event.get("address"), dict) else {})
    )

    if not city and calendar.get("geo_city"):
        region = calendar.get("geo_region_abbrev") or calendar.get("geo_region")
        city = f"{calendar.get('geo_city')}, {region}" if region else calendar.get("geo_city")

    if not city and location_name and location_name not in {"Register to See Address", "Online"}:
        city = location_name
    
    vague_cities = ["California", "United States", "USA", "Register to See Address"]

    if city and city not in vague_cities:
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
    
    current_city = event.get("city")
    vague_cities = ["California", "United States", "USA", "Register to See Address"]
    has_valid_city_data = current_city and current_city not in vague_cities
    
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
                    
                    if city_name:
                        event["city"] = f"{city_name}, {state_name}" if state_name else city_name
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
    whitelist_lower = [c.lower() for c in whitelist]

    for i, city in enumerate(cities, 1):
        city_info = {"event_count": city_counter[city]}
        
        print(f"  [{i}/{len(cities)}] Querying: {city}", end="")
        
        # Skip unknown locations immediately
        if city == "Unknown":
            print(" ⚠️  Unknown location - skipping")
            continue

        distance_data = get_distance_and_time_from_user_location(
            user_location, city, gmaps_client
        )
        
        # Filter 1: Must have valid distance data (Status OK)
        if not distance_data or distance_data.get("status") != "OK":
            status = distance_data.get("status", "UNKNOWN") if distance_data else "UNKNOWN"
            error = distance_data.get("error") if distance_data else None
            if error:
                print(f" ✗ Skipping (Error: {error})")
            else:
                print(f" ✗ Skipping (Status: {status})")
            continue

        # Filter 2: Must be in California
        # We check for "California" or ", CA" in the city string, or if it's in our whitelist
        is_whitelisted = city.split(',')[0].strip().lower() in whitelist_lower
        
        if "California" not in city and ", CA" not in city and not is_whitelisted:
            print(f" ✗ Skipping (Not in California)")
            continue

        # If we get here, it's a valid California city
        city_info.update(distance_data)
        miles = distance_data.get("distance_miles", "N/A")
        minutes = distance_data.get("duration_minutes", "N/A")
        print(f" ✓ {miles} mi, {minutes} min")
        
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

    # Load existing events/URLs early so we can skip already-known events before
    # expensive processing (enrichment, filtering, summary generation).
    existing_events = []
    existing_urls = set()

    if "events" in db.list_tables():
        try:
            tbl = db.open_table("events")
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
            existing_events = [normalize_luma_event(e) for e in existing_events]

            for event in existing_events:
                canonical_url = canonicalize_event_url(get_event_url(event))
                if canonical_url:
                    existing_urls.add(canonical_url)

            print(f"✓ Loaded {len(existing_events)} existing events from DB")
            print(f"✓ Loaded {len(existing_urls)} canonical existing URLs")
        except Exception as e:
            print(f"⚠️ Could not read existing data: {e}")

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
        all_events = [normalize_luma_event(event) for event in all_events]

        # Skip events whose canonical URL is already present in DB.
        preexisting_skip_count = 0
        unseen_events = []

        for event in all_events:
            canonical_url = canonicalize_event_url(get_event_url(event))
            if canonical_url and canonical_url in existing_urls:
                preexisting_skip_count += 1
                continue
            unseen_events.append(event)

        all_events = unseen_events
        print(
            f"✓ Skipped {preexisting_skip_count} events already present in DB by URL "
            f"before processing"
        )
        
        # Remove duplicate events based on api_id
        print("🔄 Removing duplicate events...")
        deduplicated_events = deduplicate_events(all_events)
        removed_count = len(all_events) - len(deduplicated_events)
        all_events = deduplicated_events
        print(f"✓ Total unique events after deduplication: {len(all_events)} (removed {removed_count})")

        # Enrich events with city data using reverse geocoding where needed
        print("🔍 Enriching events with city data via reverse geocoding...")
        google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        gmaps_client = None
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

        # Filter out non-California events
        print("🔍 Filtering out non-California events...")
        
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
        whitelist_lower = [c.lower() for c in whitelist]

        def is_california_event(event):
            # Use extract_city to get the best city string
            city_str = extract_city(event, gmaps_client)
            if not city_str:
                return False # Skip if no city found
            
            if "California" in city_str or ", CA" in city_str:
                return True
            
            # Check whitelist
            # Extract just the city part if it has a comma (though extract_city tries to give "City, State")
            city_part = city_str.split(',')[0].strip()
            if city_part.lower() in whitelist_lower:
                return True
                
            return False

        filtered_events = []
        non_cal_count = 0
        for event in all_events:
            if is_california_event(event):
                filtered_events.append(event)
            else:
                non_cal_count += 1
        
        all_events = filtered_events
        if non_cal_count > 0:
            print(f"✓ Filtered out {non_cal_count} non-California events")
        else:
            print("✓ No non-California events found")

        # Filter fetched events to only include those not in DB
        # (a defensive second pass in case URL canonicalization changed later).
        new_events = []
        skipped_count = 0
        
        for event in all_events:
            canonical_url = canonicalize_event_url(get_event_url(event))
            if canonical_url and canonical_url in existing_urls:
                skipped_count += 1
                continue
            new_events.append(event)
            
        print(f"✓ Found {len(new_events)} new events (skipped {skipped_count} existing)")

        # Initialize fields for NEW events only
        print("📝 Initializing fields for new events...")

        for event in new_events:
            # Initialize bookmark
            event['bookmarked'] = False

            event.setdefault('topic_id', None)
            event.setdefault('topic_label', None)
            event.setdefault('topic_color', None)

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

        if city_summary_data:
            db.create_table("city_summary", data=city_summary_data)
            print(f"✓ Saved city summary to LanceDB table 'city_summary'")
        else:
            print("✓ No city summary rows to save")

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
        },
        {
            "calendar_api_id": "cal-sCNm2eqHymNd4aq",
            "name": "playful-sincerity-events"
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