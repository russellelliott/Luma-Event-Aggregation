from fastapi import FastAPI, Query
from typing import List, Optional
import json
import os
import math
from listCities import load_city_summary
from filterEvents import load_events, apply_filters, convert_to_serializable

app = FastAPI()

# Load data at startup
print("Loading data...")
try:
    CITY_SUMMARY_DF = load_city_summary()
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
        return clean_nans(convert_to_serializable(filtered_events))
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
