import os

import lancedb
import pandas as pd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import torch


PALETTE = [
    "#0EA5E9",
    "#22C55E",
    "#F97316",
    "#EAB308",
    "#EF4444",
    "#14B8A6",
    "#3B82F6",
    "#84CC16",
    "#F59E0B",
    "#06B6D4",
]


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


def cluster_event_topics(min_topic_size=8):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    if "events" not in db.table_names():
        print("events table not found")
        return

    table = db.open_table("events")
    df = table.to_pandas()
    if df.empty:
        print("No events to cluster")
        return

    docs = []
    for _, row in df.iterrows():
        name = row.get("name") or ""
        description = row.get("description") or ""
        docs.append(f"{name}\n\n{description}".strip())

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    embedding_model = SentenceTransformer(
        "jinaai/jina-embeddings-v2-base-en",
        trust_remote_code=True,
        device=device,
    )

    topic_model = BERTopic(
        embedding_model=embedding_model,
        min_topic_size=min_topic_size,
        calculate_probabilities=False,
        verbose=True,
    )
    topics, _ = topic_model.fit_transform(docs)

    unique_topics = sorted({topic for topic in topics if topic != -1})
    topic_color_map = {topic_id: PALETTE[i % len(PALETTE)] for i, topic_id in enumerate(unique_topics)}
    topic_color_map[-1] = "#64748B"

    labels = []
    colors = []
    for topic_id in topics:
        labels.append(build_topic_label(topic_model, topic_id))
        colors.append(topic_color_map.get(topic_id, "#64748B"))

    df["topic_id"] = topics
    df["topic_label"] = labels
    df["topic_color"] = colors

    db.create_table("events", data=df.to_dict("records"), mode="overwrite")

    topic_info = topic_model.get_topic_info()
    print("Updated topic clusters.")
    print(topic_info[["Topic", "Count", "Name"]].head(20).to_string(index=False))


if __name__ == "__main__":
    cluster_event_topics()
