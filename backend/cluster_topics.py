import os
import random
import re
import colorsys
from datetime import datetime
from collections import Counter

import lancedb
import pandas as pd
import pyarrow as pa
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import torch


CUSTOM_CLUSTER_STOP_WORDS = {
    # 1. TIME & DATE (Pure noise)
    "pm", "am", "pst", "est", "pt", "april", "march", "june", "july", "may",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "day", "week", "evening", "night", "daily", "monthly", "year", "years", "time",
    "th", "rd", "st", "nd", "today", "tomorrow", "afternoon", "morning", "date",
    "schedule", "agenda", "minute", "minutes", "hour", "hours",

    # 2. LOGISTICS & VENUE (Generic locations)
    "registration", "registering", "rsvp", "floor", "floors", "room", "venue",
    "location", "office", "offices", "street", "parking", "doors", "arrival",
    "capacity", "spots", "tickets", "ticket", "staff", "id", "valid", "required",
    "lounge", "house", "tower", "frontiertower", "village", "center", "hub",
    "space", "spaces", "hall", "suite", "site", "area", "district", "city",

    # 3. HOSPITALITY & GENERIC SOCIAL (Non-content noise)
    "drinks", "dinner", "food", "coffee", "breakfast", "lunch", "refreshments",
    "snacks", "bites", "cocktails", "wine", "pizza", "beverages", "alcohol", "meal",
    "join", "us", "community", "welcome", "happy", "friends", "everyone", "folks",
    "guest", "guests", "vibe", "vibes", "party", "reception", "hang", "mingle",
    "mingling", "thank", "thanks", "curated", "intimate", "casual", "fun",

    # 4. TECH & BUSINESS "FLUFF" (Vague buzzwords)
    "tech", "technology", "technologies", "startup", "startups", "founders",
    "founder", "founding", "ceo", "builders", "innovation", "innovators",
    "leadership", "executive", "professional", "impact", "mission", "missiondriven",
    "strategic", "strategy", "solutions", "platform", "platforms", "scale", "scaling",
    "growth", "potential", "forward", "transforming", "transformation", "shaping",
    "building", "build", "create", "creating", "vision", "visionary", "excellence",
    "value", "values", "movement", "opportunity", "opportunities", "world", "global",
    "modern", "future", "next", "advanced", "era", "ecosystem", "ecosystems",

    # 5. VAGUE ACTION VERBS & ADJECTIVES (Fillers)
    "exploring", "explore", "learn", "bringing", "happen", "making", "using",
    "driven", "designed", "facilitated", "powered", "real", "one", "get", "up",
    "co", "can", "all", "where", "across", "new", "together", "first", "most",
    "just", "work", "apply", "share", "here", "out", "has", "why", "early",
    "should", "like", "part", "over", "working", "need", "only", "when", "do",
    "so", "want", "expect", "actually", "whether", "other", "before", "become",
    "any", "each", "after", "than", "beyond", "ready", "must", "simply",
    "big", "you're", "please", "we're", "agree",
    "we'll", "jill", "what's", "director", "khosla", "he", "she", "they", "women", "woman",
    "tiat", "runway", "flybetter",
    "fyi", "slack", "members", "jepa", "lps", "femigrants", "immigrants", "european",
    "person", "east", "west", "north", "south",
    "female", "immigrant", "wwdc", "swift", "meetup", "v11", "social", "connections",
    "conversations", "content",
    "group", "see", "humanx", "collective", "gathering",
    "make", "good", "non", "but", "german", "ontology", "flourishing",
    "gain", "via",
    "something",
    "brazil", "there",
    "above", "also", "vently",
    "while",
    "intersection", "some", "swissnex",
    "communitykit",
    "best",
    "oro",
    "her",
    "taiwan",
    "limited", "hosts", "around",
    "self", "governed", "vertical", "public", "series", "water",
    "growthx", "bro", "tour", "stage", "these", "morgan", "help", "rural", "wants", "techequity", "including",
    "bubbl", "stay", "fellow", "clay", "let", "his", "legacy", "senior", "being", "zero", "convex",

    # 6. DOCUMENT META & GEOGRAPHY (Data artifact noise)
    "https", "com", "www", "io", "website", "post", "link", "information",
    "details", "intro", "introduction", "overview", "summary", "slides", "q", "a",
    "email", "linkedin", "instagram", "twitter", "follow", "visit", "check",
    "san", "francisco", "sf", "bay", "california", "valley", "silicon", "oakland",
    "palo", "alto", "menlo", "ca", "usa", "berkeley", "stanford", "leopard",
}


