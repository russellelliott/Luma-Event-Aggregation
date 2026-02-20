from sentence_transformers import SentenceTransformer
import numpy as np
import os
import torch

# Global model instance
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            print("Loading SentenceTransformer model for search...")
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            print(f"Using device: {device}")
            _model = SentenceTransformer(
                'jinaai/jina-embeddings-v2-base-en',
                trust_remote_code=True,
                device=device
            )
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    return _model

def search_events(query, events):
    """
    Search events by query string.
    
    Args:
        query (str): The search query.
        events (list): List of event dictionaries (must contain 'vector' field).
        
    Returns:
        list: events with updated 'cosine_distance' based on query.
    """
    model = get_model()
    if not model or not query:
        return events
        
    try:
        query_vector = model.encode(query)
        
        # Calculate distance for all events
        for e in events:
            # Handle nested structure if vector is inside event or top level
            # Based on add_embeddings.py, 'vector' is added to the row, so it should be at top level
            vec = e.get('vector')
            
            if vec is not None and isinstance(vec, (list, np.ndarray)):
                vec_np = np.array(vec)
                norm_vec = np.linalg.norm(vec_np)
                norm_query = np.linalg.norm(query_vector)
                
                if norm_vec > 0 and norm_query > 0:
                    cosine_sim = np.dot(vec_np / norm_vec, query_vector / norm_query)
                    # Distance = 1 - Similarity
                    e['cosine_distance'] = float(1 - cosine_sim)
                else:
                    e['cosine_distance'] = None
            else:
                e['cosine_distance'] = None
                
        return events
    except Exception as e:
        print(f"Error during search: {e}")
        return events
