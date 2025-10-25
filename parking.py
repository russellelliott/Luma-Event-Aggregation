# Event Parking Finder with Google Maps Grounding
# This script scrapes Luma event data and finds nearby parking using Gemini with Maps grounding

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import googlemaps

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# PART 1: LUMA EVENT SCRAPER
# ============================================================================

def scrape_luma_event(url):
    """
    Scrape JSON-LD structured data from Luma event page.
    
    Args:
        url (str): The Luma event page URL
    
    Returns:
        dict: Event information from JSON-LD structured data
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"📡 Fetching event page: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        if not json_ld_scripts:
            return {'error': 'No JSON-LD structured data found'}
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Event':
                    print("✓ Found Event schema")
                    return {'event_data': data}
            except (json.JSONDecodeError, TypeError):
                continue
        
        return {'error': 'No Event schema found'}
        
    except Exception as e:
        return {'error': f'Failed to fetch page: {str(e)}'}


def extract_event_info(scraped_data):
    """
    Extract key event details including coordinates and timing.
    
    Args:
        scraped_data (dict): Result from scrape_luma_event
    
    Returns:
        dict: Formatted event details with coordinates
    """
    if 'error' in scraped_data or 'event_data' not in scraped_data:
        return scraped_data
    
    event = scraped_data['event_data']
    
    details = {
        'name': event.get('name'),
        'description': event.get('description'),
        'start_date': event.get('startDate'),
        'end_date': event.get('endDate'),
        'url': event.get('@id') or event.get('url'),
    }
    
    # Extract location and coordinates
    if 'location' in event:
        loc = event['location']
        details['location'] = {
            'name': loc.get('name'),
            'address': loc.get('address'),
        }
        
        # Get coordinates (priority: direct fields, then geo object)
        geo = loc.get('geo', {})
        details['latitude'] = loc.get('latitude') or geo.get('latitude')
        details['longitude'] = loc.get('longitude') or geo.get('longitude')
    
    return details


# ============================================================================
# PART 2: PARKING FINDER WITH GOOGLE MAPS GROUNDING
# ============================================================================

def get_venue_address(event_details, maps_api_key):
    """
    Get venue address from event data or perform reverse geocoding.
    
    Args:
        event_details (dict): Event information with coordinates
        maps_api_key (str): Google Maps API key
    
    Returns:
        str: Venue address
    """
    # Check if address is already available and not a placeholder
    address = event_details.get('location', {}).get('address', '')
    if address and address != "Register to See Address" and address.strip():
        return address
    
    # Perform reverse geocoding
    if 'latitude' not in event_details or 'longitude' not in event_details:
        return "Unknown venue"
    
    try:
        gmaps = googlemaps.Client(key=maps_api_key)
        lat = event_details['latitude']
        lon = event_details['longitude']
        
        reverse_geocode_result = gmaps.reverse_geocode((lat, lon))
        
        if reverse_geocode_result:
            return reverse_geocode_result[0]['formatted_address']
    except Exception as e:
        print(f"⚠️  Reverse geocoding failed: {str(e)}")
    
    return "Unknown venue"


def calculate_distances(venue_address, parking_options, maps_api_key):
    """
    Calculate distances between venue and each parking option using Google Maps Distance Matrix API.
    
    Args:
        venue_address (str): Address of the event venue
        parking_options (list): List of parking options with addresses
        maps_api_key (str): Google Maps API key
    
    Returns:
        list: Parking options with distance_miles added
    """
    if not parking_options or not venue_address or venue_address == "Unknown venue":
        return parking_options
    
    try:
        gmaps = googlemaps.Client(key=maps_api_key)
        
        # Extract parking addresses
        destinations = [option.get('address', '') for option in parking_options if option.get('address')]
        
        if not destinations:
            return parking_options
        
        print(f"📍 Calculating distances from: {venue_address}")
        
        # Calculate distances
        distance_matrix = gmaps.distance_matrix(
            origins=venue_address,
            destinations=destinations,
            mode='walking',
            units='imperial'
        )
        
        # Add distances to parking options
        if distance_matrix['status'] == 'OK':
            for i, option in enumerate(parking_options):
                if i < len(distance_matrix['rows'][0]['elements']):
                    element = distance_matrix['rows'][0]['elements'][i]
                    if element['status'] == 'OK':
                        distance_m = element['distance']['value']
                        distance_miles = distance_m * 0.000621371  # Convert meters to miles
                        option['distance_miles'] = round(distance_miles, 2)
                        print(f"✓ {option.get('name', 'Parking')}: {option['distance_miles']} miles")
                    else:
                        print(f"⚠️  Could not calculate distance for {option.get('name', 'Parking')}: {element['status']}")
                        option['distance_miles'] = None
        else:
            print(f"⚠️  Distance Matrix API error: {distance_matrix['status']}")
    except Exception as e:
        print(f"⚠️  Could not calculate distances: {str(e)}")
    
    return parking_options


def parse_event_datetime(datetime_str):
    """
    Parse ISO 8601 datetime string to datetime object.
    
    Args:
        datetime_str (str): ISO 8601 formatted datetime
    
    Returns:
        datetime: Parsed datetime object
    """
    try:
        # Handle timezone offset (e.g., -07:00)
        if datetime_str:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except:
        pass
    return None


def find_parking_near_event(event_details, gemini_api_key, maps_api_key):
    """
    Use Google Maps grounding to find parking near event location.
    
    Args:
        event_details (dict): Event information with coordinates
        gemini_api_key (str): Gemini API key
        maps_api_key (str): Google Maps API key
    
    Returns:
        dict: Parking recommendations with details
    """
    if 'latitude' not in event_details or 'longitude' not in event_details:
        return {'error': 'Event coordinates not found'}
    
    lat = event_details['latitude']
    lon = event_details['longitude']
    
    # Get venue address
    venue_address = get_venue_address(event_details, maps_api_key)
    
    # Build a detailed prompt for parking search using coordinates
    prompt = f"""Find 3-5 parking options near {venue_address} (coordinates: {lat}, {lon}) that meet these criteria:
