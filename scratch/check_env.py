import sys

print("Python:", sys.version)

for mod in ["torch", "sentence_transformers", "transformers", "faiss", "rank_bm25", "sklearn"]:
    try:
        m = __import__(mod)
        print(f"{mod}: available (version: {getattr(m, '__version__', 'unknown')})")
    except ImportError as e:
        print(f"{mod}: NOT available ({e})")
