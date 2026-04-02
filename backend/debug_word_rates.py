import os
import re
from collections import Counter

import lancedb
import pandas as pd


OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "common_word_rates.txt")


def get_db_path():
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def tokenize_text(text):
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", (text or "").lower())


def load_event_docs(db):
    table = db.open_table("events")
    df = table.to_pandas()

    docs = []
    for _, row in df.iterrows():
        name = row.get("name") or ""
        description = row.get("description") or ""
        docs.append(f"{name}\n\n{description}".strip())

    return docs


def main():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    if "events" not in getattr(db, "table_names", lambda: [])() and "events" not in getattr(db, "list_tables", lambda: [])():
        print("events table not found")
        return

    docs = load_event_docs(db)
    tokenized_docs = [tokenize_text(doc) for doc in docs]
    all_tokens = [token for doc_tokens in tokenized_docs for token in doc_tokens]

    if not all_tokens:
        print("No tokens found in event text.")
        return

    token_counts = Counter(all_tokens)
    total_tokens = len(all_tokens)
    repeated_token_counts = {word: count for word, count in token_counts.items() if count >= 10}

    lines = []
    lines.append(f"Total documents: {len(docs)}")
    lines.append(f"Total tokens: {total_tokens}")
    lines.append(f"Words appearing at least 10 times: {len(repeated_token_counts)}")
    lines.append("")
    lines.append(f"{'Word':<30} | {'Count':<10} | {'Percent':<10}")
    lines.append("-" * 60)

    for word, count in sorted(repeated_token_counts.items(), key=lambda item: item[1], reverse=True):
        percent = (count / total_tokens) * 100
        lines.append(f"{word:<30} | {count:<10} | {percent:>8.4f}%")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines) + "\n")

    print(f"Wrote common-word report to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()