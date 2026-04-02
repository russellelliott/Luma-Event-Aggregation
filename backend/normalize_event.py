import uuid


def _to_float_or_none(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_text_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


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


def normalize_luma_event(raw):
    """Normalize a raw Luma event payload into the flat project schema."""
    base = raw.get("event") if isinstance(raw.get("event"), dict) else raw
    geo = base.get("geo_address_info") if isinstance(base.get("geo_address_info"), dict) else {}
    cal = raw.get("calendar") if isinstance(raw.get("calendar"), dict) else {}
    loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    loc_geo = loc.get("geo") if isinstance(loc.get("geo"), dict) else {}
    coord = base.get("coordinate") if isinstance(base.get("coordinate"), dict) else {}
    address = base.get("address") if isinstance(base.get("address"), dict) else raw.get("address") if isinstance(raw.get("address"), dict) else {}
    location_name = base.get("location_name") or raw.get("location_name")

    city = (
        geo.get("city_state")
        or geo.get("city")
        or _extract_city_from_address(address)
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
        "id": _to_text_or_none(existing_id) or str(uuid.uuid4()),
        "name": _to_text_or_none(base.get("name") or base.get("title")),
        "url": _to_text_or_none(url),
        "start_at": _to_text_or_none(base.get("start_at") or raw.get("start_at")),
        "end_at": _to_text_or_none(base.get("end_at") or raw.get("end_at")),
        "description": _to_text_or_none(base.get("description") or raw.get("description")),
        "timezone": _to_text_or_none(base.get("timezone") or raw.get("timezone")) or "America/Los_Angeles",
        "pricing": base.get("pricing") or raw.get("pricing"),
        "city": _to_text_or_none(city),
        "coordinates": {
            "latitude": _to_float_or_none(latitude),
            "longitude": _to_float_or_none(longitude),
        },
        "bookmarked": bool(raw.get("bookmarked", False)),
        "topic_id": raw.get("topic_id"),
        "topic_label": _to_text_or_none(raw.get("topic_label")),
        "topic_color": _to_text_or_none(raw.get("topic_color")),
        "cosine_distance": raw.get("cosine_distance"),
    }
