import uuid


def _to_float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_luma_event(raw):
    """Normalize a raw Luma event payload into the flat project schema."""
    base = raw.get("event") if isinstance(raw.get("event"), dict) else raw
    geo = base.get("geo_address_info") if isinstance(base.get("geo_address_info"), dict) else {}
    cal = raw.get("calendar") if isinstance(raw.get("calendar"), dict) else {}
    loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    loc_geo = loc.get("geo") if isinstance(loc.get("geo"), dict) else {}
    coord = base.get("coordinate") if isinstance(base.get("coordinate"), dict) else {}

    city = (
        geo.get("city_state")
        or geo.get("city")
        or (
            f'{cal.get("geo_city")}, {cal.get("geo_region_abbrev") or cal.get("geo_region")}'
            if cal.get("geo_city")
            else None
        )
    )

    latitude = (
        coord.get("latitude")
        or loc.get("latitude")
        or loc_geo.get("latitude")
        or geo.get("latitude")
    )
    longitude = (
        coord.get("longitude")
        or loc.get("longitude")
        or loc_geo.get("longitude")
        or geo.get("longitude")
    )

    url = base.get("url")
    if url and not str(url).startswith("http"):
        url = f"https://luma.com/{url}"

    existing_id = raw.get("id") or base.get("id")

    return {
        "id": existing_id if isinstance(existing_id, str) and existing_id else str(uuid.uuid4()),
        "name": base.get("name") or base.get("title"),
        "url": url,
        "start_at": base.get("start_at") or raw.get("start_at"),
        "end_at": base.get("end_at") or raw.get("end_at"),
        "description": base.get("description") or raw.get("description"),
        "timezone": base.get("timezone") or raw.get("timezone") or "America/Los_Angeles",
        "pricing": base.get("pricing") or raw.get("pricing"),
        "city": city,
        "coordinates": {
            "latitude": _to_float_or_none(latitude),
            "longitude": _to_float_or_none(longitude),
        },
        "bookmarked": bool(raw.get("bookmarked", False)),
        "vector": raw.get("vector"),
        "topic_id": raw.get("topic_id"),
        "topic_label": raw.get("topic_label"),
        "topic_color": raw.get("topic_color"),
        "cosine_distance": raw.get("cosine_distance"),
    }
