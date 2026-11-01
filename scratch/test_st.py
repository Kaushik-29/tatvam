import time
from sentence_transformers import SentenceTransformer

print("Testing SentenceTransformer initialization...", flush=True)
t0 = time.time()
try:
    # Try BAAI/bge-m3 since it's already in the cache!
    model = SentenceTransformer("BAAI/bge-m3")
    print(f"Loaded BAAI/bge-m3 in {time.time()-t0:.2f}s", flush=True)
    emb = model.encode(["Chest pain with dyspnea", "Gastroesophageal reflux disease"])
    print(f"Encoded shape: {emb.shape}", flush=True)
except Exception as e:
    print(f"BAAI/bge-m3 error: {e}", flush=True)
    # Fallback check for all-MiniLM-L6-v2
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        print(f"Loaded all-MiniLM-L6-v2 in {time.time()-t0:.2f}s", flush=True)
        emb = model.encode(["Chest pain", "Fever"])
        print(f"Encoded shape: {emb.shape}", flush=True)
    except Exception as e2:
        print(f"all-MiniLM-L6-v2 error: {e2}", flush=True)
