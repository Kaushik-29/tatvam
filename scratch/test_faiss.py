import faiss
import numpy as np

print("Testing FAISS FlatIP index...", flush=True)
d = 1024
index = faiss.IndexFlatIP(d)

# Create 2 normalized vectors
vecs = np.random.randn(2, d).astype(np.float32)
faiss.normalize_L2(vecs)

index.add(vecs)
print(f"Index total: {index.ntotal}", flush=True)

query = np.random.randn(1, d).astype(np.float32)
faiss.normalize_L2(query)

scores, indices = index.search(query, k=2)
print("Search scores:", scores, "indices:", indices, flush=True)
print("FAISS works perfectly!", flush=True)
