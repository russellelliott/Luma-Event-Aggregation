import requests
from bs4 import BeautifulSoup
import json


def get_luma_event_info(slug):
    """
    Get event information from a Luma event slug.
    
    Args:
        slug (str): The Luma event slug (e.g., 'l5vbx903')
    
    Returns:
        dict: Event information including name, description, location, dates, and coordinates
              Returns {'error': message} if extraction fails
    
    Example:
        >>> info = get_luma_event_info('l5vbx903')
        >>> print(info['name'])
        >>> print(info['latitude'], info['longitude'])
    """
    url = f'https://lu.ma/{slug}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        if not json_ld_scripts:
            return {'error': 'No structured data found on page'}
        
        # Find Event schema in JSON-LD data
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Event':
                    event = data
                    
                    # Extract event details
                    info = {
                        'name': event.get('name'),
                        'description': event.get('description'),
                        'start_date': event.get('startDate'),
                        'end_date': event.get('endDate'),
                        'url': event.get('@id') or event.get('url'),
                    }
                    
                    # Extract location information
                    if 'location' in event:
                        loc = event['location']
                        info['location_name'] = loc.get('name')
                        info['address'] = loc.get('address')
                        
                        # Get coordinates (check both direct and geo object)
                        geo = loc.get('geo', {})
                        info['latitude'] = loc.get('latitude') or geo.get('latitude')
                        info['longitude'] = loc.get('longitude') or geo.get('longitude')
                    
                    # Extract pricing information
                    if 'offers' in event:
                        info['pricing'] = []
                        offers = event['offers'] if isinstance(event['offers'], list) else [event['offers']]
                        for offer in offers:
                            info['pricing'].append({
                                'name': offer.get('name'),
                                'price': offer.get('price'),
                                'currency': offer.get('priceCurrency'),
                                'availability': offer.get('availability'),
                                'url': offer.get('url')
                            })
                    
                    return info
                    
            except (json.JSONDecodeError, TypeError):
                continue
        
        return {'error': 'No Event schema found in page data'}
        
    except requests.RequestException as e:
        return {'error': f'Failed to fetch page: {str(e)}'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}


# Example usage
# Ticket only shows prices for general admission. Could use tools like Gemini for more specific pricing
# https://gemini.google.com/app/07952bc87b9d6fbf
if __name__ == '__main__':
    event_info = get_luma_event_info('GAP2025')
    
    if 'error' in event_info:
        print(f"Error: {event_info['error']}")
    else:
        print(f"Event: {event_info['name']}")
        print(f"Description: {event_info['description']}")
        print(f"Location: {event_info['location_name']}")
        print(f"Coordinates: ({event_info['latitude']}, {event_info['longitude']})")
        print(f"Start: {event_info['start_date']}")
        print(f"End: {event_info['end_date']}")
        if 'pricing' in event_info and event_info['pricing']:
            print("Pricing:")
            for option in event_info['pricing']:
                price_str = f"${option['price']}" if option['price'] else "Free"
                currency = option.get('currency', '')
                name = option.get('name', 'Ticket')
                print(f"  - {name}: {price_str} {currency}")