1. Must be within 0.5 miles (10 min walk)
2. Include pricing information when available
3. Mix of parking types: garages, lots, and street parking if available

For each option, provide:
- Name and address
- Operating hours
- Pricing (hourly, daily, evening rates)
- Type (garage, lot, street)
- Any special notes (validation, restrictions, etc.)

Return the results as a JSON array with objects containing these fields: name, address, hours, pricing, type, notes."""
    
    # Configure Maps grounding with event location
    location_config = types.ToolConfig(
        retrieval_config=types.RetrievalConfig(
            lat_lng=types.LatLng(
                latitude=lat,
                longitude=lon,
            ),
            language_code='en_US',
        )
    )
    
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_maps=types.GoogleMaps())],
        tool_config=location_config
    )
    
    # Initialize client with Gemini API key (Maps API key is handled via credentials)
    client = genai.Client(api_key=gemini_api_key)
    
    try:
        print(f"\n🗺️  Searching for parking near {venue_address}...")
        print(f"📍 Coordinates: ({lat}, {lon})")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        
        # Parse the response as JSON
        parking_data = []
        try:
            # Extract JSON from response text
            response_text = response.text
            # Find JSON array in response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parking_data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  Could not parse response as JSON: {str(e)}")
            parking_data = []
        
        # Calculate distances for each parking option
        parking_data = calculate_distances(venue_address, parking_data, maps_api_key)
        
        return {
            'parking_recommendations': parking_data,
            'venue_address': venue_address,
            'event_coordinates': {'latitude': lat, 'longitude': lon},
            'grounding_used': bool(response.candidates[0].grounding_metadata) if response.candidates else False,
            'raw_response': response.text
        }
        
    except Exception as e:
        return {'error': f'Maps API error: {str(e)}'}


# ============================================================================
# PART 3: MAIN EXECUTION FLOW
# ============================================================================

def find_event_parking(luma_url):
    """
    Complete workflow: scrape event, extract coordinates, find parking.
    
    Args:
        luma_url (str): URL of Luma event page
    
    Returns:
        dict: Complete results with event info and parking recommendations
    """
    print("="*70)
    print("EVENT PARKING FINDER")
    print("="*70)
    
    # Step 1: Scrape event data
    scraped_data = scrape_luma_event(luma_url)
    if 'error' in scraped_data:
        return scraped_data
    
    # Step 2: Extract event details
    event_details = extract_event_info(scraped_data)
    if 'error' in event_details:
        return event_details
    
    print(f"\n📅 Event: {event_details['name']}")
    print(f"📍 Location: {event_details.get('location', {}).get('name')}")
    print(f"📌 Coordinates: ({event_details.get('latitude')}, {event_details.get('longitude')})")
    print(f"🕐 Start: {event_details.get('start_date')}")
    print(f"🕐 End: {event_details.get('end_date')}")
    
    # Step 3: Get API keys from environment
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not gemini_api_key:
        return {'error': 'GOOGLE_API_KEY not found in .env file'}
    if not maps_api_key:
        return {'error': 'GOOGLE_MAPS_API_KEY not found in .env file'}
    
    # Step 4: Find parking
    parking_results = find_parking_near_event(event_details, gemini_api_key, maps_api_key)
    
    if 'error' in parking_results:
        return {'event_details': event_details, 'error': parking_results['error']}
    
    # Display results
    print("\n" + "="*70)
    print("🅿️  PARKING RECOMMENDATIONS")
    print("="*70)
    
    if parking_results.get('parking_recommendations'):
        print(json.dumps(parking_results['parking_recommendations'], indent=2))
    else:
        print(parking_results.get('raw_response', 'No parking recommendations found'))
    
    if parking_results.get('grounding_used'):
        print("\n✓ Results grounded with Google Maps data")
    
    return {
        'event_details': event_details,
        'parking_results': parking_results
    }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Example: TechCrunch event from the provided document
    event_url = 'https://luma.com/l5vbx903'
    
    # Run the complete workflow
    results = find_event_parking(event_url)
    
    # Save results to JSON file (optional)
    if 'error' not in results:
        output_file = f'parking_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {output_file}")