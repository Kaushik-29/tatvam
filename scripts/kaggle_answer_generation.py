# Kaggle notebook: generate MedResolve answers on a GPU with the SAME Ollama model the app uses.
# Input : answer_prompts_*.jsonl  (made locally by: run_response_eval --mode export)
# Output: /kaggle/working/answers_<same name>.jsonl  -> back on the PC: run_response_eval --mode import
# Settings: Accelerator = GPU T4 x1, Internet = On. Safe to re-run: finished prompts are skipped.
# The same file also runs locally (python scripts/kaggle_answer_generation.py <prompts> <answers>).

# ---------------- CELL 1: install and start Ollama, pull the model ----------------
# !apt-get install -y -qq zstd            # the Ollama installer needs zstd; Kaggle images lack it
# !curl -fsSL https://ollama.com/install.sh | sh
# import subprocess, time; subprocess.Popen(["ollama", "serve"]); time.sleep(5)
# !ollama pull llama3.2:3b

# ---------------- CELL 2: generate ----------------
import glob
import json
import os
import platform
import sys
import time
import urllib.request

URL = "http://127.0.0.1:11434"
MODEL = "llama3.2:3b"


def _post(path, payload, timeout=600):
    req = urllib.request.Request(URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def model_info():
    tags = json.load(urllib.request.urlopen(URL + "/api/tags", timeout=10))["models"]
    m = next((t for t in tags if t["name"] == MODEL), None)
    if m is None:
        raise SystemExit(f"{MODEL} is not pulled")
    ver = json.load(urllib.request.urlopen(URL + "/api/version", timeout=10)).get("version")
    try:
        import subprocess
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True,
                             text=True).stdout.strip() or "no GPU"
    except Exception:
        gpu = "no GPU"
    return {"model_digest": m["digest"], "ollama_version": ver, "hardware": f"{platform.node()} / {gpu}"}


def run(inp, out):
    rows = [json.loads(l) for l in open(inp, encoding="utf-8") if l.strip()]
    done = {json.loads(l)["id"] for l in open(out, encoding="utf-8") if l.strip()} if os.path.exists(out) else set()
    todo = [r for r in rows if r["id"] not in done]
    meta = model_info()
    print(f"{len(rows)} prompts, {len(done)} done, {len(todo)} to go | {MODEL} {meta['model_digest'][:12]} | {meta['hardware']}")
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            payload = {"model": MODEL, "prompt": r["prompt"], "stream": False, "options": r["options"]}
            if r.get("system"):
                payload["system"] = r["system"]
            ts = time.time()
            resp = _post("/api/generate", payload)["response"]
            f.write(json.dumps({"id": r["id"], "today": r.get("today"), "model": MODEL, **meta,
                                "response": resp, "generation_s": round(time.time() - ts, 2)}) + "\n")
            f.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  ({(time.time() - t0) / i:.1f}s per answer)", flush=True)


# Kaggle first: inside Jupyter sys.argv is [launcher, "-f", kernel.json], which also has 3 entries
if os.path.exists("/kaggle/input"):                         # Kaggle notebook
    for inp in sorted(glob.glob("/kaggle/input/**/answer_prompts_*.jsonl", recursive=True)):
        run(inp, "/kaggle/working/" + os.path.basename(inp).replace("answer_prompts_", "answers_"))
elif __name__ == "__main__" and len(sys.argv) == 3:          # local use
    run(sys.argv[1], sys.argv[2])