def get_db_path():
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def build_topic_label(topic_model, topic_id):
    if topic_id == -1:
        return "Other"
    words = topic_model.get_topic(topic_id) or []
    top_terms = [word for word, _ in words[:3]]
    if not top_terms:
        return f"Topic {topic_id}"
    return " / ".join(top_terms)


def random_hex_color():
    hue = random.random()
    saturation = random.uniform(0.55, 0.85)
    lightness = random.uniform(0.20, 0.40)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(red * 255):02X}{int(green * 255):02X}{int(blue * 255):02X}"


def assign_outliers_to_fallback(topics):
    """Ensure every event has a concrete topic id by remapping BERTopic outliers (-1)."""
    non_outliers = [topic for topic in topics if topic != -1]
    if non_outliers:
        fallback_topic = max(set(non_outliers), key=non_outliers.count)
    else:
        fallback_topic = 0
    return [fallback_topic if topic == -1 else topic for topic in topics]


def next_cluster_id(counter_state):
    cluster_id = counter_state[0]
    counter_state[0] += 1
    return cluster_id


def summarize_cluster_label(docs, max_terms=3):
    token_counts = Counter()
    for doc in docs:
        token_counts.update(token for token in tokenize_text(doc) if len(token) > 2 and not token.isdigit())

    top_terms = [word for word, _ in token_counts.most_common(max_terms)]
    if not top_terms:
        return "Misc"
    return " / ".join(top_terms)


def tokenize_text(text):
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", (text or "").lower())


def remove_high_frequency_stopwords(docs, frequency_threshold=0.001, base_stopwords=None):
    """
    Remove words that appear in more than `frequency_threshold` of all corpus tokens.
    frequency_threshold=0.001 corresponds to 0.1%.
    """
    tokenized_docs = [tokenize_text(doc) for doc in docs]
    all_tokens = [token for doc_tokens in tokenized_docs for token in doc_tokens]

    if not all_tokens:
        return docs, set()

    token_counts = Counter(all_tokens)
    total_tokens = len(all_tokens)
    dynamic_stopwords = {
        token
        for token, count in token_counts.items()
        if (count / total_tokens) > frequency_threshold
    }
    combined_stopwords = dynamic_stopwords.union(base_stopwords or set())

    filtered_docs = [
        " ".join(token for token in doc_tokens if token not in combined_stopwords)
        for doc_tokens in tokenized_docs
    ]
    return filtered_docs, dynamic_stopwords


