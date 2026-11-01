import json
import time
import urllib.request

payload = {
    'model': 'llama3.2:3b',
    'prompt': 'Briefly summarize in 1 sentence what vasovagal syncope is.',
    'stream': False,
    'options': {'temperature': 0.1, 'num_predict': 100}
}
t0 = time.perf_counter()
req = urllib.request.Request(
    'http://localhost:11434/api/generate',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req, timeout=30)
t_elapsed = time.perf_counter() - t0
res = json.loads(resp.read().decode('utf-8'))
print("Response:", res.get("response", "").strip())
print(f"Time: {t_elapsed:.2f}s")
print(f"Eval count (output tokens): {res.get('eval_count')}")
print(f"Prompt eval count (input tokens): {res.get('prompt_eval_count')}")
print(f"Prompt eval duration: {res.get('prompt_eval_duration') / 1e6:.1f}ms")
print(f"Eval duration: {res.get('eval_duration') / 1e6:.1f}ms")
