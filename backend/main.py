from fastapi import FastAPI, Query
from typing import List, Optional
import json
import os
from listCities import load_city_summary
from filterEvents import load_events, apply_filters, convert_to_serializable

app = FastAPI()

@app.get("/cities")
def get_cities():
    try:
        df = load_city_summary()
        # Sort by duration_seconds (ascending)
        if 'duration_seconds' in df.columns:
            df = df.sort_values(by='duration_seconds', ascending=True)
        
        # Convert to list of dictionaries
        result = df.to_dict(orient='records')
        return convert_to_serializable(result)
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
        events = load_events()
        filtered_events = apply_filters(
            events, 
            location=location, 
            dates=dates, 
            weekdays=weekdays, 
            event_types=event_type, 
            audiences=audience
        )
        return convert_to_serializable(filtered_events)
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