def cluster_documents_recursively(
    docs,
    indices,
    total_docs,
    cluster_id_counter,
    min_topic_size,
    max_cluster_fraction=0.10,
):
    """Recursively cluster documents until no cluster exceeds the corpus fraction threshold."""
    subset_docs = [docs[index] for index in indices]
    subset_size = len(indices)

    if subset_size == 0:
        return {}, {}, {}

    # Base case: tiny groups or groups already under the split threshold become leaf clusters.
    if subset_size == 1 or (subset_size / total_docs) <= max_cluster_fraction or subset_size < 2:
        cluster_id = next_cluster_id(cluster_id_counter)
        label = summarize_cluster_label(subset_docs)
        color = random_hex_color()
        return {index: cluster_id for index in indices}, {cluster_id: label}, {cluster_id: color}

    effective_min_topic_size = max(2, min(min_topic_size, max(2, subset_size // 10)))
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    embedding_model = SentenceTransformer(
        "all-MiniLM-L6-v2",
        device=device,
    )

    topic_model = BERTopic(
        embedding_model=embedding_model,
        min_topic_size=effective_min_topic_size,
        calculate_probabilities=False,
        verbose=False,
    )

    topics, _ = topic_model.fit_transform(subset_docs)
    topics = assign_outliers_to_fallback(topics)

    groups = {}
    for local_index, topic_id in enumerate(topics):
        groups.setdefault(topic_id, []).append(indices[local_index])

    # If BERTopic could not split the subset meaningfully, treat it as one leaf cluster.
    if len(groups) <= 1:
        cluster_id = next_cluster_id(cluster_id_counter)
        label = summarize_cluster_label(subset_docs)
        color = random_hex_color()
        return {index: cluster_id for index in indices}, {cluster_id: label}, {cluster_id: color}

    doc_to_cluster = {}
    cluster_labels = {}
    cluster_colors = {}

    for topic_id, topic_indices in groups.items():
        topic_size = len(topic_indices)
        topic_ratio = topic_size / total_docs

        # Split again if this cluster is still too large and has enough documents to cluster.
        if topic_size > 1 and topic_ratio > max_cluster_fraction:
            child_doc_to_cluster, child_labels, child_colors = cluster_documents_recursively(
                docs=docs,
                indices=topic_indices,
                total_docs=total_docs,
                cluster_id_counter=cluster_id_counter,
                min_topic_size=min_topic_size,
                max_cluster_fraction=max_cluster_fraction,
            )
            doc_to_cluster.update(child_doc_to_cluster)
            cluster_labels.update(child_labels)
            cluster_colors.update(child_colors)
            continue

        cluster_id = next_cluster_id(cluster_id_counter)
        label = summarize_cluster_label([docs[index] for index in topic_indices])
        color = random_hex_color()
        for index in topic_indices:
            doc_to_cluster[index] = cluster_id
        cluster_labels[cluster_id] = label
        cluster_colors[cluster_id] = color

    return doc_to_cluster, cluster_labels, cluster_colors


def _to_text_or_none(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


def _to_float_or_none(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value):
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_events_arrow_table(df):
    records = []
    for _, row in df.iterrows():
        coordinates = row.get("coordinates") if isinstance(row.get("coordinates"), dict) else {}
        records.append(
            {
                "id": _to_text_or_none(row.get("id")),
                "name": _to_text_or_none(row.get("name")),
                "url": _to_text_or_none(row.get("url")),
                "start_at": _to_text_or_none(row.get("start_at")),
                "end_at": _to_text_or_none(row.get("end_at")),
                "description": _to_text_or_none(row.get("description")),
                "timezone": _to_text_or_none(row.get("timezone")),
                "pricing": _to_text_or_none(row.get("pricing")),
                "city": _to_text_or_none(row.get("city")),
                "coordinates": {
                    "latitude": _to_float_or_none(coordinates.get("latitude")),
                    "longitude": _to_float_or_none(coordinates.get("longitude")),
                },
                "bookmarked": bool(row.get("bookmarked", False)),
                "topic_id": _to_int_or_none(row.get("topic_id")),
                "topic_label": _to_text_or_none(row.get("topic_label")),
                "topic_color": _to_text_or_none(row.get("topic_color")),
                "cosine_distance": _to_float_or_none(row.get("cosine_distance")),
            }
        )

    coordinates_array = pa.array(
        [record["coordinates"] for record in records],
        type=pa.struct(
            [
                pa.field("latitude", pa.float64()),
                pa.field("longitude", pa.float64()),
            ]
        ),
    )

    arrays = [
        pa.array([record["id"] for record in records], type=pa.string()),
        pa.array([record["name"] for record in records], type=pa.string()),
        pa.array([record["url"] for record in records], type=pa.string()),
        pa.array([record["start_at"] for record in records], type=pa.string()),
        pa.array([record["end_at"] for record in records], type=pa.string()),
        pa.array([record["description"] for record in records], type=pa.string()),
        pa.array([record["timezone"] for record in records], type=pa.string()),
        pa.array([record["pricing"] for record in records], type=pa.string()),
        pa.array([record["city"] for record in records], type=pa.string()),
        coordinates_array,
        pa.array([record["bookmarked"] for record in records], type=pa.bool_()),
        pa.array([record["topic_id"] for record in records], type=pa.int64()),
        pa.array([record["topic_label"] for record in records], type=pa.string()),
        pa.array([record["topic_color"] for record in records], type=pa.string()),
        pa.array([record["cosine_distance"] for record in records], type=pa.float64()),
    ]

    field_names = [
        "id",
        "name",
        "url",
        "start_at",
        "end_at",
        "description",
        "timezone",
        "pricing",
        "city",
        "coordinates",
        "bookmarked",
        "topic_id",
        "topic_label",
        "topic_color",
        "cosine_distance",
    ]

    return pa.Table.from_arrays(arrays, names=field_names)


def backup_events_table(db, events_df):
    backup_df = events_df.copy()
    backup_df = backup_df.where(pd.notna(backup_df), None)

    text_columns = [
        "id",
        "name",
        "url",
        "start_at",
        "end_at",
        "description",
        "timezone",
        "pricing",
        "city",
        "topic_label",
        "topic_color",
    ]
    for column in text_columns:
        if column in backup_df.columns:
            backup_df[column] = backup_df[column].apply(
                lambda value: str(value) if value is not None and not isinstance(value, str) else value
            )

    timestamp = int(datetime.now().timestamp())
    backup_name = f"events_backup_before_clustering_{timestamp}"
    db.create_table(backup_name, data=backup_df.to_dict("records"), mode="overwrite")
    print(f"Created backup table: {backup_name}")
    return backup_name


def get_table_names(db):
    """Return table names across LanceDB versions where list_tables/table_names differ."""
    tables = []

    def _extract_names(raw):
        # Common shape: ['events', 'city_summary']
        if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
            return raw

        # Shape: {'tables': [...], 'page_token': ...}
        if isinstance(raw, dict):
            if isinstance(raw.get("tables"), list):
                return [str(x) for x in raw["tables"]]
            return [str(x) for x in raw.keys()]

        # Shape: [('tables', [...]), ('page_token', None)]
        if isinstance(raw, list) and raw and all(isinstance(x, tuple) and len(x) == 2 for x in raw):
            as_dict = dict(raw)
            if isinstance(as_dict.get("tables"), list):
                return [str(x) for x in as_dict["tables"]]

        return None

    if hasattr(db, "list_tables"):
        try:
            raw_tables = db.list_tables()
            extracted = _extract_names(raw_tables)
            tables = extracted if extracted is not None else (raw_tables or [])
        except Exception:
            tables = []

    if (not tables) and hasattr(db, "table_names"):
        try:
            raw_tables = db.table_names()
            extracted = _extract_names(raw_tables)
            tables = extracted if extracted is not None else (raw_tables or [])
        except Exception:
            tables = []

    normalized = []
    for table in tables:
        if isinstance(table, str):
            normalized.append(table)
        elif isinstance(table, dict) and isinstance(table.get("name"), str):
            normalized.append(table["name"])
        else:
            normalized.append(str(table))

    return normalized


def cluster_event_topics(min_topic_size=8):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    try:
        table = db.open_table("events")
    except Exception as exc:
        table_names = get_table_names(db)
        print(f"events table not found. Available tables: {table_names}")
        print(f"open_table('events') error: {exc}")
        return
    df = table.to_pandas()

    # Safety gate: backup must succeed before any clustering work proceeds.
    try:
        backup_events_table(db, df)
        print("Backup check succeeded.")
    except Exception as exc:
        print(f"Backup failed, aborting clustering: {exc}")
        return

    if df.empty:
        print("No events to cluster")
        return

    docs = []
    for _, row in df.iterrows():
        name = row.get("name") or ""
        description = row.get("description") or ""
        docs.append(f"{name}\n\n{description}".strip())

    clustering_docs, dynamic_stopwords = remove_high_frequency_stopwords(
        docs,
        frequency_threshold=0.001,
        base_stopwords=CUSTOM_CLUSTER_STOP_WORDS,
    )
    print(
        "Removed "
        f"{len(dynamic_stopwords)} high-frequency stopwords (>0.1% corpus frequency) "
        f"plus {len(CUSTOM_CLUSTER_STOP_WORDS)} custom stop words for clustering input."
    )

    cluster_id_counter = [0]
    doc_to_cluster, cluster_labels, cluster_colors = cluster_documents_recursively(
        docs=clustering_docs,
        indices=list(range(len(clustering_docs))),
        total_docs=len(clustering_docs),
        cluster_id_counter=cluster_id_counter,
        min_topic_size=min_topic_size,
        max_cluster_fraction=0.10,
    )

    topics = [doc_to_cluster[index] for index in range(len(clustering_docs))]
    labels = [cluster_labels[topic_id] for topic_id in topics]
    colors = [cluster_colors[topic_id] for topic_id in topics]

    df["topic_id"] = topics
    df["topic_label"] = labels
    df["topic_color"] = colors

    events_table = build_events_arrow_table(df)
    db.create_table("events", data=events_table, mode="overwrite")

    cluster_counts = Counter(topics)
    summary_rows = sorted(
        (
            (cluster_id, count, cluster_labels.get(cluster_id, "Misc"))
            for cluster_id, count in cluster_counts.items()
        ),
        key=lambda item: (-item[1], item[0]),
    )
    print("Updated topic clusters.")
    print(f"{'Topic':>6}  {'Count':>5}  Name")
    for cluster_id, count, label in summary_rows[:20]:
        print(f"{cluster_id:>6}  {count:>5}  {label}")


if __name__ == "__main__":
    cluster_event_topics()
