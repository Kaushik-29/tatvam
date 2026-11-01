import sys
import time

print("Testing torch import...", flush=True)
t0 = time.time()
try:
    import torch
    print(f"torch OK in {time.time()-t0:.2f}s, version: {torch.__version__}", flush=True)
except Exception as e:
    print(f"torch err: {e}", flush=True)

print("Testing sentence_transformers import...", flush=True)
t0 = time.time()
try:
    import sentence_transformers
    print(f"sentence_transformers OK in {time.time()-t0:.2f}s, version: {sentence_transformers.__version__}", flush=True)
except Exception as e:
    print(f"sentence_transformers err: {e}", flush=True)
