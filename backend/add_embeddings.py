import lancedb
import os
import pandas as pd
from sentence_transformers import SentenceTransformer
import torch

def add_embeddings():
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    try:
        print("Loading SentenceTransformer model...")
        # Check for MPS availability
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"Using device: {device}")
        
        model = SentenceTransformer(
            'jinaai/jina-embeddings-v2-base-en',
            trust_remote_code=True,
            device=device
        )

        db = lancedb.connect(db_path)
        if "events" not in db.table_names():
            print("Table 'events' not found")
            return

        table = db.open_table("events")
        df = table.to_pandas()
        
        print(f"Generating embeddings for {len(df)} events...")
        
        embeddings = []
        for index, row in df.iterrows():
            title = row.get('name', '')
            description = row.get('description', '')

            combined_text = f"{title}\n\n{description}"
            # Encode returns numpy array, convert to list for storage if needed or LanceDB handles it
            vector = model.encode(combined_text).tolist()
            embeddings.append(vector)
            
            if (index + 1) % 10 == 0:
                print(f"Processed {index + 1}/{len(df)} events")

        df['vector'] = embeddings
        
        print("Saving back to database...")
        # Overwrite the table with the new schema containing embeddings
        db.create_table("events", data=df, mode="overwrite")
        print("Successfully added embeddings to all events.")
            
    except Exception as e:
        print(f"Error updating database: {e}")

if __name__ == "__main__":
    add_embeddings()